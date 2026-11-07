"""SQLite storage for class sessions, attendance records and check-in attempts."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import pandas as pd

from src.core.config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS class_sessions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    token               TEXT    NOT NULL UNIQUE,
    course_name         TEXT    NOT NULL,
    class_name          TEXT    NOT NULL,
    lecturer            TEXT    NOT NULL DEFAULT '',
    room                TEXT    NOT NULL DEFAULT '',
    session_date        TEXT    NOT NULL,              -- YYYY-MM-DD
    start_time          TEXT    NOT NULL,              -- HH:MM
    end_time            TEXT    NOT NULL,              -- HH:MM
    late_after_minutes  INTEGER NOT NULL DEFAULT 15,
    departments         TEXT    NOT NULL DEFAULT '',   -- comma separated, empty = all
    enforce_schedule    INTEGER NOT NULL DEFAULT 1,
    is_active           INTEGER NOT NULL DEFAULT 1,
    created_at          TEXT    NOT NULL,
    course_id           INTEGER REFERENCES courses(id) ON DELETE CASCADE,  -- NULL = one-off session
    is_cancelled        INTEGER NOT NULL DEFAULT 0                          -- e.g. public holiday
);

-- A semester course: weekly schedule that generates one class_session per meeting.
-- Its token is a permanent link/QR that always points to the current meeting.
CREATE TABLE IF NOT EXISTS courses (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    token               TEXT    NOT NULL UNIQUE,
    course_name         TEXT    NOT NULL,
    class_name          TEXT    NOT NULL,
    lecturer            TEXT    NOT NULL DEFAULT '',
    room                TEXT    NOT NULL DEFAULT '',
    weekdays            TEXT    NOT NULL,              -- "0,2" = Monday, Wednesday
    start_time          TEXT    NOT NULL,              -- HH:MM
    end_time            TEXT    NOT NULL,              -- HH:MM
    late_after_minutes  INTEGER NOT NULL DEFAULT 15,
    departments         TEXT    NOT NULL DEFAULT '',
    start_date          TEXT    NOT NULL,              -- YYYY-MM-DD
    end_date            TEXT    NOT NULL,              -- YYYY-MM-DD
    is_active           INTEGER NOT NULL DEFAULT 1,
    created_at          TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS attendance (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id       INTEGER NOT NULL REFERENCES class_sessions(id) ON DELETE CASCADE,
    nim              TEXT    NOT NULL,
    name             TEXT    NOT NULL,
    gender           TEXT    NOT NULL,
    faculty          TEXT    NOT NULL,
    department       TEXT    NOT NULL,
    cohort           TEXT    NOT NULL,
    status           TEXT    NOT NULL,                 -- Present | Late
    attendance_date  TEXT    NOT NULL,                 -- YYYY-MM-DD
    checked_in_at    TEXT    NOT NULL,                 -- YYYY-MM-DD HH:MM:SS
    device_id        TEXT,                             -- browser cookie, NULL for admin entries
    ip_address       TEXT,
    added_by_admin   INTEGER NOT NULL DEFAULT 0,
    UNIQUE (session_id, nim)
);

-- Key/value settings edited on Admin > Settings > General.
CREATE TABLE IF NOT EXISTS app_settings (
    key    TEXT PRIMARY KEY,
    value  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS admins (
    username       TEXT PRIMARY KEY,
    password_hash  TEXT NOT NULL,
    created_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS admin_sessions (
    token_hash  TEXT PRIMARY KEY,
    username    TEXT NOT NULL REFERENCES admins(username) ON DELETE CASCADE,
    expires_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS checkin_attempts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  INTEGER REFERENCES class_sessions(id) ON DELETE CASCADE,
    nim_input   TEXT NOT NULL,
    result      TEXT NOT NULL,   -- success | not_found | duplicate | closed | not_allowed | device_used
    created_at  TEXT NOT NULL,
    device_id   TEXT,
    ip_address  TEXT
);

-- Transactional outbox: every domain event is stored here first and then
-- published to Kafka by a background thread, so no event is lost while Kafka is down.
CREATE TABLE IF NOT EXISTS event_outbox (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id      TEXT NOT NULL UNIQUE,
    event_type    TEXT NOT NULL,
    event_key     TEXT,
    payload       TEXT NOT NULL,            -- JSON
    created_at    TEXT NOT NULL,
    published_at  TEXT
);
CREATE INDEX IF NOT EXISTS idx_outbox_pending ON event_outbox(published_at, id);

CREATE INDEX IF NOT EXISTS idx_attendance_date    ON attendance(attendance_date);
CREATE INDEX IF NOT EXISTS idx_attendance_nim     ON attendance(nim);
CREATE INDEX IF NOT EXISTS idx_attempts_created   ON checkin_attempts(created_at);
CREATE INDEX IF NOT EXISTS idx_sessions_date      ON class_sessions(session_date);
CREATE INDEX IF NOT EXISTS idx_sessions_course    ON class_sessions(course_id, session_date);
CREATE INDEX IF NOT EXISTS idx_attendance_device  ON attendance(session_id, device_id);
"""

# Columns added after the first release; created on older databases at start-up.
MIGRATIONS = {
    "class_sessions": {
        "course_id": "INTEGER REFERENCES courses(id) ON DELETE CASCADE",
        "is_cancelled": "INTEGER NOT NULL DEFAULT 0",
    },
    "attendance": {
        "device_id": "TEXT",
        "ip_address": "TEXT",
        "added_by_admin": "INTEGER NOT NULL DEFAULT 0",
    },
    "checkin_attempts": {
        "device_id": "TEXT",
        "ip_address": "TEXT",
    },
}

_initialized: set[str] = set()


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")   # concurrent readers while students check in
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn


def init_db(path: Path | None = None) -> None:
    db_path = Path(path or settings.database_path)
    with _connect(db_path) as conn:
        for table, columns in MIGRATIONS.items():
            existing = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
            if existing:  # table exists from an older version
                for column, ddl in columns.items():
                    if column not in existing:
                        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")
        conn.executescript(SCHEMA)
    _initialized.add(str(db_path))


@contextmanager
def get_connection(path: Path | None = None) -> Iterator[sqlite3.Connection]:
    db_path = Path(path or settings.database_path)
    if str(db_path) not in _initialized:
        init_db(db_path)
    conn = _connect(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def fetch_df(sql: str, params: tuple | dict = ()) -> pd.DataFrame:
    with get_connection() as conn:
        return pd.read_sql_query(sql, conn, params=params)


def fetch_one(sql: str, params: tuple | dict = ()) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(sql, params).fetchone()
        return dict(row) if row else None


def execute(sql: str, params: tuple | dict = ()) -> int:
    """Run a write statement and return the last inserted row id."""
    with get_connection() as conn:
        cur = conn.execute(sql, params)
        return cur.lastrowid
