from app.services.chunker import Chunk
from app.services.embeddings import EmbeddingProvider, EmbeddingService
from app.services.retriever import Retriever
from app.services.vector_store import VectorStore


class FakeEmbeddingProvider(EmbeddingProvider):
    """
    Maps specific known input texts to hand-picked vectors, so a test
    can control the geometry precisely -- unlike a length-derived fake,
    this lets us assert *which* chunk should rank first.
    """

    def __init__(self, mapping: dict[str, list[float]]):
        self._mapping = mapping

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._mapping[t] for t in texts]


def _build_store(tmp_path):
    store = VectorStore(persist_directory=str(tmp_path / "chroma"), collection_name="test")
    store.add_chunks(
        document_id="doc1",
        filename="handbook.pdf",
        chunks=[
            Chunk(text="leave policy chunk", page_number=1, chunk_index=0),
            Chunk(text="dress code chunk", page_number=3, chunk_index=1),
        ],
        embeddings=[[1.0, 0.0], [0.0, 1.0]],
    )
    return store


def test_retrieve_ranks_the_semantically_closer_chunk_first(tmp_path):
    store = _build_store(tmp_path)
    query = "how many leaves do I get?"
    provider = FakeEmbeddingProvider({query: [0.9, 0.1]})
    retriever = Retriever(embedding_service=EmbeddingService(provider=provider), vector_store=store)

    results = retriever.retrieve(query, top_k=2)

    assert len(results) == 2
    assert results[0].text == "leave policy chunk"
    assert results[0].score > results[1].score


def test_retrieve_respects_top_k(tmp_path):
    store = _build_store(tmp_path)
    query = "anything"
    provider = FakeEmbeddingProvider({query: [0.5, 0.5]})
    retriever = Retriever(embedding_service=EmbeddingService(provider=provider), vector_store=store)

    results = retriever.retrieve(query, top_k=1)

    assert len(results) == 1


def test_retrieve_includes_metadata_for_citation(tmp_path):
    store = _build_store(tmp_path)
    query = "dress code question"
    provider = FakeEmbeddingProvider({query: [0.1, 0.9]})
    retriever = Retriever(embedding_service=EmbeddingService(provider=provider), vector_store=store)

    results = retriever.retrieve(query, top_k=1)

    assert results[0].metadata["filename"] == "handbook.pdf"
    assert results[0].metadata["page_number"] == 3


def test_retrieve_against_empty_store_returns_no_chunks(tmp_path):
    store = VectorStore(persist_directory=str(tmp_path / "chroma"), collection_name="empty")
    query = "anything"
    provider = FakeEmbeddingProvider({query: [1.0, 0.0]})
    retriever = Retriever(embedding_service=EmbeddingService(provider=provider), vector_store=store)

    assert retriever.retrieve(query, top_k=5) == []
