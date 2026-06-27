"""Phase 3 unit tests: RRF, recency weighting, doc retention."""
from __future__ import annotations

import uuid
from datetime import date, timedelta
from pathlib import Path
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from rag.retriever import recency_weight, rrf_fusion, RRF_K


def test_recency_weight_buckets():
    today = date.today().isoformat()
    old = (date.today() - timedelta(days=400)).isoformat()
    mid = (date.today() - timedelta(days=120)).isoformat()
    assert recency_weight(today) == 1.0
    assert recency_weight(mid) == 0.7
    assert recency_weight(old) == 0.3
    assert recency_weight(None) == 0.7


def test_rrf_fusion_merges_rankings():
    fused = rrf_fusion(
        {
            "vector": ["a", "b", "c"],
            "fts": ["b", "d", "a"],
        },
        k=RRF_K,
    )
    ids = [item[0] for item in fused]
    assert ids[0] in {"a", "b"}
    assert "d" in ids
    scores = dict(fused)
    assert scores["b"] > scores["c"]


def test_doc_registry_prune_keeps_latest(tmp_path, monkeypatch):
    from rag import doc_registry

    db_path = tmp_path / "registry.db"
    monkeypatch.setattr(doc_registry, "REGISTRY_DB", db_path)

    symbol = f"PRUNE_{uuid.uuid4().hex[:6].upper()}"
    for i in range(22):
        doc_registry.register_document(
            symbol,
            f"{symbol}_doc_{i:02d}",
            f"2024-{i+1:02d}-01",
            [f"chunk_{i}"],
        )

    evicted = doc_registry.prune_symbol_documents(symbol, max_docs=20)
    remaining = doc_registry.list_documents(symbol)
    assert len(evicted) == 2
    assert len(remaining) == 20
    assert remaining[-1]["doc_id"].endswith("_21")


@pytest.fixture(scope="module")
def retriever():
    from rag.retriever import retriever as r

    if not r.vectorstore:
        pytest.skip("FAISS vectorstore not initialized")
    return r


def test_hybrid_retrieve_returns_chunks(retriever):
    run_id = uuid.uuid4().hex[:8]
    symbol = f"HYBRID_{run_id.upper()}"
    marker = f"HYBRID_MARKER_{run_id}"
    chunk_id = f"{symbol}_news_{run_id}_c0"
    chunks = [
        {
            "chunk_id": chunk_id,
            "content": f"{marker} hybrid retrieval validates vector and fts fusion pipeline.",
            "symbol": symbol,
            "source": "pytest",
            "doc_id": f"{symbol}_news_{run_id}",
            "doc_type": "news",
            "section": "",
            "page": "",
            "publish_date": date.today().isoformat(),
            "report_period": "",
            "contains_table": False,
            "language": "en",
        }
    ]
    written = retriever.add_document_chunks(chunks)
    assert written >= 1

    results = retriever.hybrid_retrieve(
        query=f"{marker} hybrid retrieval",
        symbol=symbol,
        k=5,
    )
    assert results
    assert any(marker in r.get("content", "") for r in results)
