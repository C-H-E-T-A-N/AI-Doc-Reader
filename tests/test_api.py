"""
API-level tests for the wired-together pipeline: upload -> chunk ->
embed -> store, and question -> retrieve -> prompt -> generate.

Real provider calls are swapped for fakes via FastAPI's
dependency_overrides, so these run with no network access and no API
keys -- but every other line of production code (routes, dependency
wiring, chunking, prompt construction, retrieval ranking) runs for
real. This is the same technique used to catch the get_retriever bug
during Stage 8 development: a dependency called directly instead of via
Depends(...) silently bypassed overrides during manual testing.

More edge cases (invalid file types, oversized uploads, provider
failures) are added in Stage 10's full test suite; this file covers the
core happy paths for this stage.
"""

import io

import fitz
import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_embedding_service, get_llm_service, get_vector_store
from app.main import app
from app.services.embeddings import EmbeddingProvider, EmbeddingService
from app.services.llm import LLMProvider, LLMService
from app.services.prompt_builder import Prompt
from app.services.vector_store import VectorStore


class KeywordFakeEmbeddingProvider(EmbeddingProvider):
    """Embeds by presence of a few known keywords, so retrieval ranking is predictable in tests."""

    KEYWORDS = ["leave", "hour", "dress"]

    def embed(self, texts):
        return [[1.0 if kw in t.lower() else 0.0 for kw in self.KEYWORDS] for t in texts]


class EchoFakeLLMProvider(LLMProvider):
    def generate(self, prompt: Prompt) -> str:
        return f"FAKE ANSWER || {prompt.user}"


@pytest.fixture
def client(tmp_path):
    vector_store = VectorStore(persist_directory=str(tmp_path / "chroma"), collection_name="test")

    app.dependency_overrides[get_embedding_service] = lambda: EmbeddingService(
        provider=KeywordFakeEmbeddingProvider()
    )
    app.dependency_overrides[get_vector_store] = lambda: vector_store
    app.dependency_overrides[get_llm_service] = lambda: LLMService(provider=EchoFakeLLMProvider())

    yield TestClient(app)

    app.dependency_overrides.clear()


def _make_pdf_bytes(pages_text: list[str]) -> bytes:
    doc = fitz.open()
    for text in pages_text:
        page = doc.new_page()
        page.insert_text((72, 72), text)
    return doc.write()


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_upload_valid_pdf_returns_metadata(client):
    pdf_bytes = _make_pdf_bytes(["Employees receive 24 paid leaves per year."])
    response = client.post(
        "/documents/upload", files={"file": ("handbook.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["filename"] == "handbook.pdf"
    assert body["pages"] == 1
    assert body["chunks_indexed"] >= 1
    assert body["status"] == "uploaded"


def test_upload_rejects_non_pdf_file(client):
    response = client.post(
        "/documents/upload", files={"file": ("notes.txt", io.BytesIO(b"hello"), "text/plain")}
    )
    assert response.status_code == 400


def test_upload_rejects_empty_file(client):
    response = client.post(
        "/documents/upload", files={"file": ("empty.pdf", io.BytesIO(b""), "application/pdf")}
    )
    assert response.status_code == 400


def test_upload_rejects_pdf_with_no_extractable_text(client):
    doc = fitz.open()
    doc.new_page()  # blank page, no text -- simulates a scanned/image-only PDF
    response = client.post(
        "/documents/upload", files={"file": ("scanned.pdf", io.BytesIO(doc.write()), "application/pdf")}
    )
    assert response.status_code == 422


def test_chat_with_no_documents_uploaded_still_responds(client):
    response = client.post("/chat", json={"question": "How many paid leaves do I get?"})
    assert response.status_code == 200
    assert response.json()["sources"] == []


def test_chat_rejects_empty_question(client):
    response = client.post("/chat", json={"question": "   "})
    assert response.status_code == 400


def test_full_pipeline_upload_then_chat_returns_grounded_answer_and_sources(client):
    pdf_bytes = _make_pdf_bytes(
        [
            "Employees receive 24 paid leaves per year.",
            "Standard working hours are 9 AM to 6 PM.",
        ]
    )
    upload = client.post(
        "/documents/upload", files={"file": ("handbook.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    )
    assert upload.status_code == 200

    chat = client.post("/chat", json={"question": "How many paid leaves do employees get?"})
    assert chat.status_code == 200
    body = chat.json()

    assert "leave" in body["answer"].lower() or "24" in body["answer"]
    assert any(s["filename"] == "handbook.pdf" for s in body["sources"])
    # The retrieved leave-policy chunk (page 1), not the working-hours chunk (page 2), should be cited first.
    assert body["sources"][0]["page"] == 1
