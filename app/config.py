"""
Centralized configuration, loaded once from environment variables / .env.

Every other module imports `settings` from here instead of calling
os.getenv() directly. That gives us one place to see every knob the
system has, and one place to change a default.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # --- Providers ---
    # embedding_provider/llm_provider select which class EmbeddingService/
    # LLMService construct by default (see app/services/embeddings.py and
    # llm.py). Switching providers never touches routes, retrieval, or
    # prompt code: that's the point of the EmbeddingProvider/LLMProvider
    # abstraction.
    #   embedding_provider: "openai" (default), "gemini", "local" (no key)
    #   llm_provider:       "anthropic" (default), "openai", "gemini", "groq"
    embedding_provider: str = "openai"
    llm_provider: str = "anthropic"

    openai_api_key: str = ""
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536
    # Used when llm_provider == "openai" -- lets one OpenAI key drive both
    # embeddings and answer generation.
    openai_llm_model: str = "gpt-4o-mini"

    # embedding_provider == "local": no API key, runs on-device via the
    # ONNX all-MiniLM-L6-v2 model bundled with chromadb (384-dim output).
    local_embedding_model: str = "all-MiniLM-L6-v2"

    # llm_provider == "groq": OpenAI-compatible endpoint, generous free
    # tier, no card. Key from https://console.groq.com/keys
    groq_api_key: str = ""
    groq_llm_model: str = "openai/gpt-oss-120b"
    groq_base_url: str = "https://api.groq.com/openai/v1"

    anthropic_api_key: str = ""
    llm_model: str = "claude-sonnet-5"

    gemini_api_key: str = ""
    gemini_embedding_model: str = "gemini-embedding-001"
    # "gemini-2.5-flash" is deprecated for new API keys as of this
    # writing (the API itself returns a 404 pointing here). Verified
    # working against a real key during Stage development.
    gemini_llm_model: str = "gemini-3.6-flash"

    # --- Chunking ---
    chunk_size: int = 500
    chunk_overlap: int = 50

    # --- Retrieval ---
    top_k: int = 4

    # --- Storage ---
    upload_dir: str = "data/uploads"
    vector_db_dir: str = "vector_db"
    chroma_collection_name: str = "documents"

    # --- Limits ---
    max_upload_mb: int = 25

    # --- CORS ---
    # Comma-separated list of origins allowed to call this API from a
    # browser, or "*" for any. The chat UI (see web/) is served from a
    # different origin -- localhost during dev, a Vercel domain once
    # deployed -- so the browser needs these headers to allow the call.
    cors_allow_origins: str = "*"


# Imported everywhere else as: from app.config import settings
settings = Settings()
