"""
POST /chat

The query-side pipeline from the README's architecture diagram, made
real: question -> query embedding -> vector search -> top-k chunks ->
prompt -> LLM -> answer + sources. This route only orchestrates calls
into services built in prior stages and shapes the response; no
retrieval, prompt-formatting, or generation logic lives here.

Logging follows the request's actual shape (request received ->
retrieval started -> chunks retrieved + their scores -> LLM request ->
response generated) so a slow or wrong answer can be diagnosed from
logs alone: was retrieval empty? were the scores low (bad match)? did
the LLM take unusually long? No prompt/answer content or secrets are
logged -- only counts, scores, and lengths.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.config import settings
from app.dependencies import get_llm_service, get_retriever
from app.models.schemas import ChatRequest, ChatResponse, Source
from app.services.embeddings import EmbeddingGenerationError
from app.services.llm import LLMGenerationError, LLMService
from app.services.prompt_builder import build_prompt
from app.services.retriever import Retriever
from app.services.vector_store import VectorStoreError

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    retriever: Retriever = Depends(get_retriever),
    llm: LLMService = Depends(get_llm_service),
) -> ChatResponse:
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Question must not be empty.")

    logger.info("chat request received, question_length=%d", len(question))

    # Note: a missing API key (ConfigurationError) can't surface here --
    # retriever/llm are constructed by FastAPI's dependency injection
    # before this function body even starts running, so that failure is
    # handled globally in app/main.py instead.
    try:
        logger.info("retrieval started, top_k=%d", settings.top_k)
        chunks = retriever.retrieve(question, top_k=settings.top_k)
        logger.info(
            "retrieval complete, chunks_retrieved=%d scores=%s",
            len(chunks),
            [round(c.score, 3) for c in chunks],
        )

        prompt = build_prompt(question, chunks)

        logger.info("llm request sending, model=%s", settings.llm_model)
        answer = llm.generate(prompt)
        logger.info("llm response generated, answer_length=%d", len(answer))
    except (EmbeddingGenerationError, VectorStoreError) as e:
        logger.error("retrieval failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to search the documents. Please try again.",
        ) from e
    except LLMGenerationError as e:
        logger.error("llm generation failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to generate an answer. Please try again.",
        ) from e

    # Multiple retrieved chunks can come from the same page -- collapse
    # to one Source entry per (filename, page) pair, in first-seen order.
    seen: dict[tuple[str, int], Source] = {}
    for c in chunks:
        filename = c.metadata.get("filename", "unknown")
        page = c.metadata.get("page_number", 0)
        seen.setdefault((filename, page), Source(filename=filename, page=page))

    return ChatResponse(answer=answer, sources=list(seen.values()))
