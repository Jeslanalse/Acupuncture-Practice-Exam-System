"""教师端界面共用的小工具。"""

from __future__ import annotations

import time
from datetime import datetime

MANUAL_TECHNIQUE_NAME = "人工批阅"

STATUS_COLORS = {
    "未开始": "#8a6d3b",
    "进行中": "#1e7b45",
    "已截止": "#b23b3b",
}


def format_timestamp(value) -> str:
    """把 epoch 秒格式成本地时间；None 显示「不限」。"""
    if value is None:
        return "不限"
    return datetime.fromtimestamp(float(value)).strftime("%Y/%m/%d %H:%M")


def assignment_status(start_at, end_at, current: float | None = None) -> tuple[str, str]:
    """返回 (状态文字, 颜色)。"""
    now = time.time() if current is None else current
    if start_at is not None and now < float(start_at):
        return "未开始", STATUS_COLORS["未开始"]
    if end_at is not None and now > float(end_at):
        return "已截止", STATUS_COLORS["已截止"]
    return "进行中", STATUS_COLORS["进行中"]
