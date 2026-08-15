"""Citation and unsupported-claim validation for research conclusions.

Deterministic Day-1 checks. Blocking issues should prevent submit-for-review
once wired into governance/approvals.py.
"""
from __future__ import annotations

import re
from typing import Any

from services.citations import build_citations

_KEYWORD_FIELD_MAP: dict[str, str] = {
    "current price": "current_price",
    "股价": "current_price",
    "价格": "current_price",
    "price": "current_price",
    "rsi": "rsi_14",
    "macd": "macd",
    "volatility": "volatility_20d_annualized",
    "波动率": "volatility_20d_annualized",
    "pe ratio": "pe_ratio",
    "p/e": "pe_ratio",
    "市盈率": "pe_ratio",
    "pb ratio": "pb_ratio",
    "p/b": "pb_ratio",
    "市净率": "pb_ratio",
    "market cap": "market_cap",
    "市值": "market_cap",
    "revenue growth": "revenue_growth_yoy",
    "营收增长": "revenue_growth_yoy",
    "eps growth": "eps_growth_yoy",
    "eps增长": "eps_growth_yoy",
}

_MATERIAL_CLAIM_PATTERNS = [
    re.compile(r"\b(buy|sell|hold)\b", re.IGNORECASE),
    re.compile(r"买入|卖出|持有"),
    re.compile(r"目标价|target\s*price|price\s*target", re.IGNORECASE),
    re.compile(r"强烈推荐|建议买入|建议卖出"),
    re.compile(r"估值偏高|估值偏低|undervalued|overvalued", re.IGNORECASE),
]

_TARGET_PRICE_PATTERNS = [
    re.compile(r"\btarget\s*price\b", re.IGNORECASE),
    re.compile(r"目标价"),
    re.compile(r"\bprice\s*target\b", re.IGNORECASE),
]

_NEGATION = re.compile(
    r"缺少|缺乏|缺失|无法|不提供|禁止|不允许|不得|没有|不可用|不可获取|不可计算|无意义|"
    r"missing|not available|no data|unavailable|do not|does not|not provide|n/?a\b",
    re.IGNORECASE,
)

_JSON_BLOCK = re.compile(r"```(?:json)?\s*[\s\S]*?\s*```")


def _strip_machine_json_blocks(text: str) -> str:
    if not text:
        return ""
    return _JSON_BLOCK.sub("", text).strip()


def _clean_report_text(final_report: str) -> str:
    text = _strip_machine_json_blocks(final_report or "")
    lines = text.split("\n")
    clean_lines = [ln for ln in lines if not _NEGATION.search(ln)]
    return "\n".join(clean_lines)


def _available_fields(evidence_packet: dict[str, Any] | None) -> set[str]:
    if not evidence_packet or not isinstance(evidence_packet, dict):
        return set()
    facts = evidence_packet.get("facts") or []
    fields: set[str] = set()
    for fact in facts:
        if isinstance(fact, dict) and fact.get("field"):
            fields.add(str(fact["field"]))
    return fields


def _document_evidence(evidence_packet: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not evidence_packet or not isinstance(evidence_packet, dict):
        return []
    docs = evidence_packet.get("document_evidence") or []
    if not isinstance(docs, list):
        return []
    return [d for d in docs if isinstance(d, dict)]


def _has_material_claim(text: str) -> bool:
    return any(p.search(text) for p in _MATERIAL_CLAIM_PATTERNS)


def _issue(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def validate_claims(
    *,
    final_report: str,
    evidence_packet: dict[str, Any] | None,
    citations: dict[str, Any] | None = None,
    stock_symbol: str = "",
) -> dict[str, Any]:
    """
    Combine citation validation with unsupported-claim checks.

    Returns:
      ok, blocking_issues, warnings, citation_validation
    """
    cit = citations if isinstance(citations, dict) else build_citations(
        final_report or "",
        evidence_packet if isinstance(evidence_packet, dict) else None,
    )
    citation_validation = dict(cit.get("validation") or {})
    blocking_issues: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    # A) Citation markers
    if citation_validation.get("missing_citations"):
        blocking_issues.append(
            _issue(
                "MISSING_CITATION",
                "Document evidence present but report has no valid [doc:N] citations",
            )
        )
    for bad in citation_validation.get("invalid_citations") or []:
        blocking_issues.append(
            _issue("INVALID_CITATION", f"Invalid citation marker: {bad}")
        )

    clean_text = _clean_report_text(final_report or "")
    lower = clean_text.lower()
    cited_count = int(citation_validation.get("cited_count") or 0)
    retrieved_count = int(citation_validation.get("retrieved_count") or 0)

    # B) Material conclusions require citations when docs were retrieved
    if retrieved_count > 0 and cited_count == 0 and _has_material_claim(clean_text):
        # Avoid duplicate MISSING_CITATION if already flagged
        if not any(i["code"] == "MISSING_CITATION" for i in blocking_issues):
            blocking_issues.append(
                _issue(
                    "MISSING_CITATION",
                    "Material investment conclusion requires valid [doc:N] citation",
                )
            )

    # C) Unsupported field / target-price claims
    available = _available_fields(evidence_packet)
    seen_field_issues: set[str] = set()
    for keyword, required_field in _KEYWORD_FIELD_MAP.items():
        if keyword in lower and required_field not in available:
            key = f"{keyword}:{required_field}"
            if key in seen_field_issues:
                continue
            seen_field_issues.add(key)
            code = (
                "UNSUPPORTED_NUMERIC_CLAIM"
                if required_field
                in {
                    "current_price",
                    "pe_ratio",
                    "pb_ratio",
                    "market_cap",
                    "revenue_growth_yoy",
                    "eps_growth_yoy",
                    "rsi_14",
                    "macd",
                    "volatility_20d_annualized",
                }
                else "UNSUPPORTED_CLAIM"
            )
            blocking_issues.append(
                _issue(
                    code,
                    f"Ungrounded claim: mentions '{keyword}' but Evidence Packet "
                    f"has no field '{required_field}'",
                )
            )

    if any(p.search(lower) for p in _TARGET_PRICE_PATTERNS):
        blocking_issues.append(
            _issue(
                "UNSUPPORTED_NUMERIC_CLAIM",
                "Ungrounded claim: target price statement is not allowed unless "
                "explicitly grounded in Evidence Packet",
            )
        )

    # D) Symbol mismatch on document evidence
    symbol = (stock_symbol or "").strip().upper()
    if symbol:
        for dc in _document_evidence(evidence_packet):
            doc_symbol = str(dc.get("symbol") or "").strip().upper()
            if doc_symbol and doc_symbol != symbol:
                blocking_issues.append(
                    _issue(
                        "SYMBOL_MISMATCH",
                        f"Document evidence symbol={doc_symbol} does not match "
                        f"requested symbol={symbol}",
                    )
                )
                break

    # Deduplicate identical code+message pairs while preserving order
    deduped: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in blocking_issues:
        key = (item["code"], item["message"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)

    ok = len(deduped) == 0
    citation_validation = {
        **citation_validation,
        "claim_ok": ok,
        "blocking_issues": deduped,
    }

    return {
        "ok": ok,
        "blocking_issues": deduped,
        "warnings": warnings,
        "citation_validation": citation_validation,
    }


__all__ = ["validate_claims"]
