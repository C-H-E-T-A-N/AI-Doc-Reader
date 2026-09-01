"""
Evaluation harness: measures RETRIEVAL and GROUNDING quality against a
small hand-labeled question set (questions.json) -- not just "did the
endpoint return 200", which is what test_api.py / test_rag.py already
check.

Why RAG evaluation is different from normal API testing
-----------------------------------------------------------
A normal test asserts an exact expected value. RAG has no such fixed
target for the LLM's final wording -- the same fact can be phrased many
valid ways, so string equality on the answer is the wrong tool. What
CAN be measured precisely, per question:

  - retrieval hit: for a question whose answer exists in the corpus,
    did the system actually retrieve the chunk from the expected
    source document? If not, nothing downstream can succeed --
    generation can't ground an answer in a chunk that was never
    retrieved.
  - groundedness: does the generated answer contain the fact it's
    supposed to (checked here by keyword presence -- a real production
    setup might use a second LLM call as an automated judge instead;
    that's a Phase 2-level upgrade, not implemented here)?
  - refusal correctness: for a question the corpus genuinely cannot
    answer, does the system say so, or does it hallucinate a
    plausible-sounding but fabricated answer?

None of this is pass/fail the way a unit test is. It's reported as
RATES over the question set (retrieval hit rate, groundedness rate,
hallucination rate), because RAG quality is a distribution of behavior
across many questions, not a single yes/no.

Usage
-----
    python -m eval.run_eval             # real OpenAI/Anthropic APIs -- needs .env keys
    python -m eval.run_eval --dry-run   # fake providers -- proves the harness itself
                                         # computes metrics correctly, without spending
                                         # API calls or requiring keys. NOT a measurement
                                         # of real system quality -- see the DryRunLLM
                                         # docstring below for exactly what it does and
                                         # does not prove.
"""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from app.services.chunker import Chunk, chunk_pages
from app.services.embeddings import EmbeddingProvider, EmbeddingService
from app.services.llm import LLMProvider, LLMService
from app.services.prompt_builder import build_prompt
from app.services.prompt_builder import Prompt
from app.services.retriever import Retriever
from app.services.vector_store import VectorStore

QUESTIONS_PATH = Path(__file__).parent / "questions.json"

# A small, self-contained corpus -- deliberately covers three topics
# (leave policy, dress code, wifi) across two "documents", so retrieval
# has to actually discriminate between sources, and leaves one topic
# (sick leave day count, parking) entirely uncovered, so some eval
# questions are genuinely unanswerable -- on purpose, to test refusal.
CORPUS: dict[str, list[str]] = {
    "employee_handbook.pdf": [
        "Employees receive 24 paid leaves per year. Leaves reset every January 1st.",
        "Sick leave requires a doctor's note after 3 consecutive days.",
        "The office dress code is business casual on weekdays.",
    ],
    "it_policy.pdf": [
        "The office WiFi password is printed on the router label in the break room.",
    ],
}

REFUSAL_PHRASES = [
    "do not contain",
    "does not contain",
    "no information",
    "cannot find",
    "can't find",
    "not mentioned",
    "not available in",
    "don't know",
    "do not know",
    "unable to find",
    "insufficient information",
    "not provided",
]


def looks_like_refusal(answer: str) -> bool:
    lowered = answer.lower()
    return any(phrase in lowered for phrase in REFUSAL_PHRASES)


class _FakePage:
    def __init__(self, page_number: int, text: str):
        self.page_number = page_number
        self.text = text


class BagOfWordsEmbeddingProvider(EmbeddingProvider):
    """
    A real (if crude) cosine-similarity vector over a small shared
    vocabulary derived from the corpus + question set -- closer to how
    a real embedding model behaves than a single-keyword flag, since it
    captures degree of overlap across several words at once, not just
    presence of one.
    """

    def __init__(self, vocabulary: list[str]):
        self._vocab = vocabulary

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            words = {w.strip(".,?'\"").lower() for w in text.split()}
            vectors.append([1.0 if v in words else 0.0 for v in self._vocab])
        return vectors


def make_dry_run_llm(answer_must_contain: list[str]) -> LLMService:
    """
    DOES prove: the harness's ingestion -> retrieval -> prompt
    construction -> metric computation pipeline runs correctly and
    produces the right verdicts for known-good and known-bad cases.

    DOES NOT prove: anything about real embedding or LLM quality. This
    fake looks directly at whether the retrieved context contains the
    expected keywords and returns a canned answer if so, or a refusal
    if not -- it cannot be fooled or surprised the way a real model can
    be. Run without --dry-run (with real API keys) for an actual
    measurement of system quality.
    """

    class _Fake(LLMProvider):
        def generate(self, prompt: Prompt) -> str:
            context = prompt.user.split("QUESTION:")[0].lower()
            if answer_must_contain and all(kw.lower() in context for kw in answer_must_contain):
                return "Based on the documents: " + ", ".join(answer_must_contain) + "."
            return "The provided documents do not contain this information."

    return LLMService(provider=_Fake())


@dataclass
class EvalResult:
    id: str
    question: str
    answerable: bool
    expected_source: str | None
    retrieved_filenames: list[str]
    retrieval_hit: bool | None  # None = not applicable (question has no expected source)
    answer: str
    verdict: str  # correct | correct_refusal | retrieval_miss | missed_answer | hallucination


def ingest_corpus(vector_store: VectorStore, embedding_service: EmbeddingService) -> None:
    for filename, pages_text in CORPUS.items():
        pages = [_FakePage(page_number=i + 1, text=text) for i, text in enumerate(pages_text)]
        chunks: list[Chunk] = chunk_pages(pages, chunk_size=500, chunk_overlap=50)
        embeddings = embedding_service.embed_documents([c.text for c in chunks])
        vector_store.add_chunks(
            document_id=filename, filename=filename, chunks=chunks, embeddings=embeddings
        )


def run(dry_run: bool) -> list[EvalResult]:
    questions = json.loads(QUESTIONS_PATH.read_text())

    tmp_dir = tempfile.mkdtemp(prefix="rag_eval_")
    try:
        vector_store = VectorStore(persist_directory=tmp_dir, collection_name="eval")

        if dry_run:
            vocabulary = sorted(
                {
                    w.strip(".,?'\"").lower()
                    for text in [t for texts in CORPUS.values() for t in texts]
                    + [q["question"] for q in questions]
                    for w in text.split()
                }
            )
            embedding_service = EmbeddingService(provider=BagOfWordsEmbeddingProvider(vocabulary))
        else:
            embedding_service = EmbeddingService()  # real OpenAI provider, needs OPENAI_API_KEY

        ingest_corpus(vector_store, embedding_service)
        retriever = Retriever(embedding_service=embedding_service, vector_store=vector_store)

        # top_k=2, not the default 4 -- our demo corpus only has 4 chunks
        # total, so top_k=4 would retrieve literally everything on every
        # query, which proves nothing about whether retrieval actually
        # discriminates between relevant and irrelevant chunks.
        results: list[EvalResult] = []
        for q in questions:
            chunks = retriever.retrieve(q["question"], top_k=2)
            retrieved_filenames = [c.metadata.get("filename", "unknown") for c in chunks]

            prompt = build_prompt(q["question"], chunks)
            llm = make_dry_run_llm(q["answer_must_contain"]) if dry_run else LLMService()
            answer = llm.generate(prompt)

            answerable = q["answerable"]
            expected_source = q["expected_source"]

            if answerable:
                retrieval_hit = expected_source in retrieved_filenames
                if not retrieval_hit:
                    verdict = "retrieval_miss"
                elif all(kw.lower() in answer.lower() for kw in q["answer_must_contain"]):
                    verdict = "correct"
                else:
                    verdict = "missed_answer"
            else:
                retrieval_hit = None
                verdict = "correct_refusal" if looks_like_refusal(answer) else "hallucination"

            results.append(
                EvalResult(
                    id=q["id"],
                    question=q["question"],
                    answerable=answerable,
                    expected_source=expected_source,
                    retrieved_filenames=retrieved_filenames,
                    retrieval_hit=retrieval_hit,
                    answer=answer,
                    verdict=verdict,
                )
            )
        return results
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def print_report(results: list[EvalResult]) -> None:
    print(f"{'ID':<4} {'Verdict':<16} {'Retrieved from':<40} Question")
    print("-" * 100)
    for r in results:
        unique_filenames = list(dict.fromkeys(r.retrieved_filenames))  # de-dup, preserve order
        retrieved = ", ".join(unique_filenames) or "(none)"
        print(f"{r.id:<4} {r.verdict:<16} {retrieved:<40} {r.question}")
        print(f"     answer: {r.answer}")

    answerable_results = [r for r in results if r.answerable]
    unanswerable_results = [r for r in results if not r.answerable]

    print("\n" + "=" * 100)
    print("SUMMARY")
    print("=" * 100)

    if answerable_results:
        hits = sum(1 for r in answerable_results if r.retrieval_hit)
        correct = sum(1 for r in answerable_results if r.verdict == "correct")
        print(
            f"Answerable questions:   {len(answerable_results)}  |  "
            f"retrieval hit rate: {hits}/{len(answerable_results)}  |  "
            f"correct + grounded: {correct}/{len(answerable_results)}"
        )

    if unanswerable_results:
        hallucinations = sum(1 for r in unanswerable_results if r.verdict == "hallucination")
        refusals = sum(1 for r in unanswerable_results if r.verdict == "correct_refusal")
        print(
            f"Unanswerable questions: {len(unanswerable_results)}  |  "
            f"correctly refused: {refusals}/{len(unanswerable_results)}  |  "
            f"HALLUCINATED: {hallucinations}/{len(unanswerable_results)}"
        )
        if hallucinations:
            print("  -> hallucination on an unanswerable question is the failure mode RAG exists to prevent.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Use fake providers instead of real OpenAI/Anthropic APIs (no API key needed).",
    )
    args = parser.parse_args()

    mode = "DRY RUN (fake providers -- proves the harness works, not real system quality)" if args.dry_run else "LIVE (real OpenAI/Anthropic APIs)"
    print(f"Mode: {mode}\n")

    results = run(dry_run=args.dry_run)
    print_report(results)


if __name__ == "__main__":
    main()
