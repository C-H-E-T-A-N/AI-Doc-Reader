"""Pydantic request/response models shared across routes."""

from pydantic import BaseModel


class DocumentUploadResponse(BaseModel):
    document_id: str
    filename: str
    pages: int
    characters: int
    status: str
