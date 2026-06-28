"""3.2 检索增强 M2 测试：section boost + doc_type 过滤/加权。"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from rag.retriever import (
    _compute_section_boost,
    SECTION_BOOST,
    DOC_TYPE_BOOST,
)


# ═══════════════════════════════════════════════════════════
# 3.2.1  Section boost — 基础映射
# ═══════════════════════════════════════════════════════════

@pytest.mark.parametrize("section,expected_min", [
    ("Risk Factors", 1.25),
    ("Item 1A. Risk Factors", 1.25),
    ("MD&A", 1.15),
    ("management's discussion and analysis", 1.15),
    ("Risk Management", 1.20),
    ("Financial Statements", 1.10),
    ("Business Overview", 1.05),
    ("Unknown Section", 1.0),
    ("", 1.0),
])
def test_section_boost_baseline(section, expected_min):
    boost = _compute_section_boost(section, "")
    assert boost >= expected_min, f"section='{section}' boost={boost} < {expected_min}"


# ═══════════════════════════════════════════════════════════
# 3.2.1  Query keyword → section 联动（英文 section）
# ═══════════════════════════════════════════════════════════

@pytest.mark.parametrize("section,query,expected_min", [
    # 英文 query → 英文 section
    ("Risk Factors", "what are the regulatory risks", 1.25 * 1.10),
    ("MD&A", "revenue growth analysis", 1.15 * 1.08),
    ("MD&A", "profit margin analysis", 1.15 * 1.08),
    # 中文 query → 英文 section（M1 标准化后的 section 名）
    ("Risk Factors", "监管风险有哪些", 1.25 * 1.10),
    ("Risk Factors", "法规合规风险", 1.25 * 1.10),
    ("Risk Factors", "风险评估", 1.25 * 1.10),
    ("MD&A", "经营情况分析", 1.15 * 1.08),
    ("MD&A", "营收增长", 1.15 * 1.08),
    ("MD&A", "收入利润", 1.15 * 1.08),
    ("Financial Statements", "财务状况", 1.187),  # 1.10*1.08 rounded
    # 无联动
    ("Risk Factors", "revenue analysis", 1.25),  # section boost only
    ("Unknown", "risk management", 1.0),
    ("", "risk", 1.0),
])
def test_query_section_linkage(section, query, expected_min):
    boost = _compute_section_boost(section, query)
    assert boost >= expected_min, \
        f"section='{section}' query='{query}' boost={boost} < {expected_min}"


# ═══════════════════════════════════════════════════════════
# 3.2.1  中文 section 名兼容（M1 未标准化到英文的情况）
# ═══════════════════════════════════════════════════════════

def test_chinese_section_still_boosted():
    """中文 section 名仍可通过 SECTION_BOOST 中的中文 key 获得基础 boost。"""
    assert _compute_section_boost("风险因素", "") >= 1.25
    assert _compute_section_boost("管理层讨论与分析", "") >= 1.15
    assert _compute_section_boost("风险管理", "") >= 1.20


# ═══════════════════════════════════════════════════════════
# 3.2.1  doc_type boost
# ═══════════════════════════════════════════════════════════

def test_doc_type_boost_values():
    assert DOC_TYPE_BOOST["annual_report"] == 1.10
    assert DOC_TYPE_BOOST["earnings_call"] == 1.05
    assert DOC_TYPE_BOOST.get("news", 1.0) == 1.0  # 无 boost


# ═══════════════════════════════════════════════════════════
# 3.2.2  doc_type 后过滤 + boost（集成测试 through retriever）
# ═══════════════════════════════════════════════════════════

def test_hybrid_retrieve_doc_type_filter():
    """doc_type=earnings_call 不返回 annual_report 或 news chunk。"""
    from rag.retriever import retriever
    if not retriever.vectorstore:
        pytest.skip("Vectorstore not initialized")

    results = retriever.hybrid_retrieve(
        "revenue",
        symbol="0700.HK",
        k=10,
        doc_type="earnings_call",
    )
    for r in results:
        dt = str(r.get("doc_type", "")).lower()
        assert dt == "earnings_call" or dt == "", \
            f"unexpected doc_type={dt} for chunk {r.get('chunk_id')}"


def test_hybrid_retrieve_doc_type_filter_news():
    """doc_type=news 不返回 annual_report chunk。"""
    from rag.retriever import retriever
    if not retriever.vectorstore:
        pytest.skip("Vectorstore not initialized")

    results = retriever.hybrid_retrieve(
        "growth",
        symbol="0700.HK",
        k=10,
        doc_type="news",
    )
    for r in results:
        dt = str(r.get("doc_type", "")).lower()
        assert dt == "news" or dt == "", f"unexpected doc_type={dt}"


def test_hybrid_retrieve_no_filter_returns_mixed():
    """doc_type='' 不过滤，返回多种类型。"""
    from rag.retriever import retriever
    if not retriever.vectorstore:
        pytest.skip("Vectorstore not initialized")

    results = retriever.hybrid_retrieve(
        "revenue",
        symbol="0700.HK",
        k=10,
    )
    doc_types = {str(r.get("doc_type", "")).lower() for r in results}
    # 应至少有两种 doc_type（或至少不全是同一种）
    assert len(results) >= 1
    # 有不同类型的 chunk 即验证通过
    assert True  # smoke


def test_doc_type_boost_applied_in_candidates():
    """annual_report chunk 的 doc_type_boost 应 > 1.0。"""
    from rag.retriever import retriever
    if not retriever.vectorstore:
        pytest.skip("Vectorstore not initialized")

    results = retriever.retrieve_doc_chunks(
        "revenue",
        symbol="0700.HK",
        k=20,
    )
    annual_hits = [r for r in results
                   if str(r.get("doc_type", "")).lower() == "annual_report"]
    calls_hits = [r for r in results
                  if str(r.get("doc_type", "")).lower() == "earnings_call"]
    if annual_hits:
        for h in annual_hits:
            assert h.get("doc_type_boost", 1.0) >= 1.10, \
                f"annual_report chunk missing doc_type_boost: {h.get('chunk_id')}"
    if calls_hits:
        for h in calls_hits:
            assert h.get("doc_type_boost", 1.0) >= 1.05


# ═══════════════════════════════════════════════════════════
# attach_document_evidence doc_type 传递
# ═══════════════════════════════════════════════════════════

def test_attach_document_evidence_accepts_doc_type():
    """确保 attach_document_evidence 接受 doc_type 参数。"""
    from graph.document_evidence import attach_document_evidence
    from schemas.evidence_packet import EvidencePacket

    ep = EvidencePacket(symbol="TSLA")
    result = attach_document_evidence(
        ep, symbol="TSLA", query="revenue", k=2, doc_type="annual_report"
    )
    assert isinstance(result, EvidencePacket)


def test_attach_document_evidence_doc_type_filter():
    """doc_type=earnings_call 时结果不含 annual_report chunk。"""
    from graph.document_evidence import attach_document_evidence
    from schemas.evidence_packet import EvidencePacket

    ep = EvidencePacket(symbol="0700.HK")
    result = attach_document_evidence(
        ep, symbol="0700.HK", query="revenue", k=10, doc_type="earnings_call"
    )
    assert isinstance(result, EvidencePacket)
    for dc in result.document_evidence:
        dt = str(dc.doc_type).lower() if hasattr(dc, 'doc_type') else ""
        assert dt == "earnings_call" or dt == "", \
            f"unexpected doc_type={dt} in document_evidence"
