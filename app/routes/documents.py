"""
POST /documents/upload

Route responsibilities only: validate the request, delegate to services,
shape the response. No PDF-parsing/chunking/embedding logic lives here
-- that's what document_loader.py, chunker.py, and embeddings.py are
for. This separation means each piece can be (and was, in earlier
stages) unit-tested without spinning up FastAPI at all.

This is also where ingestion actually happens: extract -> chunk ->
embed -> store, the full left-hand side of the architecture diagram in
the README. Everything up to this stage built the pieces; this route
is the first place they're chained together for real.
"""

import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.config import settings
from app.dependencies import get_embedding_service, get_vector_store
from app.models.schemas import DocumentUploadResponse
from app.services.chunker import chunk_pages
from app.services.document_loader import PDFExtractionError, extract_text
from app.services.embeddings import EmbeddingService
from app.services.vector_store import VectorStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    vector_store: VectorStore = Depends(get_vector_store),
) -> DocumentUploadResponse:
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

    chunks = chunk_pages(extracted.pages, chunk_size=settings.chunk_size, chunk_overlap=settings.chunk_overlap)
    logger.info("document_id=%s filename=%s -> %d chunks", document_id, file.filename, len(chunks))

    embeddings = embedding_service.embed_documents([c.text for c in chunks])
    vector_store.add_chunks(
        document_id=document_id,
        filename=file.filename,
        chunks=chunks,
        embeddings=embeddings,
    )

    return DocumentUploadResponse(
        document_id=document_id,
        filename=file.filename,
        pages=extracted.total_pages,
        characters=extracted.total_characters,
        chunks_indexed=len(chunks),
        status="uploaded",
    )
