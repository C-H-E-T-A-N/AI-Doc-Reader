# RAG Document Q&A API — Learning Project

A Retrieval-Augmented Generation (RAG) pipeline built **from scratch** (no LangChain/LlamaIndex
in phase 1) so every stage of the pipeline is visible and understood, not hidden behind a
framework call.

> Status: Stage 1 of 12 complete (environment + skeleton). See "Build stages" below.

## What this project does

Upload a PDF → ask questions about it → get answers grounded in the document's actual content,
with citations back to the source page.

## Architecture

**Ingestion pipeline** (runs once per uploaded document):

```
PDF file
   │
   ▼
Text Extraction        (PyMuPDF reads each page's text layer)
   │
   ▼
Chunking                (split into overlapping ~500-char windows)
   │
   ▼
Embedding Model         (each chunk → a vector, via OpenAI embeddings API)
   │
   ▼
Vector Database         (ChromaDB stores vector + chunk text + metadata)
```

**Query pipeline** (runs once per question):

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

The key idea of RAG: instead of asking an LLM a question cold (where it can only rely on
whatever it memorized during training, and may hallucinate), we first **retrieve** the most
relevant pieces of *your* documents and hand them to the LLM as context. The LLM's job shrinks
from "know the answer" to "read this context and answer from it" — which is a much more
reliable task, and lets us cite exactly which page the answer came from.

## Why this stack

| Concern | Choice | Why |
|---|---|---|
| API framework | FastAPI | already known, async-friendly, great for teaching request/response shape of each pipeline stage |
| PDF text extraction | PyMuPDF (`fitz`) | fast, reliable text-layer extraction, gives per-page text + metadata cheaply |
| Chunking | hand-rolled, character-based with overlap | transparent — we control exactly how splitting works, no hidden heuristics |
| Embeddings | OpenAI `text-embedding-3-small` (API) | no heavy local ML dependency (avoids pulling in `torch`/`sentence-transformers`, which would bloat the environment); production-realistic — most real systems call an embedding API rather than hosting a model. Kept behind an `EmbeddingService` interface (Step 6) so it can be swapped for a local model later without touching the rest of the app. |
| Vector database | ChromaDB (local, file-backed) | zero external infra to run, persists to disk, good enough similarity search to learn the concepts before reaching for Pinecone/Weaviate/pgvector in a "real" deployment |
| LLM | Anthropic Claude (API) | strong instruction-following for "answer only from this context", generous context window for stuffing retrieved chunks |
| Testing | pytest | already known |

We are **not** using LangChain/LlamaIndex yet, on purpose — see "Build stages" below.

## Project structure

```
app/
  main.py                 FastAPI app entrypoint
  config.py                all environment-driven settings, one place
  routes/
    documents.py            POST /documents/upload            (Stage 2)
    chat.py                 POST /chat                        (Stage 8)
  services/
    document_loader.py      PDF -> text                       (Stage 2)
    chunker.py               text -> chunks                    (Stage 3)
    embeddings.py            chunks/query -> vectors            (Stage 4)
    vector_store.py          vectors -> ChromaDB                (Stage 5)
    retriever.py              query -> top-k relevant chunks     (Stage 6)
    prompt_builder.py        question + chunks -> prompt         (Stage 7)
    llm.py                    prompt -> generated answer          (Stage 7)
  models/
    schemas.py                Pydantic request/response models
data/uploads/                uploaded PDFs land here (git-ignored)
vector_db/                   ChromaDB's on-disk persistence (git-ignored)
tests/                        pytest suite
eval/                          retrieval/groundedness evaluation set + script (Stage 11)
```

## Setup

Requires Python 3.11+ (project targets 3.12+ per the original spec; developed here against
the 3.11 interpreter available in this environment — no 3.12-only syntax is used, so either
works).

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
| `OPENAI_API_KEY` | used only by the embedding service |
| `EMBEDDING_MODEL`, `EMBEDDING_DIMENSIONS` | which embedding model, and its output vector size |
| `ANTHROPIC_API_KEY` | used only by the LLM service |
| `LLM_MODEL` | which Claude model generates answers |
| `CHUNK_SIZE`, `CHUNK_OVERLAP` | chunking parameters (Stage 3) |
| `TOP_K` | how many chunks to retrieve per question (Stage 6) |
| `UPLOAD_DIR`, `VECTOR_DB_DIR`, `CHROMA_COLLECTION_NAME` | storage locations |
| `MAX_UPLOAD_MB` | upload size limit |

No key is ever hardcoded in source — everything routes through `app/config.py`, which reads
from the environment (`.env` is git-ignored).

## Build stages

This project is being built incrementally, as a teaching exercise, in this order:

1. ✅ Environment setup (this stage)
2. Document upload + PDF text extraction
3. Chunking
4. Embeddings (concept walkthrough + service)
5. Vector store (ChromaDB)
6. Retrieval
7. Prompt construction + LLM service
8. `/chat` endpoint — full pipeline wired together
9. Error handling + logging
10. Test suite
11. Evaluation harness
12. Full documentation

**Phase 2** (after the above works end-to-end): better chunking strategies, metadata
filtering, hybrid search, reranking, query rewriting, context compression, conversation
history, streaming responses, better citations — then a comparison against what
LangChain/LlamaIndex would give you for free.

## Testing

```bash
pytest
```

(Test suite is built out across the stages above; see Stage 10.)

## Known limitations (current stage)

- Only the `/health` endpoint exists so far — no document upload or chat yet.
- Text-based PDFs only for now; scanned/image PDFs need OCR, which is out of scope until
  we've covered the fundamentals (explained further in Stage 2/3).
