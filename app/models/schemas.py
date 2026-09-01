"""Pydantic request/response models shared across routes."""

from pydantic import BaseModel, Field


class DocumentInfo(BaseModel):
    """One row in the document registry -- what the UI's sidebar and
    details panel render."""

    document_id: str
    filename: str
    file_type: str
    size_bytes: int
    pages: int
    characters: int
    chunks: int
    uploaded_at: str
    status: str


class DocumentUploadResponse(BaseModel):
    document_id: str
    filename: str
    file_type: str
    size_bytes: int
    pages: int
    characters: int
    chunks_indexed: int
    uploaded_at: str
    status: str


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1)
    # When set, retrieval is restricted to chunks from this one document.
    # When omitted, the search spans every indexed document (leaves the
    # door open for a future "search across all documents" mode).
    document_id: str | None = None


class Source(BaseModel):
    filename: str
    page: int
    # The retrieved passage and its cosine similarity to the question.
    # Both are optional so older clients / empty results still validate.
    text: str | None = None
    score: float | None = None


class ChatResponse(BaseModel):
    answer: str
    sources: list[Source]
