"""
Housekeeping for the document store: remove duplicate uploads, orphaned
files, and orphaned vector chunks -- or wipe everything.

A "document" is created per upload with a random id, so uploading the
same PDF twice produces two independent documents (same filename,
different id, duplicated chunks in the vector DB). This script reconciles
the three places state lives:

  * data/registry.json        -- one record per uploaded document
  * data/uploads/<id>.pdf     -- the stored file
  * vector_db/ (ChromaDB)     -- one row per chunk, tagged with document_id

Run it with the API server STOPPED (ChromaDB keeps a write lock on its
SQLite file on Windows).

Usage
-----
  python scripts/cleanup_db.py --dry-run      # show what would change, do nothing
  python scripts/cleanup_db.py                # delete duplicate documents (same filename -> keep newest)
  python scripts/cleanup_db.py --orphans      # also delete files / chunks not referenced by the registry
  python scripts/cleanup_db.py --all          # duplicates + orphans
  python scripts/cleanup_db.py --wipe         # delete EVERY document, file and chunk (asks to confirm)
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

# Allow "python scripts/cleanup_db.py" from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402
from app.services import registry  # noqa: E402
from app.services.vector_store import VectorStore  # noqa: E402


def _uploads_dir() -> Path:
    return Path(settings.upload_dir)


def _stored_path(document_id: str) -> Path:
    return _uploads_dir() / f"{document_id}.pdf"


def _chroma_document_ids(store: VectorStore) -> set[str]:
    got = store._collection.get(include=["metadatas"])  # noqa: SLF001 -- maintenance script
    return {m.get("document_id") for m in got["metadatas"] if m.get("document_id")}


def delete_document(store: VectorStore, document_id: str, *, dry_run: bool) -> None:
    """The same three-step teardown the DELETE /documents/{id} route does."""
    if dry_run:
        return
    store.delete_document(document_id)
    _stored_path(document_id).unlink(missing_ok=True)
    registry.remove_document(document_id)


def find_duplicates() -> list[dict]:
    """Registry records to drop: for each filename, keep the newest upload."""
    by_name: dict[str, list[dict]] = defaultdict(list)
    for record in registry.list_documents():
        by_name[record["filename"]].append(record)

    to_delete: list[dict] = []
    for records in by_name.values():
        records.sort(key=lambda r: r.get("uploaded_at", ""), reverse=True)
        to_delete.extend(records[1:])  # keep [0] (newest)
    return to_delete


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="print planned changes, modify nothing")
    parser.add_argument("--orphans", action="store_true", help="also remove files/chunks not in the registry")
    parser.add_argument("--all", action="store_true", help="duplicates + orphans")
    parser.add_argument("--wipe", action="store_true", help="remove every document, file and chunk")
    args = parser.parse_args()

    store = VectorStore()
    known_ids = {r["document_id"] for r in registry.list_documents()}

    if args.wipe:
        docs = registry.list_documents()
        print(f"WIPE: {len(docs)} registered document(s), "
              f"{len(list(_uploads_dir().glob('*.pdf')))} stored file(s), "
              f"{store.count()} vector chunk(s)")
        if not args.dry_run:
            confirm = input("Type 'wipe' to confirm: ").strip()
            if confirm != "wipe":
                print("Aborted.")
                return 1
            for record in docs:
                delete_document(store, record["document_id"], dry_run=False)
            for pdf in _uploads_dir().glob("*.pdf"):
                pdf.unlink(missing_ok=True)
            for oid in _chroma_document_ids(store):
                store.delete_document(oid)
        print("Done." if not args.dry_run else "(dry run) nothing changed")
        return 0

    do_orphans = args.orphans or args.all
    total = 0

    duplicates = find_duplicates()
    if duplicates:
        print(f"Duplicate documents ({len(duplicates)}):")
        for record in duplicates:
            print(f"  - {record['filename']}  id={record['document_id']}  uploaded {record['uploaded_at']}")
            delete_document(store, record["document_id"], dry_run=args.dry_run)
            total += 1
    else:
        print("No duplicate documents.")

    if do_orphans:
        known_ids = {r["document_id"] for r in registry.list_documents()}  # refresh after deletes

        orphan_files = [p for p in _uploads_dir().glob("*.pdf") if p.stem not in known_ids]
        if orphan_files:
            print(f"\nOrphaned files ({len(orphan_files)}):")
            for path in orphan_files:
                print(f"  - {path.name}")
                if not args.dry_run:
                    path.unlink(missing_ok=True)
                total += 1

        orphan_chunks = _chroma_document_ids(store) - known_ids
        if orphan_chunks:
            print(f"\nOrphaned vector-chunk sets ({len(orphan_chunks)}):")
            for oid in orphan_chunks:
                print(f"  - document_id={oid}")
                if not args.dry_run:
                    store.delete_document(oid)
                total += 1

        if not orphan_files and not orphan_chunks:
            print("\nNo orphaned files or chunks.")

    verb = "would remove" if args.dry_run else "removed"
    print(f"\n{verb} {total} item(s). Vector chunks now: {store.count()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
