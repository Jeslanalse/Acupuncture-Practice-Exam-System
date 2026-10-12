from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QWidget
import requests

class Client:

    URL_BASE = "http://127.0.0.1:8000/"

    def __init__(self, token: str = None):
        self.token = token

    def _request(self, method: str, endpoint: str, **kwargs):
        url = self.URL_BASE + endpoint
        headers = kwargs.pop("headers", {})
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        try:
            resp = requests.request(method, url, headers=headers, **kwargs)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            print(f"[client] 请求失败：{e}")
            return None

    def login(self, id: str, password: str) -> bool:
        try:
            resp = self._request("POST", "auth/login",
                                 json={"id": id, "password": password})
            if resp and "access_token" in resp:
                self.token = resp["access_token"]
                return True
        except requests.RequestException as e:
            print(f"[client] 登录失败：{e}")
        return False

    def logout(self) -> bool:
        try:
            resp = self._request("POST", "auth/logout")
            if resp and "message" in resp:
                self.token = None
                return True
        except requests.RequestException as e:
            print(f"[client] 登出失败：{e}")
        return False

    def get_user_id(self) -> str:
        try:
            resp = self._request("GET", "auth/me")
            return resp.get("id") if resp else "未知用户"
        except requests.RequestException as e:
            print(f"[client] 获取用户ID失败：{e}")
            return "未知用户"