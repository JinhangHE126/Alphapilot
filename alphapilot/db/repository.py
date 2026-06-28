import hashlib
import hmac
import json
import os
import uuid
from datetime import datetime
from typing import Any

from db.models import get_connection


def _hash_password(password: str, salt: bytes | None = None) -> str:
    password_bytes = password.encode("utf-8")
    used_salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password_bytes, used_salt, 120000)
    return f"{used_salt.hex()}${digest.hex()}"


def _verify_password(password: str, encoded: str) -> bool:
    try:
        salt_hex, hash_hex = encoded.split("$", 1)
    except ValueError:
        return False
    recomputed = _hash_password(password, bytes.fromhex(salt_hex)).split("$", 1)[1]
    return hmac.compare_digest(recomputed, hash_hex)


def create_user(username: str, password: str, display_name: str = "") -> dict[str, Any]:
    password_hash = _hash_password(password)
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO users (username, password_hash, display_name) VALUES (?, ?, ?)",
            (username, password_hash, display_name or username),
        )
        user_id = int(cursor.lastrowid)
        row = conn.execute(
            "SELECT id, username, display_name, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    return dict(row) if row else {}


def get_user_by_username(username: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, username, password_hash, created_at FROM users WHERE username = ?",
            (username,),
        ).fetchone()
    return dict(row) if row else None


def authenticate_user(username: str, password: str) -> dict[str, Any] | None:
    user = get_user_by_username(username)
    if not user:
        return None
    if not _verify_password(password, user["password_hash"]):
        return None
    with get_connection() as conn:
        conn.execute(
            "UPDATE users SET last_login = datetime('now') WHERE id = ?",
            (user["id"],),
        )
    return {
        "id": user["id"],
        "username": user["username"],
        "display_name": user.get("display_name", ""),
        "created_at": user["created_at"],
    }


def create_session(user_id: int, title: str = "New Session") -> dict[str, Any]:
    session_id = str(uuid.uuid4())
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO sessions (id, user_id, title) VALUES (?, ?, ?)",
            (session_id, user_id, title),
        )
        row = conn.execute(
            "SELECT id, user_id, title, created_at, updated_at FROM sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
    return dict(row) if row else {}


def get_session(session_id: str, user_id: int) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, user_id, title, created_at, updated_at
            FROM sessions
            WHERE id = ? AND user_id = ?
            """,
            (session_id, user_id),
        ).fetchone()
    return dict(row) if row else None


def list_sessions(user_id: int) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, user_id, title, created_at, updated_at
            FROM sessions
            WHERE user_id = ?
            ORDER BY updated_at DESC
            """,
            (user_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def add_message(session_id: str, role: str, content: str, node_name: str | None = None) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO messages (session_id, role, content, node_name)
            VALUES (?, ?, ?, ?)
            """,
            (session_id, role, content, node_name),
        )
        conn.execute(
            "UPDATE sessions SET updated_at = ? WHERE id = ?",
            (datetime.utcnow().isoformat(timespec="seconds"), session_id),
        )


def list_messages(session_id: str, user_id: int) -> list[dict[str, Any]]:
    with get_connection() as conn:
        owner = conn.execute(
            "SELECT id FROM sessions WHERE id = ? AND user_id = ?",
            (session_id, user_id),
        ).fetchone()
        if not owner:
            return []
        rows = conn.execute(
            """
            SELECT id, session_id, role, content, node_name, created_at
            FROM messages
            WHERE session_id = ?
            ORDER BY created_at ASC, id ASC
            """,
            (session_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def create_analysis_record(
    user_id: int,
    stock_symbol: str,
    analysis_type: str = "analyze",
) -> dict[str, Any]:
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO analysis_history (user_id, stock_symbol, analysis_type, status) VALUES (?, ?, ?, 'running')",
            (user_id, stock_symbol, analysis_type),
        )
        analysis_id = int(cursor.lastrowid)
        row = conn.execute(
            "SELECT * FROM analysis_history WHERE id = ?",
            (analysis_id,),
        ).fetchone()
    return dict(row) if row else {}


def complete_analysis_record(
    analysis_id: int,
    report: str,
    recommendation: str | None = None,
    final_score: float = 0.0,
    status: str = "completed",
) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE analysis_history SET report=?, recommendation=?, final_score=?, status=?, completed_at=datetime('now') WHERE id=?",
            (report, recommendation, final_score, status, analysis_id),
        )


def add_analysis_event(
    analysis_id: int,
    seq_num: int,
    agent_name: str,
    event_type: str,
    content: str | None = None,
) -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO analysis_events (analysis_id, seq_num, agent_name, event_type, content) VALUES (?, ?, ?, ?, ?)",
            (analysis_id, seq_num, agent_name, event_type, content),
        )


def list_analysis_history(
    user_id: int,
    page: int = 1,
    page_size: int = 20,
    stock_symbol: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    with get_connection() as conn:
        where_clause = "WHERE user_id = ?"
        params: list[Any] = [user_id]
        if stock_symbol:
            where_clause += " AND stock_symbol = ?"
            params.append(stock_symbol.upper())

        total_row = conn.execute(
            f"SELECT COUNT(*) as cnt FROM analysis_history {where_clause}",
            params,
        ).fetchone()
        total = total_row["cnt"] if total_row else 0

        offset = (page - 1) * page_size
        rows = conn.execute(
            f"SELECT * FROM analysis_history {where_clause} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params + [page_size, offset],
        ).fetchall()

    return [dict(row) for row in rows], total


def get_analysis_detail(analysis_id: int, user_id: int) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM analysis_history WHERE id = ? AND user_id = ?",
            (analysis_id, user_id),
        ).fetchone()
        return dict(row) if row else None


def get_analysis_events(analysis_id: int) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM analysis_events WHERE analysis_id = ? ORDER BY seq_num ASC",
            (analysis_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def delete_analysis_record(analysis_id: int, user_id: int) -> bool:
    with get_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM analysis_history WHERE id = ? AND user_id = ?",
            (analysis_id, user_id),
        )
        return cursor.rowcount > 0


def save_analysis_citations(
    analysis_id: int,
    chunk_ids: list[str],
    doc_markers: list[str] | None = None,
    evidence_snapshot: list[dict[str, Any]] | None = None,
) -> None:
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM analysis_citations WHERE analysis_id = ?",
            (analysis_id,),
        )
        conn.execute(
            """
            INSERT INTO analysis_citations (analysis_id, chunk_ids, doc_markers, evidence_snapshot)
            VALUES (?, ?, ?, ?)
            """,
            (
                analysis_id,
                json.dumps(chunk_ids, ensure_ascii=False),
                json.dumps(doc_markers, ensure_ascii=False) if doc_markers else None,
                json.dumps(evidence_snapshot, ensure_ascii=False) if evidence_snapshot else None,
            ),
        )


def get_analysis_citations(analysis_id: int) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT chunk_ids, doc_markers, evidence_snapshot, created_at FROM analysis_citations WHERE analysis_id = ?",
            (analysis_id,),
        ).fetchone()
        if not row:
            return None
        result = dict(row)
        for field in ("chunk_ids", "doc_markers", "evidence_snapshot"):
            if result.get(field):
                try:
                    result[field] = json.loads(result[field])
                except (json.JSONDecodeError, TypeError):
                    pass
        return result


def get_user_stats(user_id: int) -> dict[str, Any]:
    with get_connection() as conn:
        total = conn.execute(
            "SELECT COUNT(*) as cnt FROM analysis_history WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        symbols = conn.execute(
            "SELECT COUNT(DISTINCT stock_symbol) as cnt FROM analysis_history WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        avg_score = conn.execute(
            "SELECT AVG(final_score) as avg FROM analysis_history WHERE user_id = ? AND status='completed'",
            (user_id,),
        ).fetchone()
        recent = conn.execute(
            "SELECT MAX(created_at) as ts FROM analysis_history WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    return {
        "total_analyses": total["cnt"] if total else 0,
        "unique_symbols": symbols["cnt"] if symbols else 0,
        "average_score": round(avg_score["avg"], 1) if avg_score and avg_score["avg"] else 0.0,
        "last_active": recent["ts"] if recent and recent["ts"] else None,
    }
