"""
Text -> vector, via a real embedding model (OpenAI by default, Gemini
as an alternative -- see settings.embedding_provider).

See the hand-rolled cosine-similarity demo run alongside this stage for
the concept in isolation. The short version: a trained embedding model
maps text to a fixed-length vector such that texts with similar
*meaning* end up as vectors pointing in similar *directions* -- even
when they share no words -- which is exactly what naive word-counting
cannot do.

Provider abstraction
---------------------
`EmbeddingProvider` is the only place a provider SDK (`openai` or
`google.genai`) is imported. Everything else in this app talks to
`EmbeddingService`, which doesn't know or care which provider is behind
it. Adding GeminiEmbeddingProvider below required zero changes to
routes, the chunker, the vector store, or existing tests -- that's the
actual point of the abstraction, not just a design nicety. This is the
same "one seam, swap the implementation" pattern used for the LLM
service.
"""

import time
from abc import ABC, abstractmethod

import openai
from google import genai
from google.genai import errors as genai_errors
from openai import OpenAI

from app.config import settings
from app.services.exceptions import ConfigurationError


class EmbeddingGenerationError(Exception):
    """Raised when the embedding provider fails (network, rate limit, auth, bad request, ...)."""


class EmbeddingProvider(ABC):
    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one vector per input text, in the same order."""


class OpenAIEmbeddingProvider(EmbeddingProvider):
    def __init__(self, api_key: str, model: str):
        if not api_key:
            raise ConfigurationError(
                "OPENAI_API_KEY is not set. Embeddings require it -- add it to your .env file."
            )
        self._client = OpenAI(api_key=api_key)
        self._model = model

    def embed(self, texts: list[str]) -> list[list[float]]:
        # One API call for the whole batch, not one call per text --
        # this matters at ingestion time when a document can produce
        # hundreds of chunks. The API guarantees the response order
        # matches the input order.
        try:
            response = self._client.embeddings.create(model=self._model, input=texts)
        except openai.OpenAIError as e:
            # Covers connection errors, rate limits, auth failures, bad
            # requests, etc. -- all provider-side failures collapse to
            # one type the route layer can handle uniformly.
            raise EmbeddingGenerationError(f"Embedding request failed: {e}") from e
        return [item.embedding for item in response.data]


class GeminiEmbeddingProvider(EmbeddingProvider):
    # Gemini's batchEmbedContents rejects any request with more than 100
    # items ("at most 100 requests can be in one batch"). A single
    # document routinely produces more chunks than that, so split the
    # batch and stitch the results back together in input order.
    _MAX_BATCH = 100

    # The free tier meters embedding calls per minute per base model and
    # answers a burst with 429 RESOURCE_EXHAUSTED. Pause briefly between
    # sub-batches, and retry a rejected batch a few times with a longer
    # wait, so ingesting one multi-hundred-chunk document doesn't fail
    # outright on a transient quota bump.
    _INTER_BATCH_PAUSE_S = 1.0
    _MAX_RETRIES = 4
    _RETRY_WAIT_S = 30.0

    def __init__(self, api_key: str, model: str):
        if not api_key:
            raise ConfigurationError(
                "GEMINI_API_KEY is not set. Embeddings require it -- add it to your .env file."
            )
        self._client = genai.Client(api_key=api_key)
        self._model = model

    def _embed_batch(self, batch: list[str]) -> list[list[float]]:
        for attempt in range(self._MAX_RETRIES + 1):
            try:
                response = self._client.models.embed_content(model=self._model, contents=batch)
                return [embedding.values for embedding in response.embeddings]
            except genai_errors.APIError as e:
                is_rate_limit = getattr(e, "code", None) == 429
                if is_rate_limit and attempt < self._MAX_RETRIES:
                    time.sleep(self._RETRY_WAIT_S)
                    continue
                raise EmbeddingGenerationError(f"Embedding request failed: {e}") from e
        raise EmbeddingGenerationError("Embedding request failed: retries exhausted")

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self._MAX_BATCH):
            if start > 0:
                time.sleep(self._INTER_BATCH_PAUSE_S)
            batch = texts[start : start + self._MAX_BATCH]
            vectors.extend(self._embed_batch(batch))
        return vectors


def _default_embedding_provider() -> EmbeddingProvider:
    if settings.embedding_provider == "gemini":
        return GeminiEmbeddingProvider(api_key=settings.gemini_api_key, model=settings.gemini_embedding_model)
    return OpenAIEmbeddingProvider(api_key=settings.openai_api_key, model=settings.embedding_model)


class EmbeddingService:
    """
    The interface the rest of the app uses.

    Two methods because the two call sites have different shapes:
    - embed_documents(): many chunks at once, during ingestion.
    - embed_text(): a single query, at question-answering time.
    Both ultimately call the same provider.embed(); embed_text() is a
    convenience wrapper that unwraps the single-item batch result.
    """

    def __init__(self, provider: EmbeddingProvider | None = None):
        self._provider = provider or _default_embedding_provider()

    def embed_text(self, text: str) -> list[float]:
        return self._provider.embed([text])[0]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return self._provider.embed(texts)
