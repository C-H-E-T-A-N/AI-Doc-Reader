"""
Vector database: where chunk text + its embedding + metadata live.

What's actually being stored
------------------------------
Document -> Chunks (Stage 3) -> each chunk turned into a vector by the
embedding model (Stage 4) -> the vector DB stores, per chunk: the
vector itself, the original chunk text (the vector alone is useless
once we need to hand real text to the LLM later), and metadata
(document_id, filename, page_number, chunk_index) so a matched chunk
can be traced back to its source.

A vector database is not a black box that "understands" documents.
It's a specialized index over (vector, text, metadata) triples,
optimized for one operation: given a query vector, find the N stored
vectors closest to it, fast.

How similarity search works internally (high level)
------------------------------------------------------
Naively: compare the query vector against every stored vector with
cosine similarity, sort, take the top K. Exact, but O(n) per query --
fine for a few thousand chunks, too slow at millions.

ChromaDB instead builds an Approximate Nearest Neighbor index -- by
default HNSW (Hierarchical Navigable Small World graphs): vectors are
organized into a multi-layer graph where each vector links to a handful
of "nearby" vectors. A search greedily hops through the graph toward
the query vector's neighborhood instead of visiting every stored
vector, roughly O(log n) instead of O(n) -- trading a small amount of
exactness (it might occasionally miss the single truest best match) for
a large speedup at scale. This is the same mechanism production vector
databases (Pinecone, Weaviate, pgvector w/ HNSW) run on internally.
"""

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.config import settings
from app.services.chunker import Chunk


class VectorStoreError(Exception):
    """Raised when a ChromaDB operation fails (disk I/O, corruption, internal errors, ...)."""


class VectorStore:
    def __init__(self, persist_directory: str | None = None, collection_name: str | None = None):
        self._client = chromadb.PersistentClient(
            path=persist_directory or settings.vector_db_dir,
            # Chroma phones home anonymized usage stats by default; we
            # don't want that for a local learning project.
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=collection_name or settings.chroma_collection_name,
            # Explicit, not Chroma's default (squared L2): our EmbeddingService
            # is compared elsewhere using cosine similarity, so the vector
            # store's notion of "close" must match.
            metadata={"hnsw:space": "cosine"},
        )

    def add_chunks(
        self,
        document_id: str,
        filename: str,
        chunks: list[Chunk],
        embeddings: list[list[float]],
    ) -> None:
        if not chunks:
            return
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings must be the same length")

        # id format "<document_id>:<chunk_index>" keeps ids unique across
        # documents and human-readable, without needing a separate id
        # generator or extra bookkeeping.
        ids = [f"{document_id}:{c.chunk_index}" for c in chunks]
        documents = [c.text for c in chunks]
        metadatas = [
            {
                "document_id": document_id,
                "filename": filename,
                "page_number": c.page_number,
                "chunk_index": c.chunk_index,
            }
            for c in chunks
        ]
        try:
            self._collection.add(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)
        except Exception as e:
            raise VectorStoreError(f"Failed to store chunks in the vector database: {e}") from e

    def similarity_search(self, query_embedding: list[float], top_k: int) -> list[dict]:
        """Return up to top_k chunks closest to query_embedding, best match first."""
        try:
            count = self._collection.count()
            if count == 0:
                return []
            results = self._collection.query(
                query_embeddings=[query_embedding],
                n_results=min(top_k, count),
            )
        except Exception as e:
            raise VectorStoreError(f"Vector search failed: {e}") from e

        matches = []
        for id_, text, metadata, distance in zip(
            results["ids"][0], results["documents"][0], results["metadatas"][0], results["distances"][0]
        ):
            # Chroma returns cosine *distance* (0 = identical, 2 = opposite
            # direction); convert to the more intuitive cosine
            # *similarity* (1 = identical, -1 = opposite) used everywhere
            # else in this project.
            matches.append(
                {
                    "id": id_,
                    "text": text,
                    "score": 1 - distance,
                    "metadata": metadata,
                }
            )
        return matches

    def delete_document(self, document_id: str) -> None:
        try:
            self._collection.delete(where={"document_id": document_id})
        except Exception as e:
            raise VectorStoreError(f"Failed to delete document {document_id!r}: {e}") from e

    def count(self) -> int:
        return self._collection.count()
