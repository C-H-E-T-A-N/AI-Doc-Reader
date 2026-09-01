"""
Regression tests for the evaluation harness itself (eval/run_eval.py)
-- not RAG quality, but making sure the harness's own verdict logic
stays correct as the pipeline evolves. If chunk_pages, Retriever, or
build_prompt's signatures ever change in a way that breaks the eval
script silently, these tests catch it.
"""

from eval.run_eval import looks_like_refusal, run


def test_looks_like_refusal_detects_common_refusal_phrasing():
    assert looks_like_refusal("The provided documents do not contain this information.")
    assert looks_like_refusal("I cannot find any mention of that in the context.")
    assert not looks_like_refusal("Employees receive 24 paid leaves per year.")


def test_dry_run_produces_expected_verdicts_for_the_known_question_set():
    results = run(dry_run=True)
    verdicts = {r.id: r.verdict for r in results}

    # These are known-answerable-in-corpus questions -- the dry-run fake
    # LLM is deterministic, so a correct verdict here proves ingestion,
    # retrieval, and prompt construction are wired correctly together.
    assert verdicts["q1"] == "correct"
    assert verdicts["q2"] == "correct"
    assert verdicts["q3"] == "correct"
    # These are deliberately unanswerable from the demo corpus.
    assert verdicts["q4"] == "correct_refusal"
    assert verdicts["q5"] == "correct_refusal"
