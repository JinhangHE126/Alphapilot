"""Day-1: request_id middleware → /analyze → ai_audit_records wiring."""
from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
os.environ["APP_DB_PATH"] = str(PROJECT_ROOT / "checkpoints" / "test_audit_wiring.db")

from api.main import api  # noqa: E402
from db.models import init_db  # noqa: E402
from db.repository import get_audit_record_by_request_id  # noqa: E402

init_db()
client = TestClient(api)


def _auth_headers() -> dict[str, str]:
    username = f"audit_wire_{uuid.uuid4().hex[:8]}"
    password = "audit_wire_pass_123"
    reg = client.post("/auth/register", json={"username": username, "password": password})
    assert reg.status_code in (200, 409)
    login = client.post("/auth/login", json={"username": username, "password": password})
    assert login.status_code == 200
    body = login.json()
    token = (body.get("data") or body).get("access_token")
    assert token
    return {"Authorization": f"Bearer {token}"}


def test_analyze_wires_request_id_into_audit_record():
    headers = _auth_headers()
    request_id = f"demo-req-{uuid.uuid4().hex[:10]}"
    headers["X-Request-ID"] = request_id

    fake_result = {
        "final_report": "AAPL looks stable [doc:1].",
        "recommendation": "Hold",
        "guard_check": {
            "is_valid": True,
            "confidence_score": 88,
            "issues": [],
            "grounding_warnings": [
                "GUARD_EMBEDDING_DEGRADED: semantic check skipped"
            ],
            "evidence_packet": {"symbol": "AAPL", "facts": []},
        },
        "citations": {
            "chunk_ids": ["chunk-aapl-1"],
            "doc_markers": ["doc:1"],
            "evidence_snapshot": [{"chunk_id": "chunk-aapl-1"}],
        },
    }

    with patch("services.analysis_service.run_analysis_once", return_value=fake_result):
        res = client.post(
            "/analyze",
            headers=headers,
            json={"message": "analyze AAPL", "stock_symbol": "AAPL"},
        )

    assert res.status_code == 200, res.text
    assert res.headers.get("X-Request-ID") == request_id
    payload = res.json()
    data = payload.get("data") or payload
    assert data["request_id"] == request_id
    assert data.get("analysis_id")

    audit = get_audit_record_by_request_id(request_id)
    assert audit is not None
    assert audit["analysis_id"] == data["analysis_id"]
    assert audit["stock_symbol"] == "AAPL"
    assert audit["generated_output"] == fake_result["final_report"]
    assert audit["cited_chunk_ids"] == ["chunk-aapl-1"]
    assert audit["guard_result"]["is_valid"] is True
    assert "GUARD_EMBEDDING_DEGRADED" in audit["risk_flags"]
    assert audit["timestamp_completed"]
    assert audit["model_provider"]
    assert audit["model_name"]
    assert audit["model_version"]
    assert audit["prompt_version"]
    assert "unknown" not in (audit["model_provider"], audit["model_name"])
    assert data.get("disclaimer")
    assert data.get("disclaimer_version")
    assert "SFC" in data["disclaimer"]


def test_analyze_fallback_still_records_model_prompt_metadata(monkeypatch):
    headers = _auth_headers()
    request_id = f"demo-fallback-{uuid.uuid4().hex[:10]}"
    headers["X-Request-ID"] = request_id
    monkeypatch.setenv("PROMPT_VERSION", "alphapilot-prompts-test-v1")
    monkeypatch.setenv("MODEL_VERSION", "provider-managed-test")

    with patch(
        "services.analysis_service.run_analysis_once",
        side_effect=RuntimeError("provider timeout"),
    ):
        res = client.post(
            "/analyze",
            headers=headers,
            json={"message": "analyze AAPL", "stock_symbol": "AAPL"},
        )

    assert res.status_code == 200, res.text
    audit = get_audit_record_by_request_id(request_id)
    assert audit is not None
    assert audit["prompt_version"] == "alphapilot-prompts-test-v1"
    assert audit["model_version"] == "provider-managed-test"
    assert audit["model_provider"]
    assert audit["model_name"]
    assert "ANALYSIS_FAILED" in (audit.get("risk_flags") or [])
