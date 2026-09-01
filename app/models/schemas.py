"""Pydantic request/response models shared across routes."""

from pydantic import BaseModel, Field


class DocumentUploadResponse(BaseModel):
    document_id: str
    filename: str
    pages: int
    characters: int
    chunks_indexed: int
    status: str


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1)


class Source(BaseModel):
    filename: str
    page: int


class ChatResponse(BaseModel):
    answer: str
    sources: list[Source]
