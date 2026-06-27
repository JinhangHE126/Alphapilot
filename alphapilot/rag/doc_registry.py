"""Track ingested documents per symbol and enforce retention (max N docs)."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from rag.chunk_fts import get_chunk_fts

REGISTRY_DB = Path("rag_data/doc_registry.db")
REGISTRY_DB.parent.mkdir(parents=True, exist_ok=True)

MAX_DOCS_PER_SYMBOL = 20


def _conn() -> sqlite3.Connection:
    REGISTRY_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(REGISTRY_DB), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ingested_docs (
            doc_id TEXT PRIMARY KEY,
            symbol TEXT NOT NULL,
            publish_date TEXT NOT NULL DEFAULT '',
            chunk_ids TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_ingested_docs_symbol ON ingested_docs(symbol)"
    )
    conn.commit()
    return conn


def register_document(
    symbol: str,
    doc_id: str,
    publish_date: str,
    chunk_ids: list[str],
) -> None:
    conn = _conn()
    conn.execute(
        """INSERT INTO ingested_docs (doc_id, symbol, publish_date, chunk_ids)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(doc_id) DO UPDATE SET
             publish_date=excluded.publish_date,
             chunk_ids=excluded.chunk_ids""",
        (doc_id, symbol.upper(), publish_date or "", json.dumps(chunk_ids)),
    )
    conn.commit()
    conn.close()


def list_documents(symbol: str) -> list[dict]:
    conn = _conn()
    rows = conn.execute(
        "SELECT doc_id, publish_date, chunk_ids FROM ingested_docs WHERE symbol = ?",
        (symbol.upper(),),
    ).fetchall()
    conn.close()
    return [
        {
            "doc_id": r["doc_id"],
            "publish_date": r["publish_date"] or "",
            "chunk_ids": json.loads(r["chunk_ids"] or "[]"),
        }
        for r in rows
    ]


def prune_symbol_documents(symbol: str, max_docs: int = MAX_DOCS_PER_SYMBOL) -> list[str]:
    """Evict oldest documents beyond max_docs. Returns evicted doc_ids."""
    docs = list_documents(symbol)
    if len(docs) <= max_docs:
        return []

    docs.sort(key=lambda d: d["publish_date"] or "0000")
    to_evict = [d["doc_id"] for d in docs[: len(docs) - max_docs]]
    if not to_evict:
        return []

    fts = get_chunk_fts()
    conn = _conn()
    for doc_id in to_evict:
        fts.evict_doc(doc_id)
        conn.execute("DELETE FROM ingested_docs WHERE doc_id = ?", (doc_id,))
    conn.commit()
    conn.close()

    from rag.retriever import retriever

    retriever.mark_doc_evicted(to_evict)
    print(f"🗑️ Pruned {len(to_evict)} document(s) for {symbol} (max {max_docs})")
    return to_evict
