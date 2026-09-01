"""
POST /documents/upload

Route responsibilities only: validate the request, delegate to services,
shape the response. No PDF-parsing logic lives here -- that's
app/services/document_loader.py's job. This separation means the
extraction logic can be unit-tested without spinning up FastAPI at all.
"""

import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.config import settings
from app.models.schemas import DocumentUploadResponse
from app.services.document_loader import PDFExtractionError, extract_text

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(file: UploadFile = File(...)) -> DocumentUploadResponse:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are supported.",
        )

    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)

    # A random ID, not the original filename, is used on disk and as the
    # key later stages (chunking, vector store metadata) reference this
    # document by -- two uploads of "handbook.pdf" must not collide.
    document_id = uuid.uuid4().hex
    dest_path = upload_dir / f"{document_id}.pdf"

    max_bytes = settings.max_upload_mb * 1024 * 1024
    size = 0
    with dest_path.open("wb") as out_file:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > max_bytes:
                out_file.close()
                dest_path.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"File exceeds the {settings.max_upload_mb}MB upload limit.",
                )
            out_file.write(chunk)

    if size == 0:
        dest_path.unlink(missing_ok=True)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty.")

    try:
        extracted = extract_text(str(dest_path))
    except PDFExtractionError as e:
        dest_path.unlink(missing_ok=True)
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)) from e

    return DocumentUploadResponse(
        document_id=document_id,
        filename=file.filename,
        pages=extracted.total_pages,
        characters=extracted.total_characters,
        status="uploaded",
    )
