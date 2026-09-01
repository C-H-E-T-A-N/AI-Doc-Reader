"""
FastAPI dependency providers.

Routes receive services via `Depends(get_x)` rather than constructing
them directly. Two reasons this matters, not just style:

1. Services that need an API key (EmbeddingService, LLMService) are
   only constructed the first time a request actually needs them --
   not at import time -- so the app can still start and serve
   /health even if a key is missing from .env. The clear ValueError
   from Stage 4/7 fires on first use, not on startup.
2. Tests can swap these for fakes via FastAPI's
   `app.dependency_overrides`, without touching route code or hitting
   a real API.

@lru_cache makes each provider a singleton: the same EmbeddingService/
VectorStore instance is reused across requests, matching how a real
deployment would hold one client/connection rather than reconnecting
per request.
"""

from functools import lru_cache

from fastapi import Depends

from app.services.embeddings import EmbeddingService
from app.services.llm import LLMService
from app.services.retriever import Retriever
from app.services.vector_store import VectorStore


@lru_cache
def get_embedding_service() -> EmbeddingService:
    return EmbeddingService()


@lru_cache
def get_vector_store() -> VectorStore:
    return VectorStore()


@lru_cache
def get_llm_service() -> LLMService:
    return LLMService()


def get_retriever(
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    vector_store: VectorStore = Depends(get_vector_store),
) -> Retriever:
    # get_embedding_service/get_vector_store MUST be routed through
    # Depends(...) here, not called directly -- a direct call bypasses
    # FastAPI's dependency resolution entirely, which means
    # app.dependency_overrides for them would silently have no effect
    # on any route that depends on get_retriever. (Found by testing:
    # overriding get_embedding_service alone didn't stop /chat from
    # trying to construct a real OpenAI client.)
    return Retriever(embedding_service=embedding_service, vector_store=vector_store)
