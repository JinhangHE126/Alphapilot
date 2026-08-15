"""Day-1 human-review state machine and publication gates."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from db import models as db_models  # noqa: E402
from db.models import init_db  # noqa: E402
from db.repository import (  # noqa: E402
    create_analysis_record,
    create_audit_record,
    create_user,
    update_audit_record,
)
from governance.approvals import (  # noqa: E402
    ApprovalTransitionError,
    approve,
    publish,
    reject,
    request_revision,
    submit_for_review,
)


@pytest.fixture()
def valid_analysis(tmp_path, monkeypatch) -> int:
    db_path = tmp_path / "approval.db"
    monkeypatch.setattr(db_models, "DB_PATH", db_path)
    monkeypatch.setattr(db_models, "DB_PATH_V2", db_path)
    init_db()

    user = create_user("approval_user", "approval_password_123")
    analysis = create_analysis_record(int(user["id"]), "AAPL")
    analysis_id = int(analysis["id"])
    request_id = f"approval-{analysis_id}"
    create_audit_record(
        request_id,
        analysis_id=analysis_id,
        user_id=int(user["id"]),
        stock_symbol="AAPL",
    )
    update_audit_record(
        request_id,
        guard_result={"is_valid": True, "issues": []},
        citation_validation={
            "ok": True,
            "claim_ok": True,
            "blocking_issues": [],
        },
    )
    return analysis_id


def test_happy_path_submit_approve_publish(valid_analysis):
    pending = submit_for_review(valid_analysis)
    assert pending["approval_status"] == "pending_review"

    approved = approve(
        valid_analysis,
        reviewer="compliance@example.com",
        comments="Evidence and limitations reviewed.",
    )
    assert approved["approval_status"] == "approved"
    assert approved["human_reviewer"] == "compliance@example.com"
    assert approved["approval_timestamp"]
    assert approved["publication_status"] == "not_published"

    published = publish(valid_analysis)
    assert published["publication_status"] == "published"


def test_submit_blocked_when_guard_failed(valid_analysis):
    update_audit_record(
        f"approval-{valid_analysis}",
        guard_result={"is_valid": False, "issues": ["unsupported claim"]},
    )
    with pytest.raises(ApprovalTransitionError) as caught:
        submit_for_review(valid_analysis)
    assert caught.value.code == "GUARD_NOT_PASSED"


def test_submit_blocked_when_claim_validation_failed(valid_analysis):
    update_audit_record(
        f"approval-{valid_analysis}",
        citation_validation={
            "ok": False,
            "claim_ok": False,
            "blocking_issues": [{"code": "MISSING_CITATION"}],
        },
    )
    with pytest.raises(ApprovalTransitionError) as caught:
        submit_for_review(valid_analysis)
    assert caught.value.code == "CLAIM_VALIDATION_FAILED"


def test_cannot_approve_draft(valid_analysis):
    with pytest.raises(ApprovalTransitionError) as caught:
        approve(valid_analysis, reviewer="reviewer", comments=None)
    assert caught.value.code == "INVALID_TRANSITION"


def test_reject_requires_comments(valid_analysis):
    submit_for_review(valid_analysis)
    with pytest.raises(ApprovalTransitionError) as caught:
        reject(valid_analysis, reviewer="reviewer", comments=None)
    assert caught.value.code == "REVIEW_COMMENTS_REQUIRED"


def test_revision_can_be_resubmitted(valid_analysis):
    submit_for_review(valid_analysis)
    revised = request_revision(
        valid_analysis,
        reviewer="reviewer",
        comments="Add primary-source support.",
    )
    assert revised["approval_status"] == "revision_requested"
    assert revised["publication_status"] == "not_published"

    pending = submit_for_review(valid_analysis)
    assert pending["approval_status"] == "pending_review"
    assert pending["human_reviewer"] is None
    assert pending["review_comments"] is None


def test_only_approved_report_can_publish(valid_analysis):
    with pytest.raises(ApprovalTransitionError) as caught:
        publish(valid_analysis)
    assert caught.value.code == "NOT_APPROVED"


def test_publish_rechecks_claim_validation_after_approval(valid_analysis):
    submit_for_review(valid_analysis)
    approve(valid_analysis, reviewer="reviewer", comments="Approved.")
    update_audit_record(
        f"approval-{valid_analysis}",
        citation_validation={
            "ok": False,
            "claim_ok": False,
            "blocking_issues": [{"code": "MISSING_CITATION"}],
        },
    )

    with pytest.raises(ApprovalTransitionError) as caught:
        publish(valid_analysis)
    assert caught.value.code == "CLAIM_VALIDATION_FAILED"


def test_publish_rechecks_guard_after_approval(valid_analysis):
    submit_for_review(valid_analysis)
    approve(valid_analysis, reviewer="reviewer", comments="Approved.")
    update_audit_record(
        f"approval-{valid_analysis}",
        guard_result={"is_valid": False, "issues": ["report changed"]},
    )

    with pytest.raises(ApprovalTransitionError) as caught:
        publish(valid_analysis)
    assert caught.value.code == "GUARD_NOT_PASSED"
