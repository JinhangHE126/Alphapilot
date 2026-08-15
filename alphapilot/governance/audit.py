"""Audit record assembly helpers for analysis request lifecycle."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from db.repository import create_audit_record, update_audit_record


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")


def start_analysis_audit(
    request_id: str,
    *,
    analysis_id: int,
    session_id: str | None,
    user_id: int,
    stock_symbol: str,
) -> dict[str, Any]:
    """Create the audit row when an analysis request begins."""
    return create_audit_record(
        request_id,
        analysis_id=analysis_id,
        session_id=session_id,
        user_id=user_id,
        stock_symbol=(stock_symbol or "").upper(),
    )


def complete_analysis_audit(
    request_id: str,
    *,
    final_report: str | None = None,
    guard_check: dict[str, Any] | None = None,
    citations: dict[str, Any] | None = None,
    stock_symbol: str = "",
    status: str = "completed",
) -> dict[str, Any] | None:
    """
    Patch audit fields after analysis finishes (success or failure).

    Does not invent model/prompt versions yet — those land in a later P0 step.
    """
    from governance.claim_validation import validate_claims

    citations = citations if isinstance(citations, dict) else {}
    guard_check = guard_check if isinstance(guard_check, dict) else None
    evidence = None
    if guard_check:
        ep = guard_check.get("evidence_packet")
        if isinstance(ep, dict):
            evidence = ep

    symbol = (stock_symbol or "").strip().upper()
    if not symbol and isinstance(evidence, dict):
        symbol = str(evidence.get("symbol") or "").strip().upper()

    claim = validate_claims(
        final_report=final_report or "",
        evidence_packet=evidence,
        citations=citations,
        stock_symbol=symbol,
    )

    risk_flags: list[str] = []
    if status == "failed":
        risk_flags.append("ANALYSIS_FAILED")
    if guard_check and guard_check.get("is_valid") is False:
        risk_flags.append("GUARD_INVALID")
        for issue in guard_check.get("issues") or []:
            if isinstance(issue, str) and issue:
                risk_flags.append(issue[:120])
    for item in claim.get("blocking_issues") or []:
        code = item.get("code") if isinstance(item, dict) else None
        if code and code not in risk_flags:
            risk_flags.append(code)

    return update_audit_record(
        request_id,
        timestamp_completed=_utc_now(),
        generated_output=final_report,
        guard_result=guard_check,
        cited_chunk_ids=citations.get("chunk_ids") or [],
        citation_validation=claim.get("citation_validation"),
        evidence_packet_snapshot=evidence,
        risk_flags=risk_flags,
    )


def get_request_id(http_request: Any) -> str:
    """Read request_id from middleware-populated request.state, with fallback."""
    state = getattr(http_request, "state", None)
    rid = getattr(state, "request_id", None) if state is not None else None
    if rid:
        return str(rid)
    import uuid

    return str(uuid.uuid4())


def record_security_rejection(
    request_id: str,
    *,
    risk_flags: list[str],
) -> dict[str, Any] | None:
    """Persist blocked-input outcome to audit trail."""
    clean_flags: list[str] = []
    for flag in risk_flags:
        f = str(flag).strip()
        if f and f not in clean_flags:
            clean_flags.append(f)
    return update_audit_record(
        request_id,
        timestamp_completed=_utc_now(),
        generated_output=None,
        guard_result={
            "is_valid": False,
            "issues": ["INPUT_SECURITY_BLOCKED"],
        },
        risk_flags=clean_flags,
    )
