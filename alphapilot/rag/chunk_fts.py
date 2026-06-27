"""SQLite FTS5 index for document chunk full-text search (Phase 3 hybrid RRF)."""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Any

FTS_DB_PATH = Path("rag_data/chunk_fts.db")
FTS_DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def _escape_fts_query(query: str) -> str:
    tokens = re.findall(r"[\w\u4e00-\u9fff]+", query)
    if not tokens:
        return ""
    return " OR ".join(f'"{t}"' for t in tokens[:12])


class ChunkFTSIndex:
    def __init__(self, db_path: Path = FTS_DB_PATH) -> None:
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS chunk_fts_meta (
                chunk_id TEXT PRIMARY KEY,
                doc_id TEXT NOT NULL,
                symbol TEXT NOT NULL,
                publish_date TEXT,
                evicted INTEGER NOT NULL DEFAULT 0
            );
            CREATE VIRTUAL TABLE IF NOT EXISTS chunk_fts USING fts5(
                chunk_id UNINDEXED,
                doc_id UNINDEXED,
                symbol UNINDEXED,
                content,
                tokenize='unicode61'
            );
            """
        )
        self._conn.commit()

    def index_chunk(
        self,
        chunk_id: str,
        doc_id: str,
        symbol: str,
        content: str,
        publish_date: str = "",
    ) -> None:
        if not chunk_id or not content.strip():
            return
        self._conn.execute(
            "DELETE FROM chunk_fts WHERE chunk_id = ?", (chunk_id,)
        )
        self._conn.execute(
            """INSERT INTO chunk_fts_meta (chunk_id, doc_id, symbol, publish_date, evicted)
               VALUES (?, ?, ?, ?, 0)
               ON CONFLICT(chunk_id) DO UPDATE SET
                 doc_id=excluded.doc_id,
                 symbol=excluded.symbol,
                 publish_date=excluded.publish_date,
                 evicted=0""",
            (chunk_id, doc_id, symbol.upper(), publish_date or ""),
        )
        self._conn.execute(
            "INSERT INTO chunk_fts (chunk_id, doc_id, symbol, content) VALUES (?, ?, ?, ?)",
            (chunk_id, doc_id, symbol.upper(), content),
        )
        self._conn.commit()

    def search(
        self,
        query: str,
        symbol: str = "",
        k: int = 20,
    ) -> list[dict[str, Any]]:
        fts_q = _escape_fts_query(query)
        if not fts_q:
            return []

        if symbol:
            rows = self._conn.execute(
                """
                SELECT f.chunk_id, f.doc_id, f.symbol, f.content, m.publish_date
                FROM chunk_fts f
                JOIN chunk_fts_meta m ON m.chunk_id = f.chunk_id
                WHERE chunk_fts MATCH ? AND m.symbol = ? AND m.evicted = 0
                ORDER BY rank
                LIMIT ?
                """,
                (fts_q, symbol.upper(), k),
            ).fetchall()
        else:
            rows = self._conn.execute(
                """
                SELECT f.chunk_id, f.doc_id, f.symbol, f.content, m.publish_date
                FROM chunk_fts f
                JOIN chunk_fts_meta m ON m.chunk_id = f.chunk_id
                WHERE chunk_fts MATCH ? AND m.evicted = 0
                ORDER BY rank
                LIMIT ?
                """,
                (fts_q, k),
            ).fetchall()

        return [dict(r) for r in rows]

    def evict_doc(self, doc_id: str) -> int:
        rows = self._conn.execute(
            "SELECT chunk_id FROM chunk_fts_meta WHERE doc_id = ?",
            (doc_id,),
        ).fetchall()
        chunk_ids = [r["chunk_id"] for r in rows]
        if not chunk_ids:
            return 0
        for cid in chunk_ids:
            self._conn.execute("DELETE FROM chunk_fts WHERE chunk_id = ?", (cid,))
            self._conn.execute(
                "UPDATE chunk_fts_meta SET evicted = 1 WHERE chunk_id = ?",
                (cid,),
            )
        self._conn.commit()
        return len(chunk_ids)

    def list_doc_ids_for_symbol(self, symbol: str) -> list[dict[str, str]]:
        rows = self._conn.execute(
            """
            SELECT doc_id, MAX(publish_date) AS publish_date
            FROM chunk_fts_meta
            WHERE symbol = ? AND evicted = 0
            GROUP BY doc_id
            ORDER BY publish_date DESC
            """,
            (symbol.upper(),),
        ).fetchall()
        return [{"doc_id": r["doc_id"], "publish_date": r["publish_date"] or ""} for r in rows]


_fts_index: ChunkFTSIndex | None = None


def get_chunk_fts() -> ChunkFTSIndex:
    global _fts_index
    if _fts_index is None:
        _fts_index = ChunkFTSIndex()
    return _fts_index
