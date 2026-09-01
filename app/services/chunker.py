"""
Chunking: splitting extracted document text into overlapping windows
small enough to embed meaningfully and retrieve precisely.

Why we can't just embed the whole PDF as one vector
-----------------------------------------------------
An embedding model compresses a piece of text into a single fixed-size
vector (e.g. 1536 numbers), meant to capture "what this text is about."
A 20-page handbook covers leave policy, working hours, dress code, IT
policy... compress all of that into one vector and none of those topics
survive distinctly -- you get a vector representing the document's
*average* meaning. A question like "how many paid leaves do I get?"
needs something precise to match against: a vector for *just* the
leave-policy paragraph, not the whole document's blur. Many small
chunks, each embedded separately, is what makes precise retrieval
possible.

Why overlap
-----------
Cut chunks at hard boundaries with no overlap, and a fact can be split
in half -- chunk N ends with "Employees receive 24", chunk N+1 starts
with "paid leaves per year." Neither chunk alone contains the complete
fact. Overlap repeats the last `chunk_overlap` characters of one chunk
at the start of the next, so a sentence near a boundary has a good
chance of appearing whole in at least one chunk.

Chunk size tradeoffs
---------------------
Too small (e.g. 50 chars): chunks lose surrounding context -- "It
resets every January 1st" is meaningless without knowing what "it" is.
Retrieval also gets noisier, with many near-duplicate tiny chunks
competing for the same top-k slots.

Too large (e.g. 5000 chars): back to the whole-document problem at a
smaller scale -- one chunk mixes multiple topics, diluting the
embedding signal for any single topic, and wastes LLM context budget on
irrelevant text once it's stuffed into the prompt. There's no
universally "correct" size; 500 characters with 50 overlap is a
reasonable starting point for policy-style prose, not a proven optimum.
"""

from dataclasses import dataclass
from typing import Protocol


class _HasPageText(Protocol):
    page_number: int
    text: str


@dataclass
class Chunk:
    text: str
    page_number: int
    chunk_index: int  # position of this chunk within the whole document, 0-based


def split_text(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    """
    Word-aware sliding window over a single string.

    We split on whitespace so a chunk boundary never lands in the middle
    of a word, then greedily pack words into a chunk until adding
    another word would exceed chunk_size characters. The next chunk
    starts by re-including the trailing ~chunk_overlap characters worth
    of words from the current chunk before continuing forward -- that
    shared tail is the overlap.
    """
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size")

    words = text.split()
    if not words:
        return []

    chunks: list[str] = []
    start = 0
    n = len(words)

    while start < n:
        current_words: list[str] = []
        current_len = 0
        end = start
        while end < n:
            word = words[end]
            added_len = len(word) + (1 if current_words else 0)  # +1 for the joining space
            if current_words and current_len + added_len > chunk_size:
                break
            current_words.append(word)
            current_len += added_len
            end += 1

        chunks.append(" ".join(current_words))

        if end >= n:
            break

        # Walk backward from `end` to find how many trailing words fit
        # within chunk_overlap characters -- that's where the next chunk
        # starts, so the two chunks share that tail of text.
        overlap_len = 0
        overlap_start = end
        while overlap_start > start:
            word = words[overlap_start - 1]
            added_len = len(word) + (1 if overlap_len > 0 else 0)
            if overlap_len + added_len > chunk_overlap:
                break
            overlap_len += added_len
            overlap_start -= 1

        # Guarantee forward progress even in a degenerate case.
        start = overlap_start if overlap_start > start else end

    return chunks


def chunk_pages(pages: list[_HasPageText], chunk_size: int, chunk_overlap: int) -> list[Chunk]:
    """
    Chunk each page independently -- a chunk never spans two pages -- so
    every chunk can be cited back to exactly one page number. Tradeoff:
    a sentence straddling a real page break in the source PDF can still
    be split across chunks; acceptable for policy-style documents,
    revisited in Phase 2 if it turns out to matter.
    """
    chunks: list[Chunk] = []
    index = 0
    for page in pages:
        for piece in split_text(page.text, chunk_size, chunk_overlap):
            chunks.append(Chunk(text=piece, page_number=page.page_number, chunk_index=index))
            index += 1
    return chunks
