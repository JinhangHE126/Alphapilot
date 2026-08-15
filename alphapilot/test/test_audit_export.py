"""API tests for ownership-scoped AI audit downloads."""
from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
os.environ["APP_DB_PATH"] = str(PROJECT_ROOT / "checkpoints" / "test_audit_export.db")

from api.main import api  # noqa: E402
from db.models import init_db  # noqa: E402

init_db()
client = TestClient(api)


def _auth_headers() -> dict[str, str]:
    username = f"audit_export_{uuid.uuid4().hex[:8]}"
    password = "audit_export_pass_123"
    register = client.post("/auth/register", json={"username": username, "password": password})
    assert register.status_code == 200
    login = client.post("/auth/login", json={"username": username, "password": password})
    assert login.status_code == 200
    token = (login.json().get("data") or {}).get("access_token")
    assert token
    return {"Authorization": f"Bearer {token}"}


def _create_analysis(headers: dict[str, str]) -> int:
    result = {
        "final_report": "AAPL is stable [doc:1].",
        "recommendation": "Hold",
        "guard_check": {
            "is_valid": True,
            "issues": [],
            "evidence_packet": {"symbol": "AAPL", "facts": []},
        },
        "citations": {
            "chunk_ids": ["chunk-aapl-1"],
            "doc_markers": ["doc:1"],
            "evidence_snapshot": [{"chunk_id": "chunk-aapl-1"}],
        },
    }
    with patch("services.analysis_service.run_analysis_once", return_value=result):
        response = client.post(
            "/analyze",
            headers=headers,
            json={"message": "analyze AAPL", "stock_symbol": "AAPL"},
        )
    assert response.status_code == 200, response.text
    return int((response.json().get("data") or {})["analysis_id"])


def test_audit_export_downloads_allowlisted_json_for_owner():
    headers = _auth_headers()
    analysis_id = _create_analysis(headers)

    response = client.get(f"/analyses/{analysis_id}/audit/export", headers=headers)

    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("application/json")
    assert response.headers["content-disposition"] == (
        f'attachment; filename="analysis-{analysis_id}-audit.json"'
    )
    payload = response.json()
    assert payload["export_format"] == "alphapilot-ai-audit-v1"
    audit = payload["audit_record"]
    assert audit["analysis_id"] == analysis_id
    assert audit["stock_symbol"] == "AAPL"
    assert audit["generated_output"] == "AAPL is stable [doc:1]."
    assert "user_id" not in audit
    assert "session_id" not in audit


def test_audit_export_does_not_expose_another_users_analysis():
    owner_headers = _auth_headers()
    analysis_id = _create_analysis(owner_headers)

    response = client.get(f"/analyses/{analysis_id}/audit/export", headers=_auth_headers())

    assert response.status_code == 404
