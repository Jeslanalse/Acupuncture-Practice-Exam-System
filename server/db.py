"""SQLite 存储层：用户、会话（白名单）、手法、作业、成绩。

- 数据库文件默认在 `server/auth.db`，可用环境变量 `AUTH_DB_PATH` 覆盖（测试用临时库）。
- FastAPI 的同步端点跑在线程池里，因此每次操作都开独立连接，避免跨线程复用。
- `init_db()` 同时负责轻量迁移：老库缺列时自动补列，不丢数据。
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager

_HERE = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_DB_PATH = os.path.join(_HERE, "auth.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            TEXT PRIMARY KEY,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL DEFAULT 'student',
    display_name  TEXT NOT NULL DEFAULT '',
    is_active     INTEGER NOT NULL DEFAULT 1,
    teacher_id    TEXT REFERENCES users(id) ON DELETE SET NULL,
    created_at    REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    jti            TEXT PRIMARY KEY,
    user_id        TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    issued_at      REAL NOT NULL,
    expires_at     REAL NOT NULL,
    last_seen_at   REAL NOT NULL,
    revoked_at     REAL,
    revoked_reason TEXT,
    client_info    TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS techniques (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL DEFAULT '',
    creator_id  TEXT REFERENCES users(id) ON DELETE SET NULL,
    created_at  REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS assignments (
    id             TEXT PRIMARY KEY,
    teacher_id     TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title          TEXT NOT NULL,
    description    TEXT NOT NULL DEFAULT '',
    start_at       REAL NOT NULL,
    end_at         REAL,
    technique_id   TEXT REFERENCES techniques(id) ON DELETE RESTRICT,
    technique_name TEXT NOT NULL DEFAULT '人工批阅',
    created_at     REAL NOT NULL,
    updated_at     REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS scores (
    assignment_id TEXT NOT NULL REFERENCES assignments(id) ON DELETE CASCADE,
    student_id    TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    score         INTEGER,
    updated_at    REAL NOT NULL,
    PRIMARY KEY (assignment_id, student_id)
);

CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at);
CREATE INDEX IF NOT EXISTS idx_sessions_revoked ON sessions(revoked_at);
CREATE INDEX IF NOT EXISTS idx_assignments_teacher ON assignments(teacher_id, start_at);
CREATE INDEX IF NOT EXISTS idx_scores_student ON scores(student_id);
"""

# 旧库需要补的列：(表, 列, 列定义)
_MIGRATIONS = [
    ("users", "teacher_id", "teacher_id TEXT REFERENCES users(id) ON DELETE SET NULL"),
]


def db_path() -> str:
    return os.environ.get("AUTH_DB_PATH", _DEFAULT_DB_PATH)


@contextmanager
def connect():
    """打开一个连接；正常退出提交，异常回滚。"""
    conn = sqlite3.connect(db_path(), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _existing_columns(conn, table: str) -> set[str]:
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)
        # 先补列，再建依赖新列的索引（旧库升级路径）
        for table, column, ddl in _MIGRATIONS:
            if column not in _existing_columns(conn, table):
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_users_teacher ON users(teacher_id)")
