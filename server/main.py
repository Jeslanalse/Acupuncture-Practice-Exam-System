"""服务端启动入口：加载 app、按配置启动 HTTPS/HTTP 的 uvicorn。

用法（在仓库根目录执行，任选其一）：

    python server/main.py
    python -m server.main

默认只监听 HTTPS（`https://127.0.0.1:8000`），首次启动会自动生成证书；
仅本机调试时可用 `AUTH_TLS=0` 回落明文 HTTP。

相关环境变量：`AUTH_PORT`、`AUTH_TLS`、`AUTH_TLS_DIR`，
其余（数据库、会话、密钥）见 `auth.py` / `security.py` 顶部说明。
"""

from __future__ import annotations

import os

import uvicorn

HOST = "127.0.0.1"
DEFAULT_PORT = 8000


def tls_enabled() -> bool:
    return os.environ.get("AUTH_TLS", "1").strip().lower() not in {"0", "false", "no"}


def main() -> int:
    try:  # python -m server.main
        from .auth import app
    except ImportError:  # python server/main.py
        from auth import app

    port = int(os.environ.get("AUTH_PORT", str(DEFAULT_PORT)))

    if tls_enabled():
        try:
            from .tls import ensure_certificate
        except ImportError:
            from tls import ensure_certificate

        cert_file, key_file = ensure_certificate()
        print(f"[server] HTTPS 已启用：https://{HOST}:{port}（证书：{cert_file}）")
        uvicorn.run(app, host=HOST, port=port, ssl_certfile=cert_file, ssl_keyfile=key_file)
    else:
        print(f"[server] 警告：AUTH_TLS=0，使用明文 HTTP：http://{HOST}:{port}，仅限本机调试")
        uvicorn.run(app, host=HOST, port=port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
