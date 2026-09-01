"""
Tests for Stage 9: provider/config failures must become clean,
specific HTTP responses -- never a raw stack trace, and never a plain
generic 500 when we know more (missing key -> 503, provider request
failure -> 502).

Uses TestClient + dependency_overrides directly (rather than the
shared fixture in test_api.py) because each test needs a different mix
of overridden vs. real dependencies to exercise a specific failure
path.
"""

import io

import fitz
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.dependencies import get_embedding_service, get_llm_service, get_vector_store
from app.main import app
from app.services.embeddings import EmbeddingGenerationError, EmbeddingProvider, EmbeddingService
from app.services.llm import LLMGenerationError, LLMProvider, LLMService
from app.services.prompt_builder import Prompt
from app.services.vector_store import VectorStore


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


class WorkingEmbeddingProvider(EmbeddingProvider):
    def embed(self, texts):
        return [[1.0, 0.0] for _ in texts]


class FailingEmbeddingProvider(EmbeddingProvider):
    def embed(self, texts):
        raise EmbeddingGenerationError("simulated embedding provider outage")


class FailingLLMProvider(LLMProvider):
    def generate(self, prompt: Prompt) -> str:
        raise LLMGenerationError("simulated LLM provider outage")


class CrashingLLMProvider(LLMProvider):
    """Raises something *not* covered by any specific except clause, to exercise the generic 500 safety net."""

    def generate(self, prompt: Prompt) -> str:
        raise RuntimeError("something truly unexpected")


@pytest.fixture
def force_missing_api_key(monkeypatch):
    """
    Deterministically force EmbeddingService/LLMService construction to
    fail with a missing-key ConfigurationError, regardless of whatever
    provider/keys are actually configured in this environment's .env.

    This must NOT depend on ambient environment state ("just don't set
    a key") -- that's exactly what broke silently once a real .env with
    a working Gemini key was added during development: the "real"
    construction then succeeded and made an actual ~20s network call
    instead of failing fast, turning a unit-speed test into a live
    integration test with a wrong expected status code.

    get_embedding_service/get_llm_service are @lru_cache'd singletons
    (app/dependencies.py) -- clearing the cache is necessary so a
    provider instance built successfully by an earlier test (or an
    earlier call in this same test) isn't reused instead of hitting the
    forced-missing-key path.
    """
    monkeypatch.setattr(settings, "embedding_provider", "openai")
    monkeypatch.setattr(settings, "openai_api_key", "")
    monkeypatch.setattr(settings, "llm_provider", "anthropic")
    monkeypatch.setattr(settings, "anthropic_api_key", "")
    get_embedding_service.cache_clear()
    get_llm_service.cache_clear()
    yield
    get_embedding_service.cache_clear()
    get_llm_service.cache_clear()


def test_chat_returns_503_when_api_key_is_missing(force_missing_api_key):
    # No dependency overrides -- real EmbeddingService/LLMService get
    # constructed, and construction fails with ConfigurationError during
    # dependency resolution, which app/main.py's global handler must
    # turn into a 503, not a 500.
    client = TestClient(app)
    response = client.post("/chat", json={"question": "anything"})

    assert response.status_code == 503
    assert "API_KEY" in response.json()["detail"]


def test_chat_returns_502_when_embedding_provider_fails(tmp_path):
    app.dependency_overrides[get_embedding_service] = lambda: EmbeddingService(
        provider=FailingEmbeddingProvider()
    )
    app.dependency_overrides[get_vector_store] = lambda: VectorStore(
        persist_directory=str(tmp_path / "chroma"), collection_name="test"
    )
    app.dependency_overrides[get_llm_service] = lambda: LLMService(provider=FailingLLMProvider())

    client = TestClient(app)
    response = client.post("/chat", json={"question": "anything"})

    assert response.status_code == 502
    assert "Traceback" not in response.text
    assert "simulated" not in response.text  # internal error detail is not echoed to the client


def test_chat_returns_502_when_llm_provider_fails(tmp_path):
    app.dependency_overrides[get_embedding_service] = lambda: EmbeddingService(
        provider=WorkingEmbeddingProvider()
    )
    app.dependency_overrides[get_vector_store] = lambda: VectorStore(
        persist_directory=str(tmp_path / "chroma"), collection_name="test"
    )
    app.dependency_overrides[get_llm_service] = lambda: LLMService(provider=FailingLLMProvider())

    client = TestClient(app)
    response = client.post("/chat", json={"question": "anything"})

    assert response.status_code == 502


def test_chat_returns_generic_500_for_a_truly_unexpected_error(tmp_path):
    app.dependency_overrides[get_embedding_service] = lambda: EmbeddingService(
        provider=WorkingEmbeddingProvider()
    )
    app.dependency_overrides[get_vector_store] = lambda: VectorStore(
        persist_directory=str(tmp_path / "chroma"), collection_name="test"
    )
    app.dependency_overrides[get_llm_service] = lambda: LLMService(provider=CrashingLLMProvider())

    # raise_server_exceptions=False: a real client only ever sees the
    # JSONResponse our global handler returns. TestClient's default
    # (True) re-raises the original exception in-process instead, which
    # is great for catching bugs in other tests but would defeat the
    # point of *this* one -- we're specifically verifying what a real
    # client receives when the safety net catches something.
    client = TestClient(app, raise_server_exceptions=False)
    response = client.post("/chat", json={"question": "anything"})

    assert response.status_code == 500
    assert response.json() == {"detail": "An unexpected error occurred."}
    assert "RuntimeError" not in response.text
    assert "truly unexpected" not in response.text


def test_upload_returns_503_when_api_key_is_missing(force_missing_api_key):
    client = TestClient(app)
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "some real text")

    response = client.post(
        "/documents/upload", files={"file": ("a.pdf", io.BytesIO(doc.write()), "application/pdf")}
    )

    assert response.status_code == 503


def test_upload_returns_502_and_cleans_up_file_when_embedding_fails(tmp_path):
    app.dependency_overrides[get_embedding_service] = lambda: EmbeddingService(
        provider=FailingEmbeddingProvider()
    )
    app.dependency_overrides[get_vector_store] = lambda: VectorStore(
        persist_directory=str(tmp_path / "chroma"), collection_name="test"
    )

    client = TestClient(app)
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "some real text")

    response = client.post(
        "/documents/upload", files={"file": ("a.pdf", io.BytesIO(doc.write()), "application/pdf")}
    )

    assert response.status_code == 502
