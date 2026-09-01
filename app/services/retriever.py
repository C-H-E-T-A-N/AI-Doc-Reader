"""
Retrieval: question -> query embedding -> vector search -> top-k chunks.

This module is deliberately thin -- it composes two services that
already do the real work (EmbeddingService, VectorStore) rather than
reimplementing anything. What it adds is the *shape* of a retrieval
result (RetrievedChunk) that the rest of the app (prompt construction,
the /chat response's "sources") depends on.

What top_k controls
---------------------
top_k is how many chunks get retrieved and handed to the LLM as
context.

Too low (e.g. top_k=1): if the answer spans two chunks -- common even
with chunk overlap, since a question can need information from two
different sections -- the single retrieved chunk may not contain
everything needed. The LLM then either hallucinates the missing piece,
or wrongly says "not found" even though the document did contain the
answer somewhere.

Too high (e.g. top_k=20): irrelevant chunks get stuffed into the prompt
alongside the relevant ones. This costs money and latency (more tokens
sent to the LLM) and can hurt answer quality -- "context dilution",
where the LLM has to find the signal in more noise.

There's no universally correct value; top_k=3-5 is a reasonable
starting point for short, focused documents. Stage 11 (evaluation)
exists to tune this empirically rather than guess at it.
"""

from dataclasses import dataclass

from app.services.embeddings import EmbeddingService
from app.services.vector_store import VectorStore


@dataclass
class RetrievedChunk:
    text: str
    score: float
    metadata: dict


class Retriever:
    def __init__(self, embedding_service: EmbeddingService, vector_store: VectorStore):
        self._embeddings = embedding_service
        self._vector_store = vector_store

    def retrieve(
        self,
        query: str,
        top_k: int,
        document_id: str | None = None,
    ) -> list[RetrievedChunk]:
        query_embedding = self._embeddings.embed_text(query)
        where = {"document_id": document_id} if document_id else None
        results = self._vector_store.similarity_search(query_embedding, top_k=top_k, where=where)
        return [RetrievedChunk(text=r["text"], score=r["score"], metadata=r["metadata"]) for r in results]
