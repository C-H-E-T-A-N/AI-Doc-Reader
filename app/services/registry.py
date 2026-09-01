"""
Document registry -- a small JSON sidecar that records what has been
uploaded.

Why this exists
---------------
ChromaDB stores chunk-level rows (text + vector + metadata), not a
document-level record. To render a "your documents" list with a page
count, chunk count, file size, type and upload time, the app needs a
place to keep one row per uploaded document. Rather than add a real
database for a handful of fields, this module owns a single JSON file
(`data/registry.json`) written atomically under a process-wide lock.

It is deliberately tiny and has no dependency on the rest of the app so
it can be unit-tested in isolation, the same way the other services are.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path

from app.config import settings

_lock = threading.Lock()


def _registry_path() -> Path:
    # Lives next to the uploaded files, under data/. Kept out of source
    # control via .gitignore (data/* is already ignored).
    return Path(settings.upload_dir).parent / "registry.json"


def _read_all() -> list[dict]:
    path = _registry_path()
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        # A corrupt registry should not take the API down -- treat it as
        # empty. Uploads will rewrite it.
        return []


def _write_all(records: list[dict]) -> None:
    path = _registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    # Atomic replace: write a temp file in the same directory, fsync,
    # then os.replace so a reader never sees a half-written file.
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".registry-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(records, fh, indent=2, sort_keys=True)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def list_documents() -> list[dict]:
    """All records, newest upload first."""
    with _lock:
        records = _read_all()
    records.sort(key=lambda r: r.get("uploaded_at", ""), reverse=True)
    return records


def get_document(document_id: str) -> dict | None:
    with _lock:
        for record in _read_all():
            if record.get("document_id") == document_id:
                return record
    return None


def add_document(record: dict) -> dict:
    """Insert (or replace, by document_id) a single record."""
    with _lock:
        records = [r for r in _read_all() if r.get("document_id") != record["document_id"]]
        records.append(record)
        _write_all(records)
    return record


def remove_document(document_id: str) -> bool:
    """Drop a record. Returns True if something was removed."""
    with _lock:
        records = _read_all()
        kept = [r for r in records if r.get("document_id") != document_id]
        if len(kept) == len(records):
            return False
        _write_all(kept)
    return True
