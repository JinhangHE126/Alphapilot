"""Shared ingest helpers for upload API and automated fetchers."""
from __future__ import annotations

import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from knowledge.document_chunker import chunk_document
from knowledge.pdf_parser import parse_and_chunk
from rag.doc_registry import register_document, prune_symbol_documents
from rag.retriever import retriever

RAW_DIR = Path("rag_data/raw")
RAW_DIR.mkdir(parents=True, exist_ok=True)


def _parse_text_file(file_path: str) -> str | None:
    ext = Path(file_path).suffix.lower()
    try:
        if ext in {".html", ".htm", ".txt", ".md"}:
            from markitdown import MarkItDown

            result = MarkItDown().convert(file_path)
            text = (result.text_content or "").strip()
            return text or None
    except Exception:
        pass
    try:
        return Path(file_path).read_text(encoding="utf-8", errors="ignore").strip() or None
    except Exception:
        return None


def parse_file_to_chunks(
    file_path: str,
    metadata: dict[str, str],
    doc_type: str = "annual_report",
) -> list[dict[str, Any]]:
    ext = Path(file_path).suffix.lower()
    if ext == ".pdf":
        return parse_and_chunk(file_path, metadata, doc_type=doc_type)
    text = _parse_text_file(file_path)
    if not text:
        return []
    return chunk_document(doc_type, text, metadata)


def ingest_chunks(
    chunks: list[dict[str, Any]],
    *,
    max_docs_per_symbol: int | None = 20,
    user_session_id: str = "",
) -> int:
    if not chunks:
        return 0
    if user_session_id:
        for c in chunks:
            c["user_session_id"] = user_session_id
    written = retriever.add_document_chunks(chunks)
    symbol = (chunks[0].get("symbol") or "").upper()
    doc_id = chunks[0].get("doc_id", "")
    publish_date = chunks[0].get("publish_date", "")
    chunk_ids = [c.get("chunk_id", "") for c in chunks if c.get("chunk_id")]
    if doc_id and symbol and written:
        register_document(symbol, doc_id, publish_date, chunk_ids)
    if max_docs_per_symbol and symbol:
        prune_symbol_documents(symbol, max_docs=max_docs_per_symbol)
    return written


def ingest_file(
    file_path: str,
    metadata: dict[str, str],
    doc_type: str = "annual_report",
    *,
    max_docs_per_symbol: int | None = 20,
    user_session_id: str = "",
) -> int:
    chunks = parse_file_to_chunks(file_path, metadata, doc_type=doc_type)
    return ingest_chunks(
        chunks,
        max_docs_per_symbol=max_docs_per_symbol,
        user_session_id=user_session_id,
    )


def ingest_text(
    text: str,
    metadata: dict[str, str],
    doc_type: str = "news",
    *,
    max_docs_per_symbol: int | None = 20,
) -> int:
    if not text.strip():
        return 0
    if not metadata.get("doc_id"):
        metadata = {**metadata, "doc_id": f"{metadata.get('symbol', 'UNK')}_{doc_type}_{uuid.uuid4().hex[:8]}"}
    if not metadata.get("publish_date"):
        metadata = {**metadata, "publish_date": datetime.utcnow().isoformat()}
    chunks = chunk_document(doc_type, text, metadata)
    return ingest_chunks(chunks, max_docs_per_symbol=max_docs_per_symbol)


def save_raw_bytes(symbol: str, source: str, ext: str, content: bytes) -> str:
    sub = RAW_DIR / source / symbol.upper().replace(".", "_")
    sub.mkdir(parents=True, exist_ok=True)
    path = sub / f"{uuid.uuid4().hex[:10]}{ext}"
    path.write_bytes(content)
    return str(path)
