"""Human-review state machine and publication gates."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from db.repository import (
    get_audit_record_by_analysis_id,
    update_audit_record,
)
from schemas.approval import ApprovalStatus, PublicationStatus


class ApprovalTransitionError(ValueError):
    """Raised when an approval action violates a state or validation gate."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")


def _audit_or_error(analysis_id: int) -> dict[str, Any]:
    audit = get_audit_record_by_analysis_id(analysis_id)
    if not audit:
        raise ApprovalTransitionError(
            "AUDIT_NOT_FOUND",
            f"No AI audit record exists for analysis_id={analysis_id}",
        )
    return audit


def _status(audit: dict[str, Any]) -> ApprovalStatus:
    try:
        return ApprovalStatus(audit.get("approval_status", ApprovalStatus.DRAFT.value))
    except ValueError as exc:
        raise ApprovalTransitionError(
            "INVALID_STORED_STATUS",
            f"Unknown approval status: {audit.get('approval_status')}",
        ) from exc


def _update(audit: dict[str, Any], **fields: Any) -> dict[str, Any]:
    updated = update_audit_record(str(audit["request_id"]), **fields)
    if not updated:
        raise ApprovalTransitionError(
            "AUDIT_UPDATE_FAILED",
            f"Could not update audit record for request_id={audit['request_id']}",
        )
    return updated


def _assert_review_gate(audit: dict[str, Any]) -> None:
    guard = audit.get("guard_result")
    if not isinstance(guard, dict) or guard.get("is_valid") is not True:
        raise ApprovalTransitionError(
            "GUARD_NOT_PASSED",
            "Guard validation must pass before submission for review",
        )

    validation = audit.get("citation_validation")
    if not isinstance(validation, dict):
        raise ApprovalTransitionError(
            "CLAIM_VALIDATION_MISSING",
            "Claim validation evidence is missing",
        )
    if validation.get("ok") is not True or validation.get("claim_ok") is not True:
        issues = validation.get("blocking_issues") or []
        raise ApprovalTransitionError(
            "CLAIM_VALIDATION_FAILED",
            f"Claim validation has blocking issues: {issues}",
        )


def submit_for_review(analysis_id: int) -> dict[str, Any]:
    """Move a valid draft (or revised report) into pending review."""
    audit = _audit_or_error(analysis_id)
    current = _status(audit)
    if current not in {
        ApprovalStatus.DRAFT,
        ApprovalStatus.REVISION_REQUESTED,
    }:
        raise ApprovalTransitionError(
            "INVALID_TRANSITION",
            f"Cannot submit {current.value} report for review",
        )
    _assert_review_gate(audit)
    return _update(
        audit,
        approval_status=ApprovalStatus.PENDING_REVIEW,
        human_reviewer=None,
        review_comments=None,
        approval_timestamp=None,
        publication_status=PublicationStatus.NOT_PUBLISHED,
    )


def _review(
    analysis_id: int,
    *,
    target: ApprovalStatus,
    reviewer: str,
    comments: str | None = None,
) -> dict[str, Any]:
    audit = _audit_or_error(analysis_id)
    current = _status(audit)
    if current is not ApprovalStatus.PENDING_REVIEW:
        raise ApprovalTransitionError(
            "INVALID_TRANSITION",
            f"Cannot move {current.value} report to {target.value}",
        )
    reviewer = (reviewer or "").strip()
    if not reviewer:
        raise ApprovalTransitionError(
            "REVIEWER_REQUIRED",
            "An authenticated reviewer identity is required",
        )
    comments = (comments or "").strip() or None
    if target in {
        ApprovalStatus.REJECTED,
        ApprovalStatus.REVISION_REQUESTED,
    } and not comments:
        raise ApprovalTransitionError(
            "REVIEW_COMMENTS_REQUIRED",
            f"Review comments are required for {target.value}",
        )
    return _update(
        audit,
        approval_status=target,
        human_reviewer=reviewer,
        review_comments=comments,
        approval_timestamp=_utc_now(),
        publication_status=PublicationStatus.NOT_PUBLISHED,
    )


def approve(
    analysis_id: int,
    *,
    reviewer: str,
    comments: str | None = None,
) -> dict[str, Any]:
    return _review(
        analysis_id,
        target=ApprovalStatus.APPROVED,
        reviewer=reviewer,
        comments=comments,
    )


def reject(
    analysis_id: int,
    *,
    reviewer: str,
    comments: str | None,
) -> dict[str, Any]:
    return _review(
        analysis_id,
        target=ApprovalStatus.REJECTED,
        reviewer=reviewer,
        comments=comments,
    )


def request_revision(
    analysis_id: int,
    *,
    reviewer: str,
    comments: str | None,
) -> dict[str, Any]:
    return _review(
        analysis_id,
        target=ApprovalStatus.REVISION_REQUESTED,
        reviewer=reviewer,
        comments=comments,
    )


def publish(analysis_id: int) -> dict[str, Any]:
    """Publish only a human-approved report."""
    audit = _audit_or_error(analysis_id)
    current = _status(audit)
    if current is not ApprovalStatus.APPROVED:
        raise ApprovalTransitionError(
            "NOT_APPROVED",
            f"Only approved reports can be published; current={current.value}",
        )
    if not audit.get("human_reviewer"):
        raise ApprovalTransitionError(
            "REVIEWER_REQUIRED",
            "Approved report has no recorded reviewer",
        )
    return _update(
        audit,
        publication_status=PublicationStatus.PUBLISHED,
    )


__all__ = [
    "ApprovalTransitionError",
    "submit_for_review",
    "approve",
    "reject",
    "request_revision",
    "publish",
]
