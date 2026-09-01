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
    # llm.py) -- "openai"/"anthropic" (default) or "gemini". Switching
    # providers never touches routes, retrieval, or prompt code: that's
    # the point of the EmbeddingProvider/LLMProvider abstraction.
    embedding_provider: str = "openai"
    llm_provider: str = "anthropic"

    openai_api_key: str = ""
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536

    anthropic_api_key: str = ""
    llm_model: str = "claude-sonnet-5"

    gemini_api_key: str = ""
    gemini_embedding_model: str = "gemini-embedding-001"
    gemini_llm_model: str = "gemini-2.5-flash"

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


# Imported everywhere else as: from app.config import settings
settings = Settings()
