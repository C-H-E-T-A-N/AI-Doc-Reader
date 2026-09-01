"""
FastAPI application entry point.

Routes handle failures that happen *inside* their own body (provider
request failures during retrieval/generation/indexing) and translate
them into specific HTTPExceptions -- see app/routes/documents.py and
app/routes/chat.py.

ConfigurationError (missing API key) is handled globally here instead,
for a reason worth understanding: EmbeddingService/LLMService are
constructed by FastAPI's dependency injection (Depends(get_x) in the
route signature), and that construction happens *before* the route
function body runs. A route's own try/except cannot catch an exception
raised during dependency resolution -- it never reaches the route body
at all. A dedicated exception_handler is the only place that failure
can be caught and turned into a clean 503 instead of the generic 500
safety net below.

The bare Exception handler is a last-resort safety net for anything
*not* explicitly handled: it logs the full exception server-side (for
debugging) but returns only a generic message to the client, so a bug
never leaks a stack trace, file path, or library internals through the
API.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.routes import chat, documents
from app.services.exceptions import ConfigurationError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# The google-genai SDK logs a harmless advisory on every non-streaming
# call ("Direct use of automatic function calling...") at WARNING level,
# which would otherwise clutter the clean pipeline logs from Stage 9.
logging.getLogger("google_genai.models").setLevel(logging.ERROR)

app = FastAPI(
    title="RAG Document Q&A API",
    description="A from-scratch Retrieval-Augmented Generation pipeline, built as a learning project.",
    version="0.1.0",
)

app.include_router(documents.router)
app.include_router(chat.router)


@app.exception_handler(ConfigurationError)
async def configuration_error_handler(request: Request, exc: ConfigurationError) -> JSONResponse:
    logger.error("Configuration error on %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception processing %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "An unexpected error occurred."})


@app.get("/health")
def health_check():
    return {"status": "ok"}
