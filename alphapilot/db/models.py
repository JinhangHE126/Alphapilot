import sqlite3
import os
from pathlib import Path


DB_PATH = Path(os.getenv("APP_DB_PATH", "./checkpoints/app.db"))
DB_PATH_V2 = Path(os.getenv("APP_DB_PATH", "./checkpoints/app.db"))


def get_connection() -> sqlite3.Connection:
    """Return a SQLite connection with row access by key."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def init_db() -> None:
    """Initialize business tables for auth/session/message data."""
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                display_name TEXT DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                last_login TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL DEFAULT 'New Session',
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                node_name TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS analysis_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id),
                stock_symbol TEXT NOT NULL,
                analysis_type TEXT NOT NULL DEFAULT 'analyze',
                report TEXT,
                recommendation TEXT,
                final_score REAL DEFAULT 0.0,
                status TEXT DEFAULT 'running',
                started_at TEXT DEFAULT (datetime('now')),
                completed_at TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS analysis_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                analysis_id INTEGER NOT NULL REFERENCES analysis_history(id),
                seq_num INTEGER NOT NULL,
                agent_name TEXT NOT NULL,
                event_type TEXT NOT NULL,
                content TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_sessions_user_updated
            ON sessions (user_id, updated_at DESC)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_messages_session_created
            ON messages (session_id, created_at ASC)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_history_user
            ON analysis_history (user_id)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_history_time
            ON analysis_history (created_at DESC)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_events_analysis
            ON analysis_events (analysis_id)
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS analysis_citations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                analysis_id INTEGER NOT NULL,
                chunk_ids TEXT NOT NULL,
                doc_markers TEXT,
                evidence_snapshot TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (analysis_id) REFERENCES analysis_history(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_citations_analysis
            ON analysis_citations(analysis_id)
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ai_audit_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id TEXT NOT NULL UNIQUE,
                analysis_id INTEGER,
                session_id TEXT,
                user_id INTEGER,
                timestamp_started TEXT NOT NULL DEFAULT (datetime('now')),
                timestamp_completed TEXT,
                use_case TEXT NOT NULL DEFAULT 'ai_assisted_investment_research',
                stock_symbol TEXT NOT NULL DEFAULT '',
                data_sources TEXT,
                retrieved_document_ids TEXT,
                cited_chunk_ids TEXT,
                evidence_packet_snapshot TEXT,
                model_provider TEXT,
                model_name TEXT,
                model_version TEXT,
                prompt_version TEXT,
                generated_output TEXT,
                citation_validation TEXT,
                guard_result TEXT,
                risk_flags TEXT,
                human_reviewer TEXT,
                review_comments TEXT,
                approval_status TEXT NOT NULL DEFAULT 'draft',
                approval_timestamp TEXT,
                publication_status TEXT NOT NULL DEFAULT 'not_published',
                kill_switch_status TEXT NOT NULL DEFAULT 'enabled',
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (analysis_id) REFERENCES analysis_history(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_audit_analysis
            ON ai_audit_records(analysis_id)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_audit_request
            ON ai_audit_records(request_id)
            """
        )
        _migrate_users(conn)


def _migrate_users(conn: sqlite3.Connection) -> None:
    cols = [row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()]
    if "display_name" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN display_name TEXT DEFAULT ''")
    if "last_login" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN last_login TEXT")
