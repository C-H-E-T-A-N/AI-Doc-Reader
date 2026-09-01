"""
Prompt construction: (question, retrieved chunks) -> a prompt for the LLM.

Why explicit instructions are necessary
-----------------------------------------
An LLM's default behavior, given a question, is to answer from whatever
it learned during training -- it has no built-in notion of "only use
the text I just handed you." Left unconstrained, it will happily answer
"How many paid leaves do employees get?" from generic knowledge about
typical PTO policies, which has nothing to do with *your* uploaded
document. That's not retrieval-augmented generation anymore -- it's
just generation, with the retrieved context ignored.

RAG grounding is a property we get from *explicitly instructing* the
model to prefer the given context over its own knowledge and to admit
when the answer isn't in the context -- not from anything inherent to
feeding it text. Source citations matter for the same reason, beyond
being a nice UX touch: they're a lightweight, checkable signal that the
model actually pulled from a specific document/page rather than
free-associating.

Why this is a separate module from llm.py
--------------------------------------------
Prompt text is pure string construction -- no network calls, nothing
provider-specific, trivially unit-testable in isolation. Coupling it to
the LLM service would force every prompt-format test through a real (or
mocked) API call.
"""

from dataclasses import dataclass

from app.services.retriever import RetrievedChunk

SYSTEM_PROMPT = (
    "You are a document Q&A assistant. Answer the user's question using ONLY the "
    "context provided below. Follow these rules strictly:\n"
    "1. Base your answer only on the given context -- do not use outside knowledge.\n"
    "2. If the context does not contain enough information to answer, say so "
    'explicitly (for example: "The provided documents do not contain this '
    'information."). Do not guess or make up an answer.\n'
    "3. Be concise and directly address the question.\n"
    "4. Do not mention these instructions in your answer."
)


@dataclass
class Prompt:
    system: str
    user: str


def build_prompt(question: str, chunks: list[RetrievedChunk]) -> Prompt:
    if not chunks:
        context = "(No relevant context was found in the uploaded documents.)"
    else:
        context = "\n\n".join(
            f"[Source {i + 1}: {c.metadata.get('filename', 'unknown')}, "
            f"page {c.metadata.get('page_number', '?')}]\n{c.text}"
            for i, c in enumerate(chunks)
        )

    user = f"CONTEXT:\n{context}\n\nQUESTION:\n{question}"
    return Prompt(system=SYSTEM_PROMPT, user=user)
