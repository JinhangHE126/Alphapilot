"""API permission tests for governance/approval endpoints."""
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
os.environ["APP_DB_PATH"] = str(PROJECT_ROOT / "checkpoints" / "test_approval_api_permissions.db")

from api.main import api  # noqa: E402
from db.models import init_db  # noqa: E402

init_db()
client = TestClient(api)


def _auth_headers() -> dict[str, str]:
    username = f"approve_perm_{uuid.uuid4().hex[:8]}"
    password = "approve_perm_pass_123"
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


@pytest.mark.parametrize(
    ("path_suffix", "method", "payload"),
    [
        ("submit-review", "post", None),
        ("approve", "post", {"comments": "looks good"}),
        ("reject", "post", {"comments": "insufficient support"}),
        ("request-revision", "post", {"comments": "add source for valuation claim"}),
        ("publish", "post", None),
    ],
)
def test_non_owner_cannot_call_approval_transition_endpoints(path_suffix: str, method: str, payload: dict | None):
    owner_headers = _auth_headers()
    analysis_id = _create_analysis(owner_headers)
    outsider_headers = _auth_headers()

    response = client.request(
        method.upper(),
        f"/analyses/{analysis_id}/{path_suffix}",
        headers=outsider_headers,
        json=payload,
    )

    assert response.status_code == 404


def test_non_owner_cannot_read_governance_audit_or_export():
    owner_headers = _auth_headers()
    analysis_id = _create_analysis(owner_headers)
    outsider_headers = _auth_headers()

    audit_response = client.get(f"/analyses/{analysis_id}/audit", headers=outsider_headers)
    export_response = client.get(f"/analyses/{analysis_id}/audit/export", headers=outsider_headers)

    assert audit_response.status_code == 404
    assert export_response.status_code == 404
