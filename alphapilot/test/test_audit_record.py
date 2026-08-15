"""Day-1: ai_audit_records create / get / update CRUD."""
from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
os.environ["APP_DB_PATH"] = str(PROJECT_ROOT / "checkpoints" / "test_audit_records.db")

from db.models import init_db  # noqa: E402
from db.repository import (  # noqa: E402
    create_analysis_record,
    create_audit_record,
    create_user,
    get_audit_record_by_analysis_id,
    get_audit_record_by_request_id,
    update_audit_record,
)
from schemas.approval import ApprovalStatus  # noqa: E402

init_db()


def _ensure_demo_user() -> int:
    username = f"audit_ci_{uuid.uuid4().hex[:8]}"
    user = create_user(username, "audit_password_123")
    return int(user["id"])


def test_create_and_get_audit_record_by_request_id():
    request_id = f"test-req-{uuid.uuid4().hex[:12]}"
    created = create_audit_record(
        request_id,
        stock_symbol="AAPL",
        user_id=1,
        session_id="sess-demo",
    )
    assert created["request_id"] == request_id
    assert created["stock_symbol"] == "AAPL"
    assert created["approval_status"] == "draft"
    assert created["publication_status"] == "not_published"
    assert created["kill_switch_status"] == "enabled"

    fetched = get_audit_record_by_request_id(request_id)
    assert fetched is not None
    assert fetched["request_id"] == request_id
    assert fetched["use_case"] == "ai_assisted_investment_research"


def test_update_audit_record_json_and_enum():
    request_id = f"test-req-{uuid.uuid4().hex[:12]}"
    user_id = _ensure_demo_user()
    analysis = create_analysis_record(user_id, "0700.HK")
    analysis_id = int(analysis["id"])

    create_audit_record(request_id, stock_symbol="0700.HK", user_id=user_id)

    updated = update_audit_record(
        request_id,
        analysis_id=analysis_id,
        risk_flags=["MISSING_CITATION"],
        data_sources=["HKEX", "yfinance"],
        approval_status=ApprovalStatus.PENDING_REVIEW,
        guard_result={"is_valid": True, "confidence_score": 80},
    )
    assert updated is not None
    assert updated["analysis_id"] == analysis_id
    assert updated["risk_flags"] == ["MISSING_CITATION"]
    assert updated["data_sources"] == ["HKEX", "yfinance"]
    assert updated["approval_status"] == "pending_review"
    assert updated["guard_result"]["is_valid"] is True

    by_analysis = get_audit_record_by_analysis_id(analysis_id)
    assert by_analysis is not None
    assert by_analysis["request_id"] == request_id


def test_get_missing_audit_record_returns_none():
    assert get_audit_record_by_request_id("does-not-exist") is None
    assert get_audit_record_by_analysis_id(-99999) is None
