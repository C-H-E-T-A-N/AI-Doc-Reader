"""
RAG-specific tests.

Standard API tests (test_api.py) check the *contract*: does the
endpoint return the right status code and response shape. These tests
check something different and arguably more important: does the
system actually do what RAG is supposed to do -- retrieve the
genuinely relevant chunk, cite the right source, and refuse to
fabricate an answer when the retrieved context doesn't actually
contain it. A /chat call can return a perfectly well-formed 200 with a
confidently wrong answer; these tests are what would catch that.

To make this testable without a real embedding API, BagOfWordsFakeEmbeddingProvider
computes a real (if crude) multi-dimensional cosine-similarity vector
over a small fixed vocabulary -- closer in spirit to how a real
embedding model behaves than a single-keyword flag would be, since it
captures *degree* of word overlap, not just presence/absence.

KeywordAwareFakeLLM simulates a well-grounded LLM deterministically: it
only answers when the specific fact's required keywords are actually
present in the CONTEXT section of the prompt it received, mirroring
what the Stage 7 system prompt instructs a real LLM to do. This lets
these tests assert on END-TO-END grounding -- did retrieval actually
put the right text in front of the model -- without a real API call.
"""

import io

import fitz
import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_embedding_service, get_llm_service, get_vector_store
from app.main import app
from app.services.embeddings import EmbeddingProvider, EmbeddingService
from app.services.llm import LLMProvider, LLMService
from app.services.prompt_builder import Prompt
from app.services.vector_store import VectorStore

VOCAB = [
    "paid", "leave", "leaves", "sick", "doctor", "note", "days",
    "wifi", "password", "router", "label",
    "dress", "code", "hour", "hours", "reset", "january",
]


def _bow_vector(text: str) -> list[float]:
    words = {w.strip(".,?'\"").lower() for w in text.split()}
    return [1.0 if v in words else 0.0 for v in VOCAB]


class BagOfWordsFakeEmbeddingProvider(EmbeddingProvider):
    def embed(self, texts: list[str]) -> list[list[float]]:
        return [_bow_vector(t) for t in texts]


class KeywordAwareFakeLLM(LLMProvider):
    """
    A fact only fires if BOTH the question is actually asking about it
    AND the retrieved context actually supports it. Checking context
    alone was tried first and is wrong: with only one document in the
    store, its content is always present in context regardless of
    what's asked, so a context-only check would "answer" any question
    using whatever happens to be indexed -- exactly the kind of
    ungrounded behavior these tests exist to catch. A real LLM uses the
    question to decide what's being asked; this fake must too.
    """

    NOT_FOUND = "The provided documents do not contain this information."

    def __init__(self, facts: list[tuple[list[str], list[str], str]]):
        # facts: [(question_keywords, context_keywords, answer), ...]
        self._facts = facts

    def generate(self, prompt: Prompt) -> str:
        context, _, question = prompt.user.partition("QUESTION:")
        context, question = context.lower(), question.lower()
        for question_keywords, context_keywords, answer in self._facts:
            if all(kw.lower() in question for kw in question_keywords) and all(
                kw.lower() in context for kw in context_keywords
            ):
                return answer
        return self.NOT_FOUND


@pytest.fixture
def client(tmp_path):
    vector_store = VectorStore(persist_directory=str(tmp_path / "chroma"), collection_name="test")
    app.dependency_overrides[get_embedding_service] = lambda: EmbeddingService(
        provider=BagOfWordsFakeEmbeddingProvider()
    )
    app.dependency_overrides[get_vector_store] = lambda: vector_store
    yield TestClient(app)
    app.dependency_overrides.clear()


def _set_llm(facts: list[tuple[list[str], list[str], str]]) -> None:
    app.dependency_overrides[get_llm_service] = lambda: LLMService(provider=KeywordAwareFakeLLM(facts))


def _upload(client, pages_text: list[str], filename: str):
    doc = fitz.open()
    for text in pages_text:
        page = doc.new_page()
        page.insert_text((72, 72), text)
    response = client.post(
        "/documents/upload", files={"file": (filename, io.BytesIO(doc.write()), "application/pdf")}
    )
    assert response.status_code == 200, response.text
    return response.json()


# 1. Question whose answer exists.
def test_question_with_an_existing_answer_is_answered_and_cited(client):
    _upload(client, ["Employees receive 24 paid leaves per year."], "handbook.pdf")
    _set_llm([(["paid", "leaves"], ["paid", "leaves"], "Employees are entitled to 24 paid leaves per year.")])

    response = client.post("/chat", json={"question": "How many paid leaves do employees get?"})
    body = response.json()

    assert response.status_code == 200
    assert body["answer"] == "Employees are entitled to 24 paid leaves per year."
    assert body["sources"] == [{"filename": "handbook.pdf", "page": 1}]


# 2. Question whose answer does not exist.
def test_question_with_no_answer_in_any_document_is_refused_not_fabricated(client):
    _upload(client, ["Employees receive 24 paid leaves per year."], "handbook.pdf")
    # No fact is defined for "wifi"/"password" -- nothing in the corpus
    # mentions it, so a well-grounded LLM must refuse.
    _set_llm([(["paid", "leaves"], ["paid", "leaves"], "Employees are entitled to 24 paid leaves per year.")])

    response = client.post("/chat", json={"question": "What is the wifi password?"})
    body = response.json()

    assert response.status_code == 200
    assert body["answer"] == KeywordAwareFakeLLM.NOT_FOUND
    # Worth noting: retrieval still returns the leave-policy chunk as
    # the "closest" match, because similarity_search has no minimum
    # score threshold -- it always returns up to top_k results, however
    # weak the match. The grounding safety net here is the LLM
    # (correctly, per the Stage 7 system prompt) refusing to use
    # irrelevant context, not retrieval filtering it out. Adding a
    # relevance threshold is a Phase 2 improvement, not implemented yet.
    assert len(body["sources"]) >= 1


# 3. Similar but incorrect context.
def test_topically_similar_but_non_answering_context_is_not_used_to_fabricate(client):
    _upload(
        client,
        [
            "Employees receive 24 paid leaves per year.",
            "Sick leave requires a doctor's note after 3 consecutive days.",
        ],
        "handbook.pdf",
    )
    # The question IS about sick leaves (question_keywords match), but
    # the corpus never states a specific number -- only a doctor's-note
    # requirement. The context_keywords ("10") never appear, so even
    # though a topically related chunk gets retrieved, the LLM must not
    # invent a number.
    _set_llm([(["sick", "leaves"], ["10"], "You get 10 sick leaves.")])

    response = client.post("/chat", json={"question": "How many sick leaves are employees allowed?"})
    body = response.json()

    assert response.status_code == 200
    assert body["answer"] == KeywordAwareFakeLLM.NOT_FOUND


# 4. Multiple documents.
def test_retrieval_finds_the_right_chunk_across_multiple_documents(client):
    _upload(client, ["Employees receive 24 paid leaves per year."], "handbook.pdf")
    _upload(client, ["The office WiFi password is printed on the router label."], "it_policy.pdf")
    _set_llm([(["wifi", "password"], ["wifi", "password"], "It's printed on the router label.")])

    response = client.post("/chat", json={"question": "What is the wifi password?"})
    body = response.json()

    assert response.status_code == 200
    assert body["answer"] == "It's printed on the router label."
    filenames = {s["filename"] for s in body["sources"]}
    assert "it_policy.pdf" in filenames


# 5. Multiple relevant chunks.
def test_answer_can_be_assembled_from_multiple_retrieved_chunks(client):
    _upload(
        client,
        [
            "Employees receive 24 paid leaves per year.",
            "Leaves reset every January 1st.",
        ],
        "handbook.pdf",
    )
    # The context_keywords span BOTH pages -- proving top_k > 1 actually
    # matters: if only one of the two relevant chunks were retrieved,
    # this fact could never match.
    _set_llm(
        [
            (
                ["paid", "leaves", "reset"],
                ["paid", "leaves", "reset", "january"],
                "You get 24 paid leaves, resetting every January 1st.",
            )
        ]
    )

    response = client.post(
        "/chat", json={"question": "How many paid leaves do I get and when do they reset?"}
    )
    body = response.json()

    assert response.status_code == 200
    assert body["answer"] == "You get 24 paid leaves, resetting every January 1st."
    pages = {s["page"] for s in body["sources"]}
    assert pages == {1, 2}
