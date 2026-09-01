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
from fastapi.responses import FileResponse

from app.config import settings
from app.dependencies import get_embedding_service, get_vector_store
from app.models.schemas import DocumentInfo, DocumentUploadResponse
from app.services import registry
from app.services.chunker import chunk_pages
from app.services.document_loader import PDFExtractionError, extract_text
from app.services.embeddings import EmbeddingGenerationError, EmbeddingService
from app.services.vector_store import VectorStore, VectorStoreError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])


def _stored_path(document_id: str) -> Path:
    return Path(settings.upload_dir) / f"{document_id}.pdf"


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
    logger.info(
        "document_id=%s filename=%s pages=%d chars=%d -> %d chunks",
        document_id,
        file.filename,
        extracted.total_pages,
        extracted.total_characters,
        len(chunks),
    )

    # Note: a missing API key (ConfigurationError) can't surface here --
    # embedding_service/vector_store are constructed by FastAPI's
    # dependency injection before this function body even starts
    # running, so that failure is handled globally in app/main.py
    # instead. This try/except only covers failures during the actual
    # provider request, after construction succeeded.
    try:
        embeddings = embedding_service.embed_documents([c.text for c in chunks])
        vector_store.add_chunks(
            document_id=document_id,
            filename=file.filename,
            chunks=chunks,
            embeddings=embeddings,
        )
    except (EmbeddingGenerationError, VectorStoreError) as e:
        dest_path.unlink(missing_ok=True)
        logger.error("document_id=%s ingestion failed: %s", document_id, e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to index the document. Please try again.",
        ) from e

    logger.info("document_id=%s indexed successfully, %d chunks stored", document_id, len(chunks))

    uploaded_at = registry.now_iso()
    registry.add_document(
        {
            "document_id": document_id,
            "filename": file.filename,
            "file_type": "pdf",
            "size_bytes": size,
            "pages": extracted.total_pages,
            "characters": extracted.total_characters,
            "chunks": len(chunks),
            "uploaded_at": uploaded_at,
            "status": "indexed",
        }
    )

    return DocumentUploadResponse(
        document_id=document_id,
        filename=file.filename,
        file_type="pdf",
        size_bytes=size,
        pages=extracted.total_pages,
        characters=extracted.total_characters,
        chunks_indexed=len(chunks),
        uploaded_at=uploaded_at,
        status="indexed",
    )


@router.get("", response_model=list[DocumentInfo])
def list_documents() -> list[DocumentInfo]:
    """Every indexed document, newest first -- the sidebar's data source."""
    return [DocumentInfo(**record) for record in registry.list_documents()]


@router.get("/{document_id}", response_model=DocumentInfo)
def get_document(document_id: str) -> DocumentInfo:
    record = registry.get_document(document_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    return DocumentInfo(**record)


@router.delete("/{document_id}", status_code=status.HTTP_200_OK)
def delete_document(
    document_id: str,
    vector_store: VectorStore = Depends(get_vector_store),
) -> dict:
    """Remove a document everywhere: its chunks in the vector store, the
    stored file on disk, and its registry entry."""
    record = registry.get_document(document_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    try:
        vector_store.delete_document(document_id)
    except VectorStoreError as e:
        logger.error("document_id=%s delete failed: %s", document_id, e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to delete the document. Please try again.",
        ) from e

    _stored_path(document_id).unlink(missing_ok=True)
    registry.remove_document(document_id)
    logger.info("document_id=%s deleted", document_id)
    return {"document_id": document_id, "status": "deleted"}


@router.get("/{document_id}/file")
def get_document_file(document_id: str) -> FileResponse:
    """Stream the original PDF so the UI can open a cited page in place."""
    record = registry.get_document(document_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    path = _stored_path(document_id)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stored file is missing.")

    return FileResponse(
        path,
        media_type="application/pdf",
        filename=record.get("filename", f"{document_id}.pdf"),
        content_disposition_type="inline",
    )
