import pytest

from app.services.chunker import Chunk, chunk_pages, split_text


class FakePage:
    """Minimal stand-in for document_loader.PageText, avoids importing PyMuPDF for these tests."""

    def __init__(self, page_number: int, text: str):
        self.page_number = page_number
        self.text = text


def test_empty_text_produces_no_chunks():
    assert split_text("", chunk_size=100, chunk_overlap=10) == []
    assert split_text("   ", chunk_size=100, chunk_overlap=10) == []


def test_text_shorter_than_chunk_size_is_a_single_chunk():
    text = "Employees receive 24 paid leaves per year."
    chunks = split_text(text, chunk_size=500, chunk_overlap=50)
    assert chunks == [text]


def test_overlap_must_be_smaller_than_chunk_size():
    with pytest.raises(ValueError):
        split_text("some text", chunk_size=50, chunk_overlap=50)
    with pytest.raises(ValueError):
        split_text("some text", chunk_size=50, chunk_overlap=60)


def test_long_text_is_split_into_multiple_chunks_within_size_limit():
    # 200 short words, well beyond a chunk_size of 50 characters.
    text = " ".join(f"word{i}" for i in range(200))
    chunks = split_text(text, chunk_size=50, chunk_overlap=10)

    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= 50


def test_consecutive_chunks_actually_overlap():
    text = " ".join(f"word{i}" for i in range(50))
    chunks = split_text(text, chunk_size=60, chunk_overlap=20)

    assert len(chunks) > 1
    for first, second in zip(chunks, chunks[1:]):
        first_words = first.split()
        second_words = second.split()
        # The tail of one chunk should reappear at the head of the next.
        overlap_found = any(
            first_words[-k:] == second_words[:k] for k in range(1, min(len(first_words), len(second_words)) + 1)
        )
        assert overlap_found, f"no overlap between {first!r} and {second!r}"


def test_no_words_are_lost_across_chunks():
    words = [f"word{i}" for i in range(50)]
    text = " ".join(words)
    chunks = split_text(text, chunk_size=60, chunk_overlap=20)

    # Every original word must appear in the chunked output (possibly repeated due to overlap).
    seen = set()
    for chunk in chunks:
        seen.update(chunk.split())
    assert seen == set(words)


def test_chunk_pages_tags_each_chunk_with_its_source_page():
    pages = [
        FakePage(page_number=1, text=" ".join(f"p1word{i}" for i in range(30))),
        FakePage(page_number=2, text=" ".join(f"p2word{i}" for i in range(30))),
    ]

    chunks = chunk_pages(pages, chunk_size=60, chunk_overlap=10)

    assert all(isinstance(c, Chunk) for c in chunks)
    page1_chunks = [c for c in chunks if c.page_number == 1]
    page2_chunks = [c for c in chunks if c.page_number == 2]
    assert page1_chunks and page2_chunks
    assert all("p1word" in c.text for c in page1_chunks)
    assert all("p2word" in c.text for c in page2_chunks)


def test_chunk_pages_assigns_sequential_chunk_index_across_the_whole_document():
    pages = [
        FakePage(page_number=1, text=" ".join(f"w{i}" for i in range(30))),
        FakePage(page_number=2, text=" ".join(f"w{i}" for i in range(30))),
    ]

    chunks = chunk_pages(pages, chunk_size=60, chunk_overlap=10)
    indices = [c.chunk_index for c in chunks]

    assert indices == list(range(len(chunks)))


def test_chunk_pages_skips_pages_with_no_text():
    pages = [
        FakePage(page_number=1, text=""),
        FakePage(page_number=2, text="some real content here"),
    ]

    chunks = chunk_pages(pages, chunk_size=500, chunk_overlap=50)

    assert len(chunks) == 1
    assert chunks[0].page_number == 2
