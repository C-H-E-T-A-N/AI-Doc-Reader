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

from app.config import settings
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
def client(tmp_path, monkeypatch):
    vector_store = VectorStore(persist_directory=str(tmp_path / "chroma"), collection_name="test")

    # Isolate on-disk artifacts: uploaded files land in tmp_path/uploads
    # and the document registry sidecar in tmp_path/registry.json,
    # instead of the project's real data/ directory.
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))

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
    assert body["status"] == "indexed"
    assert body["file_type"] == "pdf"
    assert body["size_bytes"] > 0
    assert body["uploaded_at"]


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


def _upload_pdf(client, pages, filename):
    resp = client.post(
        "/documents/upload",
        files={"file": (filename, io.BytesIO(_make_pdf_bytes(pages)), "application/pdf")},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_documents_listing_reflects_uploads_and_deletes(client):
    assert client.get("/documents").json() == []

    a = _upload_pdf(client, ["Leave policy: 24 paid leaves."], "a.pdf")
    b = _upload_pdf(client, ["Dress code: business casual."], "b.pdf")

    listing = client.get("/documents").json()
    assert {d["document_id"] for d in listing} == {a["document_id"], b["document_id"]}
    assert all(d["status"] == "indexed" and d["chunks"] >= 1 for d in listing)

    # Single-document fetch.
    one = client.get(f"/documents/{a['document_id']}")
    assert one.status_code == 200
    assert one.json()["filename"] == "a.pdf"

    deleted = client.delete(f"/documents/{a['document_id']}")
    assert deleted.status_code == 200
    remaining = client.get("/documents").json()
    assert [d["document_id"] for d in remaining] == [b["document_id"]]

    # Deleting again is a clean 404, not a 500.
    assert client.delete(f"/documents/{a['document_id']}").status_code == 404
    assert client.get(f"/documents/{a['document_id']}").status_code == 404


def test_chat_scoped_to_document_only_searches_that_document(client):
    leave_doc = _upload_pdf(client, ["Employees receive 24 paid leaves per year."], "leave.pdf")
    dress_doc = _upload_pdf(client, ["The dress code is business casual on weekdays."], "dress.pdf")

    scoped = client.post(
        "/chat", json={"question": "How many paid leaves?", "document_id": leave_doc["document_id"]}
    )
    assert scoped.status_code == 200
    sources = scoped.json()["sources"]
    assert sources and all(s["filename"] == "leave.pdf" for s in sources)

    # Scoping to the other document must not surface the leave chunk.
    other = client.post(
        "/chat", json={"question": "How many paid leaves?", "document_id": dress_doc["document_id"]}
    )
    assert all(s["filename"] != "leave.pdf" for s in other.json()["sources"])


def test_chat_sources_include_passage_text_and_score(client):
    _upload_pdf(client, ["Employees receive 24 paid leaves per year."], "handbook.pdf")
    body = client.post("/chat", json={"question": "How many paid leaves do employees get?"}).json()

    assert body["sources"], "expected at least one source"
    top = body["sources"][0]
    assert top["text"] and "leave" in top["text"].lower()
    assert isinstance(top["score"], (int, float))


def test_document_file_is_served_and_removed_with_the_document(client):
    doc = _upload_pdf(client, ["Employees receive 24 paid leaves per year."], "handbook.pdf")

    file_resp = client.get(f"/documents/{doc['document_id']}/file")
    assert file_resp.status_code == 200
    assert file_resp.headers["content-type"] == "application/pdf"
    assert file_resp.content[:4] == b"%PDF"

    client.delete(f"/documents/{doc['document_id']}")
    assert client.get(f"/documents/{doc['document_id']}/file").status_code == 404
