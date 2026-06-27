"""
RAG 文档管线回归测试：ingest → retrieve(k=5) → evidence_packet 非空。

用法:
    cd alphapilot
    pytest test/test_rag_e2e_pipeline.py -v
"""
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
        pytest.skip("FAISS vectorstore not initialized (check rag_data/faiss_index)")
    return r


def test_pdf_env_reports_capabilities():
    from knowledge.pdf_env import check_pdf_parse_dependencies

    caps = check_pdf_parse_dependencies()
    assert isinstance(caps["text_extraction_ready"], bool)
    assert isinstance(caps["table_extraction_ready"], bool)
    assert caps["text_extraction_ready"] is True, (
        "CI/dev env should have markitdown or pymupdf; "
        "run: pip install markitdown pymupdf"
    )


def test_ingest_retrieve_and_evidence_packet(retriever):
    """模拟 upload 入库后的 workflow 文档证据加载路径。"""
    from graph.document_evidence import attach_document_evidence
    from schemas.evidence_packet import Coverage, EvidencePacket

    run_id = uuid.uuid4().hex[:10]
    symbol = f"RAGE2E_{run_id.upper()}"
    marker = f"E2E_RAG_MARKER_{run_id}"
    doc_id = f"{symbol}_annual_report_{run_id}"
    chunk_id = f"{doc_id}_c0"

    chunks = [
        {
            "chunk_id": chunk_id,
            "content": (
                f"{marker} Management discussion: autonomous driving capex "
                "is expected to increase materially in the next fiscal year."
            ),
            "symbol": symbol,
            "source": "pytest_upload",
            "doc_id": doc_id,
            "doc_type": "annual_report",
            "section": "MD&A",
            "page": "12",
            "publish_date": "2025-01-01",
            "report_period": "FY2024",
            "contains_table": False,
            "language": "en",
        }
    ]

    written = retriever.add_document_chunks(chunks)
    assert written >= 1, "add_document_chunks should persist at least one chunk"

    query = f"{symbol} {marker} autonomous driving"
    results = retriever.retrieve_doc_chunks(query=query, symbol=symbol, k=5)
    assert len(results) >= 1, (
        f"retrieve_doc_chunks(k=5) returned 0 for symbol={symbol}; "
        "regression in post-filter / fetch_k logic"
    )
    assert any(marker in r.get("content", "") for r in results)

    packet = EvidencePacket(
        symbol=symbol,
        request_type="comprehensive_analysis",
        is_cold_start=False,
        coverage=Coverage(
            rag_context="available",
            market_data="available",
            fundamental_data="available",
            news_data="available",
            filings="missing",
            document_evidence="missing",
        ),
        facts=[],
    )
    attach_document_evidence(packet, symbol=symbol, query=query, k=5)

    assert packet.document_evidence, "evidence_packet.document_evidence must be non-empty"
    assert packet.coverage.document_evidence == "available"
    assert any(marker in dc.content for dc in packet.document_evidence)
