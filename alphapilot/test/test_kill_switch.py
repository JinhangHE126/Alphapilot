"""Kill switch and fallback gates."""
from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
os.environ["APP_DB_PATH"] = str(PROJECT_ROOT / "checkpoints" / "test_kill_switch.db")

from api.main import api  # noqa: E402
from db import models as db_models  # noqa: E402
from db.models import init_db  # noqa: E402
from db.repository import (  # noqa: E402
    create_analysis_record,
    create_audit_record,
    create_user,
    get_audit_record_by_request_id,
    update_audit_record,
)
from governance.approvals import (  # noqa: E402
    ApprovalTransitionError,
    approve,
    publish,
    submit_for_review,
)

init_db()
client = TestClient(api)


def _auth_headers() -> dict[str, str]:
    username = f"ks_user_{uuid.uuid4().hex[:8]}"
    password = "kill_switch_pass_123"
    reg = client.post("/auth/register", json={"username": username, "password": password})
    assert reg.status_code in (200, 409)
    login = client.post("/auth/login", json={"username": username, "password": password})
    assert login.status_code == 200
    body = login.json()
    token = (body.get("data") or body).get("access_token")
    assert token
    return {"Authorization": f"Bearer {token}"}


def test_analyze_blocks_when_output_paused(monkeypatch):
    headers = _auth_headers()
    request_id = f"ks-output-{uuid.uuid4().hex[:8]}"
    headers["X-Request-ID"] = request_id
    monkeypatch.setenv("AI_OUTPUT_ENABLED", "false")
    with patch("services.analysis_service.run_analysis_once") as mocked:
        res = client.post(
            "/analyze",
            headers=headers,
            json={"message": "analyze AAPL", "stock_symbol": "AAPL"},
        )
    assert res.status_code == 503, res.text
    detail = res.json().get("detail", {})
    assert detail.get("code") == "OUTPUT_PAUSED"
    mocked.assert_not_called()
    audit = get_audit_record_by_request_id(request_id)
    assert audit is not None
    assert "KILL_SWITCH_OUTPUT_PAUSED" in (audit.get("risk_flags") or [])
    assert audit.get("kill_switch_status") in {"output_paused", "output_and_publication_paused"}


@pytest.fixture()
def valid_approved_analysis(tmp_path, monkeypatch) -> int:
    db_path = tmp_path / "kill_switch_publish.db"
    monkeypatch.setattr(db_models, "DB_PATH", db_path)
    monkeypatch.setattr(db_models, "DB_PATH_V2", db_path)
    init_db()

    user = create_user("ks_publish_user", "kill_switch_publish_123")
    analysis = create_analysis_record(int(user["id"]), "AAPL")
    analysis_id = int(analysis["id"])
    request_id = f"ks-publish-{analysis_id}"
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
    submit_for_review(analysis_id)
    approve(analysis_id, reviewer="reviewer", comments="approved")
    return analysis_id


def test_publish_blocked_when_publication_paused(valid_approved_analysis, monkeypatch):
    monkeypatch.setenv("AI_PUBLICATION_ENABLED", "false")
    with pytest.raises(ApprovalTransitionError) as caught:
        publish(valid_approved_analysis)
    assert caught.value.code == "PUBLICATION_PAUSED"


def test_analyze_fallback_when_model_provider_errors(monkeypatch):
    headers = _auth_headers()
    request_id = f"ks-fallback-{uuid.uuid4().hex[:8]}"
    headers["X-Request-ID"] = request_id
    monkeypatch.setenv("AI_OUTPUT_ENABLED", "true")

    with patch("services.analysis_service.run_analysis_once", side_effect=RuntimeError("provider timeout")):
        res = client.post(
            "/analyze",
            headers=headers,
            json={"message": "analyze AAPL", "stock_symbol": "AAPL"},
        )
    assert res.status_code == 200, res.text
    payload = res.json().get("data") or {}
    assert payload.get("degraded") is True
    assert "temporarily unavailable" in (payload.get("report") or "")
    audit = get_audit_record_by_request_id(request_id)
    assert audit is not None
    assert "ANALYSIS_FAILED" in (audit.get("risk_flags") or [])
