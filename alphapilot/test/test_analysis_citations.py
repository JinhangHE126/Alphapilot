"""3.3.4 Audit Trail 测试：解析 [doc:1]、落库、API 回读。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.citations import build_citations


# ═══════════════════════════════════════════════════════════
# [doc:N] marker 解析
# ═══════════════════════════════════════════════════════════

def test_extract_doc_markers_single():
    report = "According to the annual report [doc:1], revenue grew 30%."
    ep = {
        "document_evidence": [
            {"chunk_id": "AAPL_annual_Risk_Factors_p45_i01", "doc_id": "AAPL_annual_2024",
             "section": "Risk Factors", "source": "SEC"},
        ]
    }
    cit = build_citations(report, ep)
    assert cit["doc_markers"] == ["doc:1"]
    assert cit["chunk_ids"] == ["AAPL_annual_Risk_Factors_p45_i01"]
    assert len(cit["evidence_snapshot"]) == 1
    assert cit["evidence_snapshot"][0]["section"] == "Risk Factors"


def test_extract_doc_markers_multiple():
    report = "Risk factors [doc:1] show volatility, while MD&A [doc:2] shows strong growth."
    ep = {
        "document_evidence": [
            {"chunk_id": "CHUNK_A", "doc_id": "doc_a", "section": "Risk Factors", "source": "SEC"},
            {"chunk_id": "CHUNK_B", "doc_id": "doc_b", "section": "MD&A", "source": "SEC"},
            {"chunk_id": "CHUNK_C", "doc_id": "doc_c", "section": "Financial Statements", "source": "SEC"},
        ]
    }
    cit = build_citations(report, ep)
    assert cit["doc_markers"] == ["doc:1", "doc:2"]
    assert cit["chunk_ids"] == ["CHUNK_A", "CHUNK_B"]
    assert len(cit["evidence_snapshot"]) == 2


def test_extract_doc_markers_dedup():
    """同一 [doc:N] 引用多次不重复记录。"""
    report = "As seen in [doc:1], and also [doc:1] confirms."
    ep = {
        "document_evidence": [
            {"chunk_id": "CHUNK_A", "doc_id": "doc_a", "section": "Risk Factors", "source": "SEC"},
        ]
    }
    cit = build_citations(report, ep)
    assert cit["doc_markers"] == ["doc:1"]
    assert len(cit["chunk_ids"]) == 1


def test_extract_doc_markers_out_of_range():
    """[doc:99] 超出范围应被忽略。"""
    report = "See [doc:99] for details."
    ep = {
        "document_evidence": [
            {"chunk_id": "CHUNK_A", "doc_id": "doc_a", "section": "Risk Factors", "source": "SEC"},
        ]
    }
    cit = build_citations(report, ep)
    # 无合法 marker → 兜底全部 chunk_id
    assert cit["doc_markers"] is None
    assert cit["chunk_ids"] == ["CHUNK_A"]


def test_extract_doc_markers_case_insensitive():
    """[DOC:1] / [Doc:1] 均兼容。"""
    report = "See [DOC:1] and [Doc:2]."
    ep = {
        "document_evidence": [
            {"chunk_id": "CHUNK_A", "doc_id": "doc_a", "section": "Risk Factors", "source": "SEC"},
            {"chunk_id": "CHUNK_B", "doc_id": "doc_b", "section": "MD&A", "source": "SEC"},
        ]
    }
    cit = build_citations(report, ep)
    assert "doc:1" in (cit["doc_markers"] or [])
    assert "doc:2" in (cit["doc_markers"] or [])


def test_extract_doc_markers_with_spaces():
    """[doc: 1] 含空格也解析。"""
    report = "Data shows [doc: 1] and [doc :2]."
    ep = {
        "document_evidence": [
            {"chunk_id": "CHUNK_A", "doc_id": "doc_a", "section": "Risk Factors", "source": "SEC"},
            {"chunk_id": "CHUNK_B", "doc_id": "doc_b", "section": "MD&A", "source": "SEC"},
        ]
    }
    cit = build_citations(report, ep)
    assert "doc:1" in (cit["doc_markers"] or [])
    assert "doc:2" in (cit["doc_markers"] or [])


# ═══════════════════════════════════════════════════════════
# 兜底逻辑：无 [doc:N] 时保存所有 chunk_id
# ═══════════════════════════════════════════════════════════

def test_fallback_saves_all_chunks():
    report = "Analysis complete. No citations given."
    ep = {
        "document_evidence": [
            {"chunk_id": "CHUNK_A", "doc_id": "doc_a", "section": "Risk Factors", "source": "SEC"},
            {"chunk_id": "CHUNK_B", "doc_id": "doc_b", "section": "MD&A", "source": "SEC"},
        ]
    }
    cit = build_citations(report, ep)
    assert cit["doc_markers"] is None
    assert cit["chunk_ids"] == ["CHUNK_A", "CHUNK_B"]
    assert len(cit["evidence_snapshot"]) == 2


def test_empty_document_evidence():
    report = "No documents available."
    cit = build_citations(report, None)
    assert cit["chunk_ids"] == []
    assert cit["doc_markers"] is None
    assert cit["evidence_snapshot"] is None


def test_empty_report():
    cit = build_citations("", {"document_evidence": [
        {"chunk_id": "CHUNK_A", "doc_id": "doc_a", "section": "Risk Factors", "source": "SEC"},
    ]})
    assert cit["chunk_ids"] == ["CHUNK_A"]  # fallback
    assert cit["doc_markers"] is None


# ═══════════════════════════════════════════════════════════
# Repository 集成：save + get
# ═══════════════════════════════════════════════════════════

def test_save_and_get_citations():
    from db.models import get_connection
    from db.repository import (
        save_analysis_citations, get_analysis_citations,
    )

    # 创建临时用户和分析记录以满足 FK 约束
    with get_connection() as conn:
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute(
            "INSERT OR IGNORE INTO users (id, username, password_hash) VALUES (-999, '_test_cit', 'x')"
        )
        conn.execute(
            "INSERT OR IGNORE INTO analysis_history (id, user_id, stock_symbol, status) VALUES (-999, -999, 'TEST', 'completed')"
        )

    analysis_id = -999
    chunk_ids = ["CHUNK_A", "CHUNK_B"]
    doc_markers = ["doc:1", "doc:2"]
    snapshot = [
        {"chunk_id": "CHUNK_A", "doc_id": "doc_a", "section": "Risk Factors", "source": "SEC"},
        {"chunk_id": "CHUNK_B", "doc_id": "doc_b", "section": "MD&A", "source": "SEC"},
    ]

    save_analysis_citations(analysis_id, chunk_ids, doc_markers, snapshot)
    result = get_analysis_citations(analysis_id)
    assert result is not None
    assert isinstance(result["chunk_ids"], list)
    assert "CHUNK_A" in result["chunk_ids"]
    assert isinstance(result["doc_markers"], list)
    assert "doc:1" in result["doc_markers"]
    assert isinstance(result["evidence_snapshot"], list)
    assert result["evidence_snapshot"][0]["section"] == "Risk Factors"


def test_get_citations_nonexistent():
    from db.repository import get_analysis_citations
    assert get_analysis_citations(-99999) is None


def test_save_citations_overwrite():
    """再次保存覆盖旧数据。"""
    from db.models import get_connection
    from db.repository import save_analysis_citations, get_analysis_citations

    with get_connection() as conn:
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute(
            "INSERT OR IGNORE INTO users (id, username, password_hash) VALUES (-998, '_test_cit2', 'x')"
        )
        conn.execute(
            "INSERT OR IGNORE INTO analysis_history (id, user_id, stock_symbol, status) VALUES (-998, -998, 'TEST', 'completed')"
        )

    analysis_id = -998
    save_analysis_citations(analysis_id, ["OLD"], ["doc:1"], [{"chunk_id": "OLD"}])
    save_analysis_citations(analysis_id, ["NEW"], ["doc:2"], [{"chunk_id": "NEW"}])
    result = get_analysis_citations(analysis_id)
    assert result["chunk_ids"] == ["NEW"]


# ═══════════════════════════════════════════════════════════
# Schema 验证
# ═══════════════════════════════════════════════════════════

def test_citations_structure():
    """验证 citations 返回结构符合方案 schema。"""
    cit = build_citations(
        "Report with [doc:1]",
        {"document_evidence": [
            {"chunk_id": "AAPL_annual_Risk_Factors_p45_i01",
             "doc_id": "AAPL_annual_2024", "section": "Risk Factors", "source": "SEC"},
        ]}
    )
    # 方案 schema: {chunk_ids, doc_markers, evidence_snapshot}
    assert isinstance(cit["chunk_ids"], list)
    assert isinstance(cit["doc_markers"], list) or cit["doc_markers"] is None
    assert isinstance(cit["evidence_snapshot"], list) or cit["evidence_snapshot"] is None
    if cit["evidence_snapshot"]:
        snap = cit["evidence_snapshot"][0]
        assert "chunk_id" in snap
        assert "doc_id" in snap
        assert "section" in snap
        assert "source" in snap


# ═══════════════════════════════════════════════════════════
# evidence_packet SchemaChunk 兼容
# ═══════════════════════════════════════════════════════════

def test_citations_with_schema_chunk():
    """兼容 SchemaChunk 对象（Pydantic model）。"""
    from schemas.evidence_packet import DocumentChunk

    chunk = DocumentChunk(
        chunk_id="TSLA_annual_Risk_Factors_p30_i01",
        content="Tesla faces regulatory risk...",
        source="SEC",
        doc_id="TSLA_annual_2024",
        doc_type="annual_report",
        section="Risk Factors",
        page="30",
        contains_table=False,
    )
    report = "Tesla's regulatory exposure [doc:1] is significant."
    ep = {"document_evidence": [chunk.model_dump()]}

    cit = build_citations(report, ep)
    assert cit["chunk_ids"] == ["TSLA_annual_Risk_Factors_p30_i01"]
    assert cit["doc_markers"] == ["doc:1"]
    assert cit["evidence_snapshot"][0]["section"] == "Risk Factors"


# ═══════════════════════════════════════════════════════════
# API 回读模拟：save → get_analysis_detail + citations → 合并响应
# ═══════════════════════════════════════════════════════════

def test_history_api_returns_citations():
    """验证 GET /history/{id} 响应结构含 citations（模拟 API 组装逻辑）。"""
    from db.models import get_connection
    from db.repository import (
        save_analysis_citations, get_analysis_citations,
        get_analysis_detail, complete_analysis_record,
    )

    test_id = -997

    # 准备用户 + 分析记录
    with get_connection() as conn:
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute(
            "INSERT OR IGNORE INTO users (id, username, password_hash) VALUES (-997, '_test_hist', 'x')"
        )
        conn.execute(
            "INSERT OR IGNORE INTO analysis_history (id, user_id, stock_symbol, status, report) VALUES (-997, -997, 'TEST', 'completed', 'report with [doc:1]')"
        )

    # 写 citations
    save_analysis_citations(
        test_id,
        chunk_ids=["CHUNK_A"],
        doc_markers=["doc:1"],
        evidence_snapshot=[{"chunk_id": "CHUNK_A", "doc_id": "doc_a", "section": "Risk Factors", "source": "SEC"}],
    )

    # 模拟 API 端 GET /history/{id} 的组装逻辑
    record = get_analysis_detail(test_id, -997)
    assert record is not None

    citations = get_analysis_citations(test_id)
    assert citations is not None
    assert isinstance(citations["chunk_ids"], list)
    assert "CHUNK_A" in citations["chunk_ids"]
    assert isinstance(citations["doc_markers"], list)
    assert "doc:1" in citations["doc_markers"]

    # 组装为 API 响应格式
    response = {"id": test_id, **record, "events": [], "citations": citations}
    assert response["id"] == test_id
    assert response["citations"]["chunk_ids"] == ["CHUNK_A"]
    assert response["citations"]["doc_markers"] == ["doc:1"]


def test_history_api_citations_null_when_none():
    """无 citations 时 API 返回 citations=None。"""
    from db.repository import get_analysis_citations
    assert get_analysis_citations(-99999) is None
