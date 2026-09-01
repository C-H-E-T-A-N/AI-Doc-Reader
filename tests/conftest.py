"""
Shared test fixtures.

_isolate_storage_dirs (autouse): redirects settings.upload_dir AND
settings.vector_db_dir to per-test temp directories, so API-level tests
(test_api.py, test_rag.py, test_error_handling.py) that hit real routes
never write into the project's actual data/uploads/ or vector_db/.
Service-level tests (chunker, embeddings, vector store, retriever, ...)
already isolate themselves directly via pytest's tmp_path fixture and
are unaffected by this.

Originally this only isolated upload_dir. That gap stayed invisible
until this environment got a working .env with real API keys: a test
meant to exercise the "API key missing -> 503" path
(test_upload_returns_503_when_api_key_is_missing) instead succeeded for
real once real keys existed, and its filename ("a.pdf") ended up
genuinely stored in the project's real vector_db/ -- because
VectorStore() falls back to settings.vector_db_dir, which nothing was
overriding. Fixed here rather than relying on tests never having real
credentials to fail in front of, which is not a safe assumption.
"""

import pytest

from app.config import settings


@pytest.fixture(autouse=True)
def _isolate_storage_dirs(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))
    monkeypatch.setattr(settings, "vector_db_dir", str(tmp_path / "vector_db"))
