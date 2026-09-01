# RAG Document Q&A API — Learning Project

A Retrieval-Augmented Generation (RAG) pipeline built **from scratch** (no LangChain/LlamaIndex
in Phase 1) so every stage of the pipeline is visible and understood, not hidden behind a
framework call. Upload a PDF, ask questions about it, get answers grounded in the document's
actual content, with citations back to the source page.

> Status: all 12 build stages complete, verified against a real provider (Gemini) end-to-end --
> real upload, real embeddings, real retrieval, real generation, correct grounded answer for an
> answerable question and a correct refusal (not a hallucination) for an unanswerable one. See
> "Build stages" for how this was built, one concept at a time.

## Table of contents

1. [What RAG is, and why it's used](#what-rag-is-and-why-its-used)
2. [Architecture](#architecture)
3. [What an embedding is](#what-an-embedding-is)
4. [What a vector database is](#what-a-vector-database-is)
5. [What retrieval is](#what-retrieval-is)
6. [How the LLM fits in](#how-the-llm-fits-in)
7. [Why this stack](#why-this-stack)
8. [Project structure](#project-structure)
9. [Setup](#setup)
10. [Environment variables](#environment-variables)
11. [API endpoints](#api-endpoints)
12. [Error handling](#error-handling)
13. [Logging](#logging)
14. [Testing](#testing)
15. [Evaluation](#evaluation)
16. [Build stages](#build-stages)
17. [Known limitations](#known-limitations)
18. [Future improvements](#future-improvements)

## What RAG is, and why it's used

A plain LLM answers a question using only what it memorized during training. Ask it about
*your* company's leave policy and it either says it doesn't know, or -- worse -- confidently
guesses at a plausible-sounding but made-up answer (a **hallucination**), because it has no
access to your actual documents and no way to tell you that.

**Retrieval-Augmented Generation** fixes this by changing what the LLM is asked to do. Instead
of "answer this from memory," the system first **retrieves** the specific pieces of *your*
documents that are relevant to the question, and hands them to the LLM as context alongside the
question: "answer this using *only* the following text." The LLM's job shrinks from "know the
answer" (unreliable -- it either does or it doesn't) to "read this text and answer from it"
(much more reliable -- reading comprehension is something LLMs are genuinely good at). This is
also what makes citations possible: since the answer is built from specific retrieved chunks,
the system knows exactly which document and page it came from.

RAG is used instead of just fine-tuning a model on your documents because: it doesn't require
retraining anything when documents change (add/remove a PDF and it's immediately reflected);
it scales to far more information than fits in a single prompt (the corpus can be huge --
only the relevant slice gets retrieved per question); and it's auditable -- you can point at
the exact source text an answer came from, which a fine-tuned model's internal weights cannot
give you.

## Architecture

**Ingestion pipeline** (runs once per uploaded document -- `POST /documents/upload`):

```
PDF file
   │
   ▼
Text Extraction        (PyMuPDF reads each page's text layer)
   │
   ▼
Chunking                (split into overlapping ~500-char windows, per page)
   │
   ▼
Embedding Model         (each chunk → a vector, via OpenAI embeddings API)
   │
   ▼
Vector Database         (ChromaDB stores vector + chunk text + metadata)
```

**Query pipeline** (runs once per question -- `POST /chat`):

```
User question
   │
   ▼
Query Embedding          (question → vector, same embedding model as ingestion)
   │
   ▼
Vector Search             (cosine similarity against stored chunk vectors)
   │
   ▼
Top-K Relevant Chunks
   │
   ▼
Prompt Construction       (question + retrieved chunks assembled into one prompt)
   │
   ▼
LLM (Claude)               (generates an answer constrained to the given context)
   │
   ▼
Grounded Answer + Sources
```

The two pipelines only ever meet inside the vector database: ingestion's whole job is to
populate it, query's whole job is to read from it. Every arrow above is a real, separately
testable function in `app/services/` -- there is no framework doing this "automatically" behind
the scenes.

## What an embedding is

An embedding model maps a piece of text to a fixed-length list of numbers (a **vector**) --
1536 numbers for the model this project uses -- trained so that texts with similar *meaning*
end up as vectors pointing in similar *directions*, even when they share no words in common.
`"Employees receive 24 paid leaves per year."` becomes conceptually `[0.012, -0.083, 0.041, ...]`.

Three ways to compare two vectors, each answering a different question:

- **Dot product** -- `Σ(aᵢ × bᵢ)`, sum of elementwise products. Grows with both similarity *and*
  vector length, so two long vectors pointing similar directions can outscore two short ones
  pointing in the exact same direction.
- **Euclidean distance** -- `√(Σ(aᵢ - bᵢ)²)`, straight-line distance between the two points.
  Also sensitive to magnitude.
- **Cosine similarity** -- `dot(a,b) / (‖a‖ × ‖b‖)`, the dot product normalized by both
  vectors' lengths, so it measures only the *angle* between them (-1 to 1). This is what RAG
  systems use almost universally, because we care whether two chunks mean the same thing, not
  how "long" their vectors are.

A concrete demonstration run during development, using hand-rolled word-count vectors (not a
real embedding model) and manually computed cosine similarity, against the sentence *"Employees
receive 24 paid leaves per year"*:

| Compared sentence | Cosine similarity | Why |
|---|---|---|
| "Employees get 24 paid leaves each year." | 0.714 | shares several words |
| "Staff are entitled to 24 vacation days annually." | 0.134 | **means the same thing**, shares almost no words |
| "The office is located in downtown Seattle." | 0.000 | unrelated |

The middle row is the important one: naive word-counting scores the true paraphrase *lower*
than it "should" be, because it can't see that "staff"/"employees" or "vacation days"/"paid
leaves" mean the same thing. A real trained embedding model closes exactly that gap -- it's
learned, from massive text exposure, which words and phrases tend to substitute for each other
-- which is the entire reason embeddings are used for semantic search instead of keyword
matching.

## What a vector database is

Not a black box that "understands" documents -- a specialized index over `(vector, text,
metadata)` triples, optimized for one operation: given a query vector, find the N stored
vectors closest to it, fast. For every chunk, three things are stored side by side: the
**vector** (for the similarity math), the **original chunk text** (the vector alone is useless
once the LLM needs real text to read), and **metadata** (`document_id`, `filename`,
`page_number`, `chunk_index` -- how a match traces back to its source).

Naive similarity search -- compare the query vector against every stored vector, sort, take the
top K -- is exact but `O(n)` per query, fine for a few thousand chunks, too slow at millions.
ChromaDB (this project's choice, see "Why this stack") instead builds an **HNSW** index
(Hierarchical Navigable Small World graph): vectors are organized into a multi-layer graph where
each vector links to a handful of "nearby" vectors, and a search greedily hops through the graph
toward the query's neighborhood instead of visiting every stored vector -- roughly `O(log n)`
instead of `O(n)`, trading a small amount of exactness for a large speedup at scale. This is the
same mechanism production vector databases (Pinecone, Weaviate, pgvector w/ HNSW) run on
internally.

## What retrieval is

Retrieval is the query-time half of the pipeline: turn the question into a vector (using the
*same* embedding model used at ingestion time -- otherwise the vectors aren't comparable), run
a similarity search, return the top `k` chunks. `top_k` is a real tradeoff, not a free
parameter:

- **Too low** (e.g. `top_k=1`): if the answer spans two chunks -- common even with chunk
  overlap, since a question can need information from two different sections -- the single
  retrieved chunk may not contain everything needed, and the LLM either hallucinates the rest
  or wrongly says "not found."
- **Too high** (e.g. `top_k=20`): irrelevant chunks get stuffed into the prompt alongside
  relevant ones, costing money and latency, and risking "context dilution" -- the LLM has to
  find the signal in more noise.

This project's `similarity_search` has **no minimum-relevance threshold** -- it always returns
up to `top_k` results, however weak the match (see "Known limitations"). The only thing
preventing a fabricated answer from a weak match today is the LLM correctly following its
grounding instructions, not retrieval filtering out irrelevant chunks.

## How the LLM fits in

The LLM's role in this system is deliberately narrow: given the question and the retrieved
chunks (never the raw document, never anything not retrieved), produce an answer. This is
enforced by explicit instructions in the system prompt (`app/services/prompt_builder.py`):
answer only from the given context, say so explicitly if the context doesn't contain the
answer, don't invent information. None of this is automatic -- an LLM's default behavior, left
unconstrained, is to answer from whatever it learned in training, which would make the
"retrieval" part of RAG pointless. Grounding is a property of how the prompt is built and
instructed, not something inherent to handing an LLM some text.

## Why this stack

| Concern | Choice | Why |
|---|---|---|
| API framework | FastAPI | already known, async-friendly, great for teaching request/response shape of each pipeline stage |
| PDF text extraction | PyMuPDF (`fitz`) | fast, reliable text-layer extraction, gives per-page text + metadata cheaply |
| Chunking | hand-rolled, word-boundary-aware with overlap | transparent — we control exactly how splitting works, no hidden heuristics |
| Embeddings | OpenAI `text-embedding-3-small` (API), Gemini as an alternative | no heavy local ML dependency (avoids pulling in `torch`/`sentence-transformers`, which would bloat the environment); production-realistic — most real systems call an embedding API rather than hosting a model. Kept behind an `EmbeddingService` interface so the provider can be swapped without touching the rest of the app -- proven in practice, not just in theory: Gemini support was added and verified end-to-end without changing a single route, retrieval, or prompt-construction line. |
| Vector database | ChromaDB (local, file-backed) | zero external infra to run, persists to disk, good enough similarity search to learn the concepts before reaching for Pinecone/Weaviate/pgvector in a "real" deployment |
| LLM | Anthropic Claude (API), Gemini as an alternative | strong instruction-following for "answer only from this context", generous context window for stuffing retrieved chunks |
| Testing | pytest | already known |

We are **not** using LangChain/LlamaIndex, on purpose: the goal of Phase 1 is to understand
what each pipeline stage actually does, which a framework's high-level `.from_documents()`-style
API would hide. Phase 2 (see "Future improvements") revisits this once the fundamentals are
solid, comparing this hand-rolled pipeline against what a framework provides for free.

**Provider abstraction, proven, not just designed:** `EMBEDDING_PROVIDER`/`LLM_PROVIDER` (see
"Environment variables") select OpenAI/Anthropic (default) or Gemini. One Gemini API key (free
tier available) covers both embeddings and generation. Wiring it in required zero changes to
`app/routes/`, `retriever.py`, or `prompt_builder.py` -- only new provider classes in
`embeddings.py`/`llm.py` -- which is the actual payoff of the `EmbeddingProvider`/`LLMProvider`
seam from Stages 4 and 7, demonstrated rather than just asserted.

## Project structure

```
app/
  main.py                  FastAPI app entrypoint, global exception handlers
  config.py                 all environment-driven settings, one place
  dependencies.py           FastAPI dependency providers (singletons, swappable in tests)
  routes/
    documents.py             POST /documents/upload  -- extract, chunk, embed, store
    chat.py                  POST /chat               -- retrieve, prompt, generate
  services/
    document_loader.py       PDF -> text
    chunker.py                text -> chunks
    embeddings.py             chunks/query -> vectors           (EmbeddingService)
    vector_store.py           vectors -> ChromaDB                (VectorStore)
    retriever.py               query -> top-k relevant chunks     (Retriever)
    prompt_builder.py         question + chunks -> prompt         (build_prompt)
    llm.py                     prompt -> generated answer          (LLMService)
    exceptions.py              shared exception types (ConfigurationError)
  models/
    schemas.py                 Pydantic request/response models
data/uploads/                 uploaded PDFs land here (git-ignored)
vector_db/                    ChromaDB's on-disk persistence (git-ignored)
tests/                         pytest suite (unit + API + RAG-specific + eval regression)
eval/                           evaluation dataset + harness (retrieval/groundedness/hallucination)
```

Every provider (OpenAI, Anthropic, ChromaDB) sits behind a small abstraction (`EmbeddingProvider`,
`LLMProvider`) so nothing outside one file imports the SDK directly -- swapping providers, or
injecting a fake for tests, touches only that file.

## Setup

Requires Python 3.11+ (project targets 3.12+ per the original spec; developed here against the
3.11 interpreter available in this environment -- no 3.12-only syntax is used, so either works).

```bash
# 1. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment variables
cp .env.example .env
# then edit .env and fill in OPENAI_API_KEY and ANTHROPIC_API_KEY

# 4. Run the API
uvicorn app.main:app --reload

# 5. Check it's alive
curl http://localhost:8000/health
```

## Environment variables

See `.env.example` for the full list with defaults. Summary:

| Variable | Purpose |
|---|---|
| `EMBEDDING_PROVIDER` | `openai` (default) or `gemini` -- which class `EmbeddingService` constructs |
| `LLM_PROVIDER` | `anthropic` (default) or `gemini` -- which class `LLMService` constructs |
| `OPENAI_API_KEY` | used when `EMBEDDING_PROVIDER=openai` |
| `EMBEDDING_MODEL`, `EMBEDDING_DIMENSIONS` | which OpenAI embedding model, and its output vector size |
| `ANTHROPIC_API_KEY` | used when `LLM_PROVIDER=anthropic` |
| `LLM_MODEL` | which Claude model generates answers |
| `GEMINI_API_KEY` | used when `EMBEDDING_PROVIDER=gemini` and/or `LLM_PROVIDER=gemini` -- one key covers both |
| `GEMINI_EMBEDDING_MODEL`, `GEMINI_LLM_MODEL` | which Gemini models to use |
| `CHUNK_SIZE`, `CHUNK_OVERLAP` | chunking parameters |
| `TOP_K` | how many chunks to retrieve per question |
| `UPLOAD_DIR`, `VECTOR_DB_DIR`, `CHROMA_COLLECTION_NAME` | storage locations |
| `MAX_UPLOAD_MB` | upload size limit |

No key is ever hardcoded in source — everything routes through `app/config.py`, which reads
from the environment (`.env` is git-ignored, never committed).

## API endpoints

### `POST /documents/upload`

Accepts a PDF (`multipart/form-data`, field name `file`), extracts its text, chunks it, embeds
each chunk, and stores it in the vector database -- full ingestion in one call.

```bash
curl -X POST http://localhost:8000/documents/upload \
  -F "file=@employee_handbook.pdf"
```
```json
{
  "document_id": "1024de9a32d5440ab1ec325dffd20ff8",
  "filename": "employee_handbook.pdf",
  "pages": 20,
  "characters": 45321,
  "chunks_indexed": 94,
  "status": "uploaded"
}
```

### `POST /chat`

Runs the full query pipeline: embed the question, retrieve relevant chunks, build a prompt,
generate an answer, return it with sources.

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "How many paid leaves do employees get?"}'
```
```json
{
  "answer": "Employees are entitled to 24 paid leaves per year.",
  "sources": [
    {"filename": "employee_handbook.pdf", "page": 5}
  ]
}
```

### `GET /health`

Liveness check, no dependencies constructed -- returns `{"status": "ok"}` even without API keys
configured.

## Error handling

| Failure | Status | Notes |
|---|---|---|
| Non-PDF file / empty file | 400 | checked before any processing |
| Oversized upload | 413 | enforced while streaming to disk, not after |
| Encrypted PDF / no extractable text | 422 | see `document_loader.py` |
| Empty question | 400 | |
| Missing `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` | 503 | handled globally in `app/main.py` — see note below |
| Embedding/LLM/vector-DB provider request fails | 502 | network, rate limit, auth, etc. — caught per-route |
| Anything else unexpected | 500 | generic message only; full exception logged server-side, never returned to the client |

Worth understanding: a missing API key can't be caught by a route's own `try/except`, because
`EmbeddingService`/`LLMService` are constructed by FastAPI's dependency injection
(`Depends(get_x)`) *before* the route function body runs at all. That failure is instead handled
by a dedicated `@app.exception_handler(ConfigurationError)` in `app/main.py` — one of the more
subtle FastAPI behaviors this project surfaced by testing it directly rather than assuming a
route-level `try/except` would cover every case.

## Logging

A `/chat` request logs its own pipeline stages (no prompt content or secrets, only counts/
scores/lengths):
```
chat request received, question_length=30
retrieval started, top_k=4
retrieval complete, chunks_retrieved=1 scores=[1.0]
llm request sending, model=claude-sonnet-5
llm response generated, answer_length=42
```

## Testing

```bash
pytest
```

55 tests, all using fake providers and temp directories — no network or API key required:

| File | Covers |
|---|---|
| `test_chunker.py` | word-boundary splitting, overlap, page tagging |
| `test_embeddings.py` | `EmbeddingService` interface, batching, missing-key error |
| `test_vector_store.py` | add/search/delete, ranking, metadata, missing-key isolation |
| `test_retriever.py` | embed→search composition, ranking, top_k, citations |
| `test_prompt_builder.py` | grounding instructions, citation formatting, empty-context case |
| `test_llm.py` | `LLMService` interface, missing-key error |
| `test_api.py` | upload/chat happy paths, invalid file, empty file, empty question |
| `test_error_handling.py` | missing key → 503, provider failure → 502, unexpected → 500 |
| `test_rag.py` | retrieval/grounding correctness, not just API contract — see below |
| `test_eval.py` | regression tests for the evaluation harness's own verdict logic |

`test_rag.py` is qualitatively different from the rest: it checks whether the system actually
behaves like RAG is supposed to, not just whether an endpoint returns the right status code. It
uses a bag-of-words fake embedding provider (real, if crude, cosine similarity over a small
shared vocabulary) and a fake LLM that only answers when both the *question* and the *retrieved
context* support the fact, mirroring the system prompt's own instructions. Five scenarios: an
answerable question, an unanswerable one (verifying refusal, not fabrication), a
topically-similar-but-non-answering case, multiple documents, and an answer requiring multiple
retrieved chunks.

`conftest.py` adds one autouse fixture redirecting `settings.upload_dir` to a per-test temp
directory, so no test writes real files into the project's actual `data/uploads/`.

## Evaluation

Testing checks whether the code runs correctly; evaluation checks whether the *system* is good
at its actual job — retrieving the right chunk and answering only when grounded. Run it with:

```bash
python -m eval.run_eval             # real OpenAI/Anthropic APIs -- needs .env keys
python -m eval.run_eval --dry-run   # fake providers -- proves the harness works, not real quality
```

`eval/questions.json` is a small hand-labeled set (5 questions) against a self-contained demo
corpus defined in `eval/run_eval.py` — two documents, three topics covered, two topics
deliberately left uncovered so some questions are genuinely unanswerable. For each question the
harness measures:

- **retrieval hit rate** — for answerable questions, was the expected source document actually
  retrieved? (If not, nothing downstream can succeed.)
- **groundedness** — does the generated answer actually contain the expected fact?
- **hallucination rate** — for unanswerable questions, did the system fabricate a
  confident-sounding answer instead of refusing? (Detected via a refusal-phrase heuristic here;
  a production setup might use a second LLM call as an automated judge instead.)

`--dry-run` proves the harness's own ingestion → retrieval → prompt → metric pipeline is wired
correctly, without API keys or cost — it never measures real system quality. A hand-run demo
during development confirmed the hallucination check actually catches a bad case: a simulated
poorly-grounded LLM that confidently answered "10 sick leave days" (a fact present in neither
document) was correctly flagged `HALLUCINATION`, not silently accepted.

## Build stages

This project was built incrementally, as a teaching exercise, one concept at a time:

1. Environment setup — project skeleton, dependencies, config
2. Document upload + PDF text extraction — what makes PDF parsing hard, why scanned PDFs need OCR
3. Chunking — why the whole document can't be one embedding, what overlap does
4. Embeddings — hand-rolled word-count/cosine-similarity demo before touching a real API
5. Vector store (ChromaDB) — what's actually stored, how HNSW search works
6. Retrieval — composing embedding + search, the `top_k` tradeoff
7. Prompt construction + LLM service — why grounding instructions must be explicit
8. `/chat` endpoint + wired-up ingestion — the full pipeline working end-to-end; caught a real
   FastAPI dependency-injection bug by testing it, not just writing it
9. Error handling + logging — provider failures, missing keys, and why some errors need a
   global exception handler instead of a route-level `try/except`
10. Full test suite — 51 tests; found and fixed a real test-isolation bug along the way
11. Evaluation harness — retrieval hit rate, groundedness, hallucination detection; proved the
    hallucination check works by feeding it a deliberately bad answer
12. Full documentation (this file)

## Known limitations

- Verified end-to-end against Gemini (`EMBEDDING_PROVIDER=gemini`, `LLM_PROVIDER=gemini`), not
  against the OpenAI/Anthropic default path -- that combination is still only tested with fakes.
  Getting the Gemini run working surfaced real issues fakes couldn't have caught: the originally
  configured default model was deprecated for new API keys (404), and Gemini's newer models can
  return a successful response with no answer text if `max_output_tokens` runs out during
  internal "thinking" before any visible output -- both are now handled explicitly (see
  `app/services/llm.py` and `app/config.py`).
- Gemini's free tier has a low per-minute rate limit -- a `429` during a quick succession of
  requests is expected, not a bug; the app correctly turns it into a `502`, not a crash.
- Text-based PDFs only; scanned/image PDFs need OCR (out of scope for this version — see
  `app/services/document_loader.py` for why).
- Encrypted/password-protected PDFs are rejected rather than prompted for a password.
- `similarity_search` has no minimum-relevance threshold — it always returns up to `top_k`
  results, however weak the match. The grounding safety net today is entirely the LLM following
  its system prompt, not retrieval filtering out irrelevant chunks.
- No conversation history — each `/chat` call is independent, with no memory of prior questions.
- No document deletion endpoint (the `VectorStore.delete_document()` service method exists and
  is tested, but isn't exposed over the API).
- Chunking never spans a page boundary — a fact split exactly across two pages can be split
  across chunks even with overlap.

## Future improvements

**Phase 2** (deepening the pipeline itself, still hand-rolled):
1. Better chunking strategies (semantic/sentence-aware splitting, not just character windows)
2. Metadata filtering (restrict retrieval to a specific document/date range)
3. Hybrid search (combine vector similarity with keyword/BM25 search)
4. Reranking (a second, more expensive pass to reorder the initial top-k)
5. Query rewriting (expand/clarify the user's question before embedding it)
6. Context compression (summarize retrieved chunks before sending to the LLM)
7. Conversation history (multi-turn `/chat`, not just single questions)
8. Streaming LLM responses
9. Better citations (highlight the exact sentence used, not just the page)
10. A relevance threshold on `similarity_search` (addressing the limitation above)
11. Latency and cost optimization (caching embeddings, smaller models where acceptable)
12. Production architecture (auth, multi-tenancy, a managed vector DB, observability)

**Phase 3** (framework comparison): once Phase 2 is solid, reimplement the same pipeline using
LangChain and/or LlamaIndex, and compare — what do their abstractions buy you, what do they
hide that's worth understanding, and where does the hand-rolled version stay easier to reason
about or debug.
