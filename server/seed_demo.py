"""可选脚本：向本地数据库写入演示数据（学生 / 作业 / 成绩），方便教师端联调。

用法（先启动过服务端，或让脚本自动建表）：

    python server/seed_demo.py

学生账号密码统一为 `hitsz`，归属教师 `admin`。脚本可重复执行，不会重复插入。
"""

from __future__ import annotations

import time

try:
    from .db import connect, init_db
    from .security import hash_password, seed_users
except ImportError:  # 直接运行 python server/seed_demo.py
    from db import connect, init_db
    from security import hash_password, seed_users

TEACHER_ID = "admin"
STUDENT_PASSWORD = "hitsz"

STUDENTS = [
    ("2023001", "张三"),
    ("2023002", "李四"),
    ("2023003", "王五"),
    ("2023004", "赵六"),
    ("2023005", "孙七"),
]

# (id, 题目, 描述, 起始偏移天数, 截止偏移天数)
ASSIGNMENTS = [
    ("demo-1", "捻转手法练习", "练习捻转手法，保持角度与频率稳定。", -2, 5),
    ("demo-2", "提插手法练习", "提插幅度均匀，注意进针深度控制。", -1, 6),
    ("demo-3", "进针角度考核", "按标准角度完成进针，教师人工批阅。", 1, 8),
    ("demo-4", "综合手法测验", "综合考核，已截止，用于查看状态列。", -10, -1),
]

# 学生 id -> {作业 id: 分数}
SCORES = {
    "2023001": {"demo-1": 88, "demo-2": 92, "demo-3": 90},
    "2023002": {"demo-1": 76, "demo-2": 81, "demo-4": 70},
    "2023003": {"demo-1": 95, "demo-2": 89, "demo-3": 93, "demo-4": 85},
    "2023004": {"demo-2": 68, "demo-3": 74},
    "2023005": {"demo-1": 82, "demo-4": 79},
}


def main() -> None:
    init_db()
    seed_users()
    now = time.time()

    with connect() as conn:
        for student_id, name in STUDENTS:
            exists = conn.execute("SELECT id FROM users WHERE id = ?", (student_id,)).fetchone()
            if exists is not None:
                continue
            conn.execute(
                "INSERT INTO users"
                " (id, password_hash, role, display_name, is_active, teacher_id, created_at)"
                " VALUES (?, ?, 'student', ?, 1, ?, ?)",
                (student_id, hash_password(STUDENT_PASSWORD), name, TEACHER_ID, now),
            )

        for assignment_id, title, description, start_days, end_days in ASSIGNMENTS:
            exists = conn.execute(
                "SELECT id FROM assignments WHERE id = ?", (assignment_id,)
            ).fetchone()
            if exists is not None:
                continue
            conn.execute(
                "INSERT INTO assignments"
                " (id, teacher_id, title, description, start_at, end_at,"
                "  technique_id, technique_name, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?, NULL, ?, ?, ?)",
                (
                    assignment_id, TEACHER_ID, title, description,
                    now + start_days * 86400, now + end_days * 86400,
                    "人工批阅", now, now,
                ),
            )

        for student_id, scores in SCORES.items():
            for assignment_id, score in scores.items():
                conn.execute(
                    "INSERT INTO scores (assignment_id, student_id, score, updated_at)"
                    " VALUES (?, ?, ?, ?)"
                    " ON CONFLICT(assignment_id, student_id) DO NOTHING",
                    (assignment_id, student_id, score, now),
                )

    print(
        f"演示数据就绪：教师 {TEACHER_ID}，学生 {len(STUDENTS)} 名，"
        f"作业 {len(ASSIGNMENTS)} 项（学生密码 {STUDENT_PASSWORD}）"
    )


if __name__ == "__main__":
    main()
