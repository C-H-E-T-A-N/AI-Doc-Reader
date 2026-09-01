"""
Text -> vector, via a real embedding model (OpenAI's text-embedding-3-small).

See the hand-rolled cosine-similarity demo run alongside this stage for
the concept in isolation. The short version: a trained embedding model
maps text to a fixed-length vector such that texts with similar
*meaning* end up as vectors pointing in similar *directions* -- even
when they share no words -- which is exactly what naive word-counting
cannot do.

Provider abstraction
---------------------
`EmbeddingProvider` is the only place the `openai` SDK is imported.
Everything else in this app talks to `EmbeddingService`, which doesn't
know or care which provider is behind it. If we later swap to a
different embedding API (or a local model), only this file changes --
routes, the chunker, the vector store, and tests referencing
EmbeddingService stay untouched. This is the same "one seam, swap the
implementation" pattern used for the LLM service later.
"""

from abc import ABC, abstractmethod

import openai
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
        self._provider = provider or OpenAIEmbeddingProvider(
            api_key=settings.openai_api_key,
            model=settings.embedding_model,
        )

    def embed_text(self, text: str) -> list[float]:
        return self._provider.embed([text])[0]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return self._provider.embed(texts)
