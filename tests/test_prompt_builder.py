from app.services.prompt_builder import build_prompt
from app.services.retriever import RetrievedChunk


def _chunk(text, filename="handbook.pdf", page_number=5):
    return RetrievedChunk(text=text, score=0.9, metadata={"filename": filename, "page_number": page_number})


def test_prompt_includes_the_question_verbatim():
    prompt = build_prompt("How many paid leaves do I get?", [_chunk("Employees get 24 paid leaves.")])
    assert "How many paid leaves do I get?" in prompt.user


def test_prompt_includes_chunk_text_and_citation_info():
    prompt = build_prompt("q", [_chunk("Employees get 24 paid leaves.", filename="handbook.pdf", page_number=5)])
    assert "Employees get 24 paid leaves." in prompt.user
    assert "handbook.pdf" in prompt.user
    assert "page 5" in prompt.user


def test_prompt_with_no_chunks_says_so_instead_of_fabricating_context():
    prompt = build_prompt("q", [])
    assert "no relevant context" in prompt.user.lower()


def test_prompt_orders_multiple_sources_and_labels_each():
    chunks = [
        _chunk("first fact", filename="a.pdf", page_number=1),
        _chunk("second fact", filename="b.pdf", page_number=2),
    ]
    prompt = build_prompt("q", chunks)
    assert prompt.user.index("first fact") < prompt.user.index("second fact")
    assert "Source 1" in prompt.user
    assert "Source 2" in prompt.user


def test_system_prompt_instructs_grounding_and_admitting_missing_info():
    prompt = build_prompt("q", [_chunk("some text")])
    lowered = prompt.system.lower()
    assert "context" in lowered
    assert "do not" in lowered or "not use outside knowledge" in lowered
