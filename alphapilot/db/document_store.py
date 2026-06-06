from __future__ import annotations

import os
import sqlite3
import hashlib
from datetime import datetime
from typing import Optional

DB_PATH = os.getenv("FACT_STORE_PATH", str(__import__("pathlib").Path(__file__).parent.parent / "data" / "fact_store.db"))


class DocumentStore:
    def __init__(self, db_path: str = DB_PATH) -> None:
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._run_migrations()

    def _run_migrations(self) -> None:
        from pathlib import Path
        migration_dir = Path(__file__).parent / "migrations"
        if not migration_dir.is_dir():
            return
        for name in sorted(os.listdir(str(migration_dir))):
            if name.endswith(".sql"):
                path = migration_dir / name
                self._conn.executescript(path.read_text(encoding="utf-8"))
        self._conn.commit()

    def upsert(self, symbol: str, doc_type: str, fmt: str, source: str,
               content: bytes, source_url: Optional[str] = None,
               title: Optional[str] = None, as_of_date: Optional[str] = None,
               storage_path: Optional[str] = None) -> int | None:
        content_hash = hashlib.sha256(content).hexdigest()[:16]
        existing = self._conn.execute(
            "SELECT id FROM documents WHERE content_hash=?", (content_hash,)
        ).fetchone()
        if existing:
            return existing["id"]

        now = datetime.now().isoformat()
        cursor = self._conn.execute(
            """INSERT INTO documents
               (symbol, doc_type, format, source, source_url, title,
                retrieved_at, as_of_date, content_hash, raw_content, storage_path)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (symbol, doc_type, fmt, source, source_url, title,
             now, as_of_date, content_hash,
             content if storage_path is None else None,
             storage_path),
        )
        self._conn.commit()
        return cursor.lastrowid

    def get_unindexed(self, limit: int = 50) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM documents WHERE ingested_to_faiss=0 LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def mark_indexed(self, doc_id: int) -> None:
        self._conn.execute(
            "UPDATE documents SET ingested_to_faiss=1 WHERE id=?",
            (doc_id,),
        )
        self._conn.commit()


_document_store: Optional[DocumentStore] = None


def get_document_store() -> DocumentStore:
    global _document_store
    if _document_store is None:
        _document_store = DocumentStore()
    return _document_store