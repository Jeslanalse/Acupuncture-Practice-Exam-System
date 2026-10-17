"""FastAPI 应用组装：鉴权接口 + 教师端业务接口（学生/作业/成绩/手法）。

本文件只负责：
- 组装 FastAPI app 与生命周期（建表、预置账号、清理过期会话）；
- 认证端点：`/auth/login`、`/auth/logout`、`/auth/logout-all`、`/auth/me`、`/health`；
- 挂载 `teacher.py` 里的教师业务路由。

启动入口是 `server/main.py`（负责 HTTPS/端口/证书），不要直接运行本文件。

环境变量：
    AUTH_SECRET_KEY               JWT 密钥（生产必须覆盖）
    AUTH_TOKEN_TTL_MINUTES        会话绝对上限，默认 720（12 小时）
    AUTH_IDLE_TIMEOUT_MINUTES     空闲超时，默认 20
    AUTH_SINGLE_SESSION           1/0，是否单会话，默认 1
    AUTH_SESSION_RETENTION_DAYS   失效记录保留天数，默认 7
    AUTH_DB_PATH                  数据库路径，默认 server/auth.db
    AUTH_PORT                     监听端口，默认 8000（由 main.py 读取）
    AUTH_TLS                      1/0，默认 1（由 main.py 读取）
    AUTH_TLS_DIR                  证书目录，默认 server/certs（由 main.py 读取）
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel

try:  # 支持 `python server/auth.py` 与 `python -m server.auth` 两种启动方式
    from .db import connect, init_db
    from .security import (
        authenticate,
        bearer_scheme,
        create_session,
        decode_token,
        get_user,
        iso,
        now,
        purge_expired,
        revoke,
        revoke_all_for_user,
        seed_users,
        unauthorized,
        verify_password,
    )
    from .teacher import router as teacher_router
    from .teacher import technique_router
except ImportError:
    from db import connect, init_db
    from security import (
        authenticate,
        bearer_scheme,
        create_session,
        decode_token,
        get_user,
        iso,
        now,
        purge_expired,
        revoke,
        revoke_all_for_user,
        seed_users,
        unauthorized,
        verify_password,
    )
    from teacher import router as teacher_router
    from teacher import technique_router


# ---------- 请求 / 响应模型 ----------
class LoginRequest(BaseModel):
    id: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class MeResponse(BaseModel):
    id: str
    role: str
    issued_at: str
    expires_at: str
    expires_in: int


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    seed_users()
    purge_expired()
    yield


app = FastAPI(title="Auth Server", lifespan=lifespan)
app.include_router(teacher_router)
app.include_router(technique_router)


# ---------- 认证端点 ----------
@app.post("/auth/login", response_model=TokenResponse)
def login(req: LoginRequest, request: Request):
    """验证账号密码，登记白名单会话并返回 JWT。"""
    user_id = req.id.strip()
    with connect() as conn:
        user = get_user(conn, user_id)

    if user is None or not user["is_active"] or not verify_password(req.password, user["password_hash"]):
        # 统一提示，不区分「用户不存在」与「密码错误」
        raise HTTPException(status_code=401, detail="账号或密码错误")

    token, expires_at = create_session(user["id"], request.headers.get("user-agent", ""))
    return TokenResponse(
        access_token=token,
        expires_in=max(0, int(expires_at - now())),
    )


@app.post("/auth/logout")
def logout(credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme)):
    """撤销当前会话。幂等：token 已失效/已撤销时同样返回 200。"""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise unauthorized("Not authenticated")

    try:
        payload = decode_token(credentials.credentials)
    except HTTPException:
        # 已过期的 token 再来登出：会话本来就已经失效，按幂等处理
        return {"message": "已登出", "revoked": False}

    jti = payload.get("jti")
    revoked = revoke(jti, "logout") if jti else False
    return {"message": "已登出", "revoked": revoked}


@app.post("/auth/logout-all")
def logout_all(user: dict = Depends(authenticate)):
    """撤销当前用户的全部会话（换机、丢失设备时使用）。"""
    revoked = revoke_all_for_user(user["id"], "logout_all")
    return {"message": "已登出所有会话", "revoked": revoked}


@app.get("/auth/me", response_model=MeResponse)
def me(user: dict = Depends(authenticate)):
    """受保护端点：同时用于客户端心跳续期。"""
    with connect() as conn:
        row = get_user(conn, user["id"])
    return MeResponse(
        id=user["id"],
        role=row["role"] if row else "unknown",
        issued_at=iso(user["issued_at"]),
        expires_at=iso(user["expires_at"]),
        expires_in=max(0, int(user["expires_at"] - now())),
    )


@app.get("/health")
def health():
    """探活接口（不需要鉴权）。"""
    return {"status": "ok"}


if __name__ == "__main__":
    # 启动逻辑已移到 server/main.py，这里只给出提示，避免旧命令静默退出
    print("此文件只负责组装 FastAPI app；请使用 `python server/main.py` 启动服务端。")

