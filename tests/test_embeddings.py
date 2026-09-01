import pytest

from app.services.embeddings import EmbeddingProvider, EmbeddingService, OpenAIEmbeddingProvider


class FakeProvider(EmbeddingProvider):
    """
    Deterministic stand-in for a real embedding API: returns a fixed-size
    vector derived from each text's length. Lets us test EmbeddingService's
    own logic (batching, unwrapping) without any network call, matching
    how the vector store and retriever tests will also avoid real API
    calls later.
    """

    def __init__(self, dimensions: int = 4):
        self.dimensions = dimensions
        self.calls: list[list[str]] = []

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        return [[float(len(t))] * self.dimensions for t in texts]


def test_embed_text_returns_a_single_vector():
    service = EmbeddingService(provider=FakeProvider(dimensions=3))
    vector = service.embed_text("hello")
    assert vector == [5.0, 5.0, 5.0]


def test_embed_documents_returns_one_vector_per_input_in_order():
    service = EmbeddingService(provider=FakeProvider(dimensions=2))
    vectors = service.embed_documents(["ab", "abcd"])
    assert vectors == [[2.0, 2.0], [4.0, 4.0]]


def test_embed_documents_with_empty_list_makes_no_provider_call():
    provider = FakeProvider()
    service = EmbeddingService(provider=provider)
    assert service.embed_documents([]) == []
    assert provider.calls == []


def test_embed_documents_batches_in_a_single_provider_call():
    provider = FakeProvider()
    service = EmbeddingService(provider=provider)
    service.embed_documents(["a", "b", "c"])
    assert len(provider.calls) == 1
    assert provider.calls[0] == ["a", "b", "c"]


def test_openai_provider_requires_an_api_key():
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        OpenAIEmbeddingProvider(api_key="", model="text-embedding-3-small")
