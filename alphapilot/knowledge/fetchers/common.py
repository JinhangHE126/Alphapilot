"""Shared ingest helpers for automated document fetchers."""
from __future__ import annotations

import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from knowledge.pdf_parser import parse_and_chunk
from knowledge.ingest_service import upsert_document
from rag.retriever import retriever

RAW_DIR = Path("rag_data/raw")
RAW_DIR.mkdir(parents=True, exist_ok=True)


def strip_html(text: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def make_doc_id(symbol: str, doc_type: str, suffix: str = "") -> str:
    token = suffix or uuid.uuid4().hex[:10]
    safe = re.sub(r"[^\w.\-]+", "_", token)
    return f"{symbol.upper()}_{doc_type}_{safe}"


def base_metadata(
    symbol: str,
    doc_type: str,
    source: str,
    *,
    doc_id: str | None = None,
    publish_date: str | None = None,
    report_period: str = "",
    language: str = "en",
    title: str = "",
) -> dict[str, Any]:
    now = datetime.utcnow().isoformat()
    return {
        "doc_id": doc_id or make_doc_id(symbol, doc_type),
        "symbol": symbol.upper(),
        "source": source,
        "doc_type": doc_type,
        "publish_date": publish_date or now,
        "report_period": report_period,
        "language": language,
        "title": title,
        "page": "",
    }


def ingest_text_document(
    text: str,
    metadata: dict[str, Any],
    doc_type: str,
) -> int:
    if not text or not text.strip():
        return 0
    result = upsert_document(doc_type, metadata, text.strip())
    return int(result.get("chunks", 0) or 0)


def ingest_file_document(
    file_path: str | Path,
    metadata: dict[str, Any],
    doc_type: str,
) -> int:
    path = Path(file_path)
    if not path.is_file():
        return 0
    chunks = parse_and_chunk(str(path), metadata, doc_type=doc_type)
    if not chunks:
        return 0
    return retriever.add_document_chunks(chunks)


def save_raw_bytes(symbol: str, doc_type: str, ext: str, content: bytes) -> Path:
    file_id = uuid.uuid4().hex[:10]
    dest = RAW_DIR / f"{symbol.upper()}_{doc_type}_{file_id}{ext}"
    dest.write_bytes(content)
    return dest
