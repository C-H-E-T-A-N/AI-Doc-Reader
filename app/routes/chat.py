"""
POST /chat

The query-side pipeline from the README's architecture diagram, made
real: question -> query embedding -> vector search -> top-k chunks ->
prompt -> LLM -> answer + sources. This route only orchestrates calls
into services built in prior stages and shapes the response; no
retrieval, prompt-formatting, or generation logic lives here.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.config import settings
from app.dependencies import get_llm_service, get_retriever
from app.models.schemas import ChatRequest, ChatResponse, Source
from app.services.llm import LLMService
from app.services.prompt_builder import build_prompt
from app.services.retriever import Retriever

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

    chunks = retriever.retrieve(question, top_k=settings.top_k)
    logger.info(
        "question=%r retrieved=%d scores=%s",
        question,
        len(chunks),
        [round(c.score, 3) for c in chunks],
    )

    prompt = build_prompt(question, chunks)
    answer = llm.generate(prompt)

    # Multiple retrieved chunks can come from the same page -- collapse
    # to one Source entry per (filename, page) pair, in first-seen order.
    seen: dict[tuple[str, int], Source] = {}
    for c in chunks:
        filename = c.metadata.get("filename", "unknown")
        page = c.metadata.get("page_number", 0)
        seen.setdefault((filename, page), Source(filename=filename, page=page))

    return ChatResponse(answer=answer, sources=list(seen.values()))
