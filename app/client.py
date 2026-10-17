"""HTTP 客户端：封装鉴权接口并持有当前会话 token。

安全默认：
- 服务端是 HTTPS，客户端用本地 CA（`server/certs/ca.crt`）做**完整校验**，
  绝不使用 `verify=False`；可用 `APP_CA_BUNDLE` 指定其他信任锚；
- 请求超时，服务未启动时不会把界面卡死；
- `last_status` / `last_error_kind` 区分「服务没起来」「证书问题」「登录态失效」；
- 会话由服务端白名单管理：客户端主动登出即撤销，异常退出由空闲超时兜底。
"""

from __future__ import annotations

import os
from typing import Any, Optional

import requests

_HERE = os.path.dirname(os.path.abspath(__file__))


def _default_ca_bundle() -> str:
    return os.path.join(os.path.dirname(_HERE), "server", "certs", "ca.crt")


class Client:

    URL_BASE = "https://127.0.0.1:8000/"
    TIMEOUT = 5.0
    LOGOUT_TIMEOUT = 2.0

    def __init__(self, token: Optional[str] = None):
        self.token = token
        self.base = os.environ.get("APP_API_BASE", self.URL_BASE)
        self.ca_bundle = os.environ.get("APP_CA_BUNDLE", _default_ca_bundle())
        self.last_status: Optional[int] = None
        self.last_error: Optional[str] = None
        self.last_error_kind: Optional[str] = None

    def _request(self, method: str, endpoint: str, timeout: Optional[float] = None, **kwargs) -> Optional[Any]:
        url = self.base + endpoint
        headers = kwargs.pop("headers", {})
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        self.last_status = None
        self.last_error = None
        self.last_error_kind = None

        https = url.startswith("https://")
        if https and not os.path.exists(self.ca_bundle):
            self.last_error = f"CA bundle not found: {self.ca_bundle}"
            self.last_error_kind = "tls"
            print(f"[client] {self.last_error}")
            return None

        try:
            resp = requests.request(
                method, url, headers=headers, verify=self.ca_bundle if https else True,
                timeout=self.TIMEOUT if timeout is None else timeout, **kwargs,
            )
            self.last_status = resp.status_code
            resp.raise_for_status()
            try:
                return resp.json()
            except ValueError:
                return {}
        except requests.RequestException as exc:
            response = getattr(exc, "response", None)
            if response is not None:
                self.last_status = response.status_code
            detail = None
            if response is not None:
                try:
                    detail = response.json().get("detail")
                except ValueError:
                    detail = (response.text or "").strip()[:200]
            self.last_error = detail if isinstance(detail, str) and detail else str(exc)
            if isinstance(exc, requests.exceptions.SSLError):
                self.last_error_kind = "tls"
            elif response is not None:
                self.last_error_kind = "http"
            else:
                self.last_error_kind = "network"
            print(f"[client] 请求失败：{exc}")
            return None
        except OSError as exc:  # CA 文件损坏等
            self.last_error = str(exc)
            self.last_error_kind = "tls"
            print(f"[client] 请求失败：{exc}")
            return None

    def login(self, id: str, password: str) -> bool:
        resp = self._request("POST", "auth/login", json={"id": id, "password": password})
        if resp and "access_token" in resp:
            self.token = resp["access_token"]
            return True
        return False

    def logout(self) -> bool:
        """尽力撤销服务端会话；无论网络是否成功，本地 token 一律清空。"""
        try:
            resp = self._request("POST", "auth/logout", timeout=self.LOGOUT_TIMEOUT)
            return bool(resp and "message" in resp)
        finally:
            self.token = None

    def get_user_id(self) -> str:
        resp = self._request("GET", "auth/me")
        if isinstance(resp, dict) and resp.get("id"):
            return resp["id"]
        return "未知用户"

    def heartbeat(self) -> bool:
        """续期会话（服务端刷新 last_seen）；返回会话是否仍然有效。"""
        if not self.token:
            return False
        resp = self._request("GET", "auth/me")
        return isinstance(resp, dict) and bool(resp.get("id"))

    def is_session_expired(self) -> bool:
        """最近一次请求是否因登录态失效被拒（401）。"""
        return self.last_status == 401

    def is_tls_error(self) -> bool:
        """最近一次失败是否属于证书/连接安全问题。"""
        return self.last_error_kind == "tls"

    def error_text(self) -> str:
        """给界面展示的错误文本：优先服务端 detail，其次 HTTP 状态，最后兜底。"""
        if self.last_error:
            return self.last_error
        if self.last_status is not None:
            return f"服务端返回 HTTP {self.last_status}"
        return "未知错误"

    # ---------- 教师端：成绩册 / 作业 / 成绩 / 手法 ----------
    def get_gradebook(self) -> Optional[dict]:
        return self._request("GET", "teacher/gradebook")

    def create_assignment(self, payload: dict) -> Optional[dict]:
        return self._request("POST", "teacher/assignments", json=payload)

    def update_assignment(self, assignment_id: str, payload: dict) -> Optional[dict]:
        return self._request("PUT", f"teacher/assignments/{assignment_id}", json=payload)

    def delete_assignment(self, assignment_id: str) -> Optional[dict]:
        return self._request("DELETE", f"teacher/assignments/{assignment_id}")

    def batch_update_scores(self, cells: list[dict], score: int) -> Optional[dict]:
        return self._request("PUT", "teacher/scores", json={"cells": cells, "score": score})

    def get_techniques(self) -> Optional[dict]:
        return self._request("GET", "techniques")

    def delete_technique(self, technique_id: str) -> Optional[dict]:
        return self._request("DELETE", f"techniques/{technique_id}")
