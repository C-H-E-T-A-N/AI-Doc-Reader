# Backend API image — portable across Render / Fly.io / Koyeb / Hugging Face Spaces.
#
#   docker build -t ai-doc-reader-api .
#   docker run -p 8000:8000 -e GROQ_API_KEY=gsk_... ai-doc-reader-api
#
# Providers default to the keyless/free combo (local ONNX embeddings +
# Groq LLM); only GROQ_API_KEY must be supplied at runtime.

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HOME=/app \
    EMBEDDING_PROVIDER=local \
    LLM_PROVIDER=groq \
    GROQ_LLM_MODEL=openai/gpt-oss-120b \
    CORS_ALLOW_ORIGINS=*

# onnxruntime (pulled in by chromadb, used by the local embedding
# provider) needs libgomp1 at runtime.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app

# Bake the ~80 MB all-MiniLM-L6-v2 ONNX model into the image so the first
# request is fast and does not depend on the model CDN at runtime.
RUN python -c "from chromadb.utils import embedding_functions as ef; ef.ONNXMiniLM_L6_V2()"

# Runtime-writable dirs. NOTE: on free hosting tiers these are ephemeral —
# uploaded PDFs and the vector store are lost on restart / redeploy.
RUN mkdir -p data/uploads vector_db && chmod -R 777 data vector_db

EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
