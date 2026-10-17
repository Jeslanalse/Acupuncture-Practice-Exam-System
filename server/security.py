"""鉴权核心：配置、密码哈希、JWT 签发与 SQLite 白名单会话校验。

`auth.py`（认证路由）与 `teacher.py`（教师业务路由）都从这里取依赖，
这样业务模块不需要反过来导入 `auth.py`，避免循环导入。

环境变量：
    AUTH_SECRET_KEY               JWT 密钥（生产必须覆盖）
    AUTH_TOKEN_TTL_MINUTES        会话绝对上限，默认 720（12 小时）
    AUTH_IDLE_TIMEOUT_MINUTES     空闲超时，默认 20
    AUTH_SINGLE_SESSION           1/0，是否单会话，默认 1
    AUTH_SESSION_RETENTION_DAYS   失效记录保留天数，默认 7
"""

from __future__ import annotations

import os
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

import bcrypt
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

try:  # 兼容 `python server/auth.py` 与 `python -m server.auth`
    from .db import connect
except ImportError:
    from db import connect

# ---------- 配置 ----------
SECRET_KEY = os.environ.get("AUTH_SECRET_KEY", "dev-secret-change-me")
ALGORITHM = "HS256"
TOKEN_TTL_MINUTES = float(os.environ.get("AUTH_TOKEN_TTL_MINUTES", "720"))
IDLE_TIMEOUT_MINUTES = float(os.environ.get("AUTH_IDLE_TIMEOUT_MINUTES", "20"))
SINGLE_SESSION = os.environ.get("AUTH_SINGLE_SESSION", "1").strip().lower() not in {"0", "false", "no"}
RETENTION_SECONDS = float(os.environ.get("AUTH_SESSION_RETENTION_DAYS", "7")) * 86400
BCRYPT_MAX_BYTES = 72  # bcrypt 5.x 超长密码会直接抛 ValueError
SEED_ADMIN = ("admin", "hitsz")

bearer_scheme = HTTPBearer(auto_error=False)


# ---------- 时间与错误 ----------
def now() -> float:
    return time.time()


def iso(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat(timespec="seconds")


def unauthorized(detail: str) -> HTTPException:
    return HTTPException(status_code=401, detail=detail, headers={"WWW-Authenticate": "Bearer"})


# ---------- 密码 ----------
def hash_password(password: str) -> str:
    pwd_bytes = password.encode("utf-8")
    if len(pwd_bytes) > BCRYPT_MAX_BYTES:
        raise ValueError("password too long for bcrypt")
    return bcrypt.hashpw(pwd_bytes, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8")[:BCRYPT_MAX_BYTES],
            hashed_password.encode("utf-8"),
        )
    except ValueError:
        return False


# ---------- 用户 ----------
def get_user(conn, user_id: str):
    return conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def user_role(user_id: str) -> Optional[str]:
    with connect() as conn:
        row = conn.execute("SELECT role FROM users WHERE id = ?", (user_id,)).fetchone()
    return row["role"] if row else None


def seed_users() -> None:
    """首次启动时预置测试账号；已存在则不动。"""
    with connect() as conn:
        if get_user(conn, SEED_ADMIN[0]) is not None:
            return
        try:
            password_hash = hash_password(SEED_ADMIN[1])
        except ValueError:  # 理论上不会发生
            return
        conn.execute(
            "INSERT INTO users (id, password_hash, role, display_name, is_active, created_at)"
            " VALUES (?, ?, 'admin', '管理员', 1, ?)",
            (SEED_ADMIN[0], password_hash, now()),
        )


# ---------- 会话（白名单） ----------
def purge(conn, timestamp: Optional[float] = None) -> int:
    cutoff = (now() if timestamp is None else timestamp) - RETENTION_SECONDS
    cursor = conn.execute(
        "DELETE FROM sessions WHERE expires_at < ? OR (revoked_at IS NOT NULL AND revoked_at < ?)",
        (cutoff, cutoff),
    )
    return cursor.rowcount


def purge_expired() -> None:
    with connect() as conn:
        purge(conn, now())


def create_session(user_id: str, client_info: str = "") -> tuple[str, float]:
    """登记一条白名单会话并签发 JWT，返回 (token, expires_at)。"""
    timestamp = now()
    jti = uuid.uuid4().hex
    expires_at = timestamp + TOKEN_TTL_MINUTES * 60

    with connect() as conn:
        if SINGLE_SESSION:
            conn.execute(
                "UPDATE sessions SET revoked_at = ?, revoked_reason = 'superseded'"
                " WHERE user_id = ? AND revoked_at IS NULL AND expires_at > ?",
                (timestamp, user_id, timestamp),
            )
        conn.execute(
            "INSERT INTO sessions (jti, user_id, issued_at, expires_at, last_seen_at, client_info)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (jti, user_id, timestamp, expires_at, timestamp, client_info[:200]),
        )
        purge(conn, timestamp)

    token = jwt.encode(
        {"sub": user_id, "jti": jti, "iat": int(timestamp), "exp": int(expires_at)},
        SECRET_KEY,
        algorithm=ALGORITHM,
    )
    return token, expires_at


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
            options={"require": ["sub", "jti", "exp"]},
        )
    except jwt.ExpiredSignatureError:
        raise unauthorized("Token expired")
    except jwt.PyJWTError:
        raise unauthorized("Invalid token")


def authenticate(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> dict:
    """白名单校验：JWT 合法 + 会话记录存在 + 未撤销 + 未过期 + 未空闲超时。"""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise unauthorized("Not authenticated")

    payload = decode_token(credentials.credentials)
    jti = payload.get("jti")
    user_id = payload.get("sub")
    if not jti or not user_id:
        raise unauthorized("Invalid token")

    timestamp = now()
    failure: Optional[str] = None
    session: Optional[dict] = None

    with connect() as conn:
        row = conn.execute("SELECT * FROM sessions WHERE jti = ?", (jti,)).fetchone()
        if row is None:
            failure = "Session expired"
        elif row["revoked_at"] is not None:
            failure = "Token has been revoked"
        elif row["expires_at"] <= timestamp:
            conn.execute(
                "UPDATE sessions SET revoked_at = ?, revoked_reason = 'expired' WHERE jti = ?",
                (timestamp, jti),
            )
            failure = "Token expired"
        elif timestamp - row["last_seen_at"] > IDLE_TIMEOUT_MINUTES * 60:
            conn.execute(
                "UPDATE sessions SET revoked_at = ?, revoked_reason = 'idle_timeout' WHERE jti = ?",
                (timestamp, jti),
            )
            failure = "Session expired (idle)"
        else:
            # 每 60 秒最多落一次 last_seen，避免每个请求都写库
            if timestamp - row["last_seen_at"] > 60:
                conn.execute("UPDATE sessions SET last_seen_at = ? WHERE jti = ?", (timestamp, jti))
                session = {**dict(row), "last_seen_at": timestamp}
            else:
                session = dict(row)

    if failure is not None or session is None:
        raise unauthorized(failure or "Invalid session")

    return {
        "id": user_id,
        "jti": jti,
        "issued_at": session["issued_at"],
        "expires_at": session["expires_at"],
        "last_seen_at": session["last_seen_at"],
    }


def revoke(jti: str, reason: str) -> bool:
    with connect() as conn:
        cursor = conn.execute(
            "UPDATE sessions SET revoked_at = ?, revoked_reason = ?"
            " WHERE jti = ? AND revoked_at IS NULL",
            (now(), reason, jti),
        )
        return cursor.rowcount > 0


def revoke_all_for_user(user_id: str, reason: str) -> int:
    with connect() as conn:
        cursor = conn.execute(
            "UPDATE sessions SET revoked_at = ?, revoked_reason = ?"
            " WHERE user_id = ? AND revoked_at IS NULL",
            (now(), reason, user_id),
        )
        return cursor.rowcount
