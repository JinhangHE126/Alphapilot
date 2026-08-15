"""Day-1 claim validation: citations + unsupported claims."""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from governance.claim_validation import validate_claims


def _ep_with_docs(*, symbol: str = "AAPL", pe: float | None = 28.5) -> dict:
    facts = []
    if pe is not None:
        facts.append(
            {
                "field": "pe_ratio",
                "value": pe,
                "unit": "ratio",
                "period": "latest",
                "source": "yfinance",
                "as_of_date": "2026-01-01",
                "confidence": 0.9,
                "confidence_tier": "machine",
            }
        )
    return {
        "symbol": symbol,
        "facts": facts,
        "document_evidence": [
            {
                "chunk_id": "AAPL_risk_1",
                "doc_id": "AAPL_10k",
                "section": "Risk Factors",
                "source": "SEC",
                "symbol": symbol,
            }
        ],
    }


def test_valid_citation_and_grounded_field_passes():
    report = "According to filings [doc:1], the PE ratio remains elevated."
    result = validate_claims(
        final_report=report,
        evidence_packet=_ep_with_docs(),
        stock_symbol="AAPL",
    )
    assert result["ok"] is True
    assert result["blocking_issues"] == []
    assert result["citation_validation"]["claim_ok"] is True


def test_invalid_doc_marker_is_blocking():
    report = "See [doc:99] for growth details."
    result = validate_claims(
        final_report=report,
        evidence_packet=_ep_with_docs(),
        stock_symbol="AAPL",
    )
    assert result["ok"] is False
    codes = {i["code"] for i in result["blocking_issues"]}
    assert "INVALID_CITATION" in codes
    assert "MISSING_CITATION" in codes


def test_missing_citations_when_docs_present():
    report = "Analysis complete with no document markers."
    result = validate_claims(
        final_report=report,
        evidence_packet=_ep_with_docs(),
        stock_symbol="AAPL",
    )
    assert result["ok"] is False
    assert any(i["code"] == "MISSING_CITATION" for i in result["blocking_issues"])


def test_ungrounded_pe_claim_blocked():
    report = "The PE ratio looks cheap [doc:1]."
    ep = _ep_with_docs(pe=None)  # no pe_ratio fact
    result = validate_claims(
        final_report=report,
        evidence_packet=ep,
        stock_symbol="AAPL",
    )
    assert result["ok"] is False
    assert any(i["code"] == "UNSUPPORTED_NUMERIC_CLAIM" for i in result["blocking_issues"])


def test_target_price_statement_blocked():
    report = "We set a target price of 200 [doc:1]."
    result = validate_claims(
        final_report=report,
        evidence_packet=_ep_with_docs(),
        stock_symbol="AAPL",
    )
    assert result["ok"] is False
    assert any(i["code"] == "UNSUPPORTED_NUMERIC_CLAIM" for i in result["blocking_issues"])


def test_material_claim_without_citation_blocked():
    report = "Buy recommendation based on strong growth outlook."
    result = validate_claims(
        final_report=report,
        evidence_packet=_ep_with_docs(),
        stock_symbol="AAPL",
    )
    assert result["ok"] is False
    assert any(i["code"] == "MISSING_CITATION" for i in result["blocking_issues"])


def test_symbol_mismatch_blocked():
    report = "Risk factors [doc:1] remain elevated."
    ep = _ep_with_docs(symbol="TSLA")
    result = validate_claims(
        final_report=report,
        evidence_packet=ep,
        stock_symbol="AAPL",
    )
    assert result["ok"] is False
    assert any(i["code"] == "SYMBOL_MISMATCH" for i in result["blocking_issues"])


def test_no_docs_and_no_claims_ok():
    report = "Data summary only; insufficient evidence for recommendation."
    result = validate_claims(
        final_report=report,
        evidence_packet={"symbol": "AAPL", "facts": [], "document_evidence": []},
        stock_symbol="AAPL",
    )
    assert result["ok"] is True
