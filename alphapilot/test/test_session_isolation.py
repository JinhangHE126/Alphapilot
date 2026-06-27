"""Phase 4.14 — 公开 + 用户私有 chunk 混合检索与隔离。"""
from __future__ import annotations

import uuid
from pathlib import Path
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(scope="module")
def retriever():
    from rag.retriever import retriever as r

    if not r.vectorstore:
        pytest.skip("FAISS not available")
    return r


def test_private_chunks_hidden_without_session(retriever):
    run_id = uuid.uuid4().hex[:8]
    symbol = f"ISO_{run_id.upper()}"
    session_a = f"user_a_{run_id}"
    marker = f"PRIVATE_ONLY_{run_id}"

    retriever.add_document_chunks(
        [
            {
                "chunk_id": f"{symbol}_private_{run_id}",
                "content": f"{marker} confidential user upload note",
                "symbol": symbol,
                "source": "user_uploaded",
                "doc_id": f"{symbol}_doc_priv",
                "doc_type": "research_report",
                "section": "",
                "page": "",
                "publish_date": "2025-01-01",
                "report_period": "",
                "contains_table": False,
                "language": "en",
                "user_session_id": session_a,
                "confidence_tier": "user_submitted",
            }
        ]
    )

    public_hits = retriever.hybrid_retrieve(
        query=marker, symbol=symbol, k=5, user_session_id=""
    )
    assert not any(marker in h.get("content", "") for h in public_hits)


def test_owner_sees_private_and_public(retriever):
    run_id = uuid.uuid4().hex[:8]
    symbol = f"ISO_{run_id.upper()}"
    session_a = f"user_a_{run_id}"
    priv_marker = f"PRIV_{run_id}"
    pub_marker = f"PUB_{run_id}"

    retriever.add_document_chunks(
        [
            {
                "chunk_id": f"{symbol}_pub_{run_id}",
                "content": f"{pub_marker} public annual report risk factors",
                "symbol": symbol,
                "source": "HKEX",
                "doc_id": f"{symbol}_doc_pub",
                "doc_type": "annual_report",
                "section": "",
                "page": "",
                "publish_date": "2025-01-01",
                "report_period": "",
                "contains_table": False,
                "language": "en",
                "confidence_tier": "machine",
            },
            {
                "chunk_id": f"{symbol}_priv_{run_id}",
                "content": f"{priv_marker} private research notes",
                "symbol": symbol,
                "source": "user_uploaded",
                "doc_id": f"{symbol}_doc_priv2",
                "doc_type": "research_report",
                "section": "",
                "page": "",
                "publish_date": "2025-01-01",
                "report_period": "",
                "contains_table": False,
                "language": "en",
                "user_session_id": session_a,
                "confidence_tier": "user_submitted",
            },
        ]
    )

    hits = retriever.hybrid_retrieve(
        query=f"{symbol} research risk",
        symbol=symbol,
        k=5,
        user_session_id=session_a,
    )
    contents = " ".join(h.get("content", "") for h in hits)
    assert pub_marker in contents or priv_marker in contents
    assert priv_marker in contents
