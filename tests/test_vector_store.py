import pytest

from app.services.chunker import Chunk
from app.services.vector_store import VectorStore


@pytest.fixture
def store(tmp_path):
    # Each test gets its own on-disk directory so tests never see each
    # other's data and nothing is left behind in the project's real
    # vector_db/ directory.
    return VectorStore(persist_directory=str(tmp_path / "chroma"), collection_name="test")


def _chunk(text, page_number=1, chunk_index=0):
    return Chunk(text=text, page_number=page_number, chunk_index=chunk_index)


def test_empty_store_returns_no_results(store):
    assert store.count() == 0
    assert store.similarity_search([1.0, 0.0], top_k=5) == []


def test_add_chunks_requires_matching_lengths(store):
    with pytest.raises(ValueError):
        store.add_chunks(
            document_id="doc1",
            filename="a.pdf",
            chunks=[_chunk("a"), _chunk("b")],
            embeddings=[[1.0, 0.0]],
        )


def test_add_chunks_with_empty_list_is_a_noop(store):
    store.add_chunks(document_id="doc1", filename="a.pdf", chunks=[], embeddings=[])
    assert store.count() == 0


def test_similarity_search_ranks_the_closer_vector_first(store):
    store.add_chunks(
        document_id="doc1",
        filename="handbook.pdf",
        chunks=[
            _chunk("leave policy text", chunk_index=0),
            _chunk("unrelated dress code text", chunk_index=1),
        ],
        embeddings=[[1.0, 0.0], [0.0, 1.0]],
    )

    results = store.similarity_search([0.9, 0.1], top_k=2)

    assert len(results) == 2
    assert results[0]["text"] == "leave policy text"
    assert results[0]["score"] > results[1]["score"]


def test_similarity_search_result_includes_metadata(store):
    store.add_chunks(
        document_id="doc1",
        filename="handbook.pdf",
        chunks=[_chunk("some text", page_number=5, chunk_index=3)],
        embeddings=[[1.0, 0.0]],
    )

    result = store.similarity_search([1.0, 0.0], top_k=1)[0]

    assert result["metadata"]["document_id"] == "doc1"
    assert result["metadata"]["filename"] == "handbook.pdf"
    assert result["metadata"]["page_number"] == 5
    assert result["metadata"]["chunk_index"] == 3


def test_similarity_search_caps_results_at_available_chunk_count(store):
    store.add_chunks(
        document_id="doc1",
        filename="a.pdf",
        chunks=[_chunk("only chunk")],
        embeddings=[[1.0, 0.0]],
    )

    # top_k asks for more results than exist -- must not error.
    results = store.similarity_search([1.0, 0.0], top_k=10)
    assert len(results) == 1


def test_delete_document_removes_only_that_documents_chunks(store):
    store.add_chunks(
        document_id="doc1",
        filename="a.pdf",
        chunks=[_chunk("doc1 chunk")],
        embeddings=[[1.0, 0.0]],
    )
    store.add_chunks(
        document_id="doc2",
        filename="b.pdf",
        chunks=[_chunk("doc2 chunk")],
        embeddings=[[0.0, 1.0]],
    )

    store.delete_document("doc1")

    assert store.count() == 1
    remaining = store.similarity_search([0.0, 1.0], top_k=1)[0]
    assert remaining["metadata"]["document_id"] == "doc2"
