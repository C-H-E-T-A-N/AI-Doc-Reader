"""
FastAPI application entry point.

At this stage the app only exposes a health check — routers for
/documents and /chat are added in later stages, one at a time.
"""

from fastapi import FastAPI

app = FastAPI(
    title="RAG Document Q&A API",
    description="A from-scratch Retrieval-Augmented Generation pipeline, built as a learning project.",
    version="0.1.0",
)


@app.get("/health")
def health_check():
    return {"status": "ok"}
