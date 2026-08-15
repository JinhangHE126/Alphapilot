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
    status: str = "completed",
) -> dict[str, Any] | None:
    """
    Patch audit fields after analysis finishes (success or failure).

    Does not invent model/prompt versions yet — those land in a later P0 step.
    """
    citations = citations if isinstance(citations, dict) else {}
    guard_check = guard_check if isinstance(guard_check, dict) else None
    evidence = None
    if guard_check:
        ep = guard_check.get("evidence_packet")
        if isinstance(ep, dict):
            evidence = ep

    risk_flags: list[str] = []
    if status == "failed":
        risk_flags.append("ANALYSIS_FAILED")
    if guard_check and guard_check.get("is_valid") is False:
        risk_flags.append("GUARD_INVALID")
        for issue in guard_check.get("issues") or []:
            if isinstance(issue, str) and issue:
                risk_flags.append(issue[:120])

    return update_audit_record(
        request_id,
        timestamp_completed=_utc_now(),
        generated_output=final_report,
        guard_result=guard_check,
        cited_chunk_ids=citations.get("chunk_ids") or [],
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
