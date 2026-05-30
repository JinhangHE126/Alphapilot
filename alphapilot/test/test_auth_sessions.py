import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
os.environ["APP_DB_PATH"] = str(PROJECT_ROOT / "checkpoints" / "test_app.db")

from api.main import api  # noqa: E402
from db.models import init_db  # noqa: E402


init_db()
client = TestClient(api)


def test_register_login_and_session_lifecycle():
    username = "ci_user_alpha"
    password = "ci_password_123"

    register_res = client.post("/auth/register", json={"username": username, "password": password})
    assert register_res.status_code in (200, 409)

    login_res = client.post("/auth/login", json={"username": username, "password": password})
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    create_session_res = client.post("/sessions", json={"title": "CI Session"}, headers=headers)
    assert create_session_res.status_code == 200
    session_id = create_session_res.json()["session"]["id"]
    assert session_id

    list_sessions_res = client.get("/sessions", headers=headers)
    assert list_sessions_res.status_code == 200
    assert any(item["id"] == session_id for item in list_sessions_res.json()["sessions"])

    list_messages_res = client.get(f"/sessions/{session_id}/messages", headers=headers)
    assert list_messages_res.status_code == 200
    assert isinstance(list_messages_res.json()["messages"], list)
