from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
import bcrypt
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel

# ---------- 配置 ----------
SECRET_KEY = "dev-secret-change-me"          # 生产环境用环境变量注入
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

app = FastAPI(title="Auth Test Server")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

# -----
def hash_password(password: str) -> str:
    # bcrypt 要求密码必须是 bytes 类型
    pwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(pwd_bytes, salt)
    return hashed.decode('utf-8')  # 存库时转成 str

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(
        plain_password.encode('utf-8'),
        hashed_password.encode('utf-8')
    )

# ---------- 模拟用户库（内存） ----------
# 真实项目中密码哈希由注册接口生成，这里预置一个测试用户
_FAKE_DB: dict[str, str] = {}
_TOKEN_BLACKLIST: set[str] = set()           # 登出后 token 进入黑名单


def _seed_user():
    """预置测试用户"""
    _FAKE_DB["admin"] = hash_password("hitsz")


_seed_user()


# ---------- 请求/响应模型 ----------
class LoginRequest(BaseModel):
    id: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---------- 工具函数 ----------
def create_access_token(username: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": username, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None


def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """依赖项：从 token 解析当前用户，校验黑名单"""
    if token in _TOKEN_BLACKLIST:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
        )
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )
    return {"id": payload["sub"]}  # 返回用户ID


# ---------- 端点 ----------
@app.post("/auth/login", response_model=TokenResponse)
def login(req: LoginRequest):
    """验证账号密码，成功返回 JWT"""
    stored_hash = _FAKE_DB.get(req.id)
    if not stored_hash or not verify_password(req.password, stored_hash):
        # 统一提示，不区分"用户不存在"和"密码错误"
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="账号或密码错误",
        )
    token = create_access_token(req.id)
    return TokenResponse(access_token=token)


@app.post("/auth/logout")
def logout(token: str = Depends(oauth2_scheme)):
    """将当前 token 加入黑名单，使其立即失效"""
    _TOKEN_BLACKLIST.add(token)
    return {"message": "已登出"}


@app.get("/auth/me")
def me(user_info: dict = Depends(get_current_user)):
    """受保护端点：验证 token 是否有效"""
    return user_info


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)