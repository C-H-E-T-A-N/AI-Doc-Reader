"""
Shared test fixtures.

_isolate_upload_dir (autouse): redirects settings.upload_dir to a
per-test temp directory, so API-level tests (test_api.py, test_rag.py,
test_error_handling.py) that hit the real /documents/upload route never
write into the project's actual data/uploads/ directory. Service-level
tests (chunker, embeddings, vector store, retriever, ...) already
isolate themselves directly via pytest's tmp_path fixture and are
unaffected by this.
"""

import pytest

from app.config import settings


@pytest.fixture(autouse=True)
def _isolate_upload_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))
