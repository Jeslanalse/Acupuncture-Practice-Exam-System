"""教师端业务接口：学生成绩册、作业增删改查、批量改分、手法列表。

权限：只允许 role 为 `teacher` 或 `admin` 的账号访问；学生账号后续开发，
届时会新增学生端路由。所有数据都按「当前登录教师」做归属校验。

「标准手法」说明：`technique_id = None` 表示内置的「人工批阅」，不存于
`techniques` 表；选择已有手法时会把名称快照进作业，便于手法被删除后仍可展示。
"""

from __future__ import annotations

import time
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

try:
    from .db import connect
    from .security import authenticate, iso
except ImportError:  # 直接运行 python server/auth.py 时
    from db import connect
    from security import authenticate, iso

MANUAL_TECHNIQUE_NAME = "人工批阅"
MAX_TITLE_LENGTH = 32
MAX_DESCRIPTION_LENGTH = 2000
MAX_SCORE_CELLS = 5000

router = APIRouter(prefix="/teacher", tags=["teacher"])
technique_router = APIRouter(prefix="/techniques", tags=["techniques"])


# ---------- 请求模型 ----------
class AssignmentPayload(BaseModel):
    title: str = Field(min_length=1, max_length=MAX_TITLE_LENGTH)
    description: str = Field(default="", max_length=MAX_DESCRIPTION_LENGTH)
    start_at: float
    end_at: Optional[float] = None
    technique_id: Optional[str] = None


class ScoreCell(BaseModel):
    student_id: str
    assignment_id: str


class ScoresPayload(BaseModel):
    cells: list[ScoreCell] = Field(min_length=1, max_length=MAX_SCORE_CELLS)
    score: Optional[int] = Field(default=None, ge=0, le=100)


# ---------- 依赖与工具 ----------
def require_teacher(user: dict = Depends(authenticate)) -> dict:
    """校验当前账号是教师（或管理员）。"""
    with connect() as conn:
        row = conn.execute("SELECT role FROM users WHERE id = ?", (user["id"],)).fetchone()
    if row is None or row["role"] not in ("teacher", "admin"):
        raise HTTPException(status_code=403, detail="需要教师权限")
    return user


def _assignment_dict(row) -> dict:
    return {
        "id": row["id"],
        "title": row["title"],
        "description": row["description"],
        "start_at": row["start_at"],
        "end_at": row["end_at"],
        "technique_id": row["technique_id"],
        "technique_name": row["technique_name"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _technique_dict(row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "description": row["description"],
        "creator_id": row["creator_id"],
        "creator_name": row["creator_name"] if "creator_name" in row.keys() else "",
        "created_at": row["created_at"],
        "created_at_text": iso(row["created_at"]),
    }


def _validate_payload(payload: AssignmentPayload) -> str:
    title = payload.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="题目不能为空")
    if len(title) > MAX_TITLE_LENGTH:
        raise HTTPException(status_code=400, detail=f"题目不能超过 {MAX_TITLE_LENGTH} 个字符")
    if payload.end_at is not None and payload.end_at <= payload.start_at:
        raise HTTPException(status_code=400, detail="截止时间必须晚于起始时间")
    return title


def _resolve_technique(conn, technique_id: Optional[str]) -> tuple[Optional[str], str]:
    if technique_id is None:
        return None, MANUAL_TECHNIQUE_NAME
    row = conn.execute("SELECT id, name FROM techniques WHERE id = ?", (technique_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=400, detail="标准手法不存在")
    return row["id"], row["name"]


def _get_own_assignment(conn, assignment_id: str, teacher_id: str):
    row = conn.execute("SELECT * FROM assignments WHERE id = ?", (assignment_id,)).fetchone()
    if row is None or row["teacher_id"] != teacher_id:
        raise HTTPException(status_code=404, detail="作业不存在")
    return row


# ---------- 成绩册 ----------
@router.get("/gradebook")
def gradebook(user: dict = Depends(require_teacher)):
    """学生 × 作业 的成绩矩阵，学生页与作业页共用一次拉取。"""
    with connect() as conn:
        students = conn.execute(
            "SELECT id, display_name FROM users"
            " WHERE role = 'student' AND teacher_id = ? ORDER BY id",
            (user["id"],),
        ).fetchall()
        assignments = conn.execute(
            "SELECT * FROM assignments WHERE teacher_id = ?"
            " ORDER BY start_at ASC, title ASC",
            (user["id"],),
        ).fetchall()
        score_rows = conn.execute(
            "SELECT sc.student_id, sc.assignment_id, sc.score FROM scores sc"
            " JOIN assignments a ON a.id = sc.assignment_id"
            " WHERE a.teacher_id = ?",
            (user["id"],),
        ).fetchall()

    scores: dict[str, dict[str, int]] = {}
    for row in score_rows:
        scores.setdefault(row["student_id"], {})[row["assignment_id"]] = row["score"]

    return {
        "students": [
            {"id": row["id"], "name": row["display_name"] or row["id"]} for row in students
        ],
        "assignments": [_assignment_dict(row) for row in assignments],
        "scores": scores,
    }


# ---------- 作业 ----------
@router.get("/assignments")
def list_assignments(user: dict = Depends(require_teacher)):
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM assignments WHERE teacher_id = ?"
            " ORDER BY start_at ASC, title ASC",
            (user["id"],),
        ).fetchall()
    return {"items": [_assignment_dict(row) for row in rows]}


@router.post("/assignments")
def create_assignment(payload: AssignmentPayload, user: dict = Depends(require_teacher)):
    title = _validate_payload(payload)
    timestamp = time.time()
    with connect() as conn:
        technique_id, technique_name = _resolve_technique(conn, payload.technique_id)
        assignment_id = uuid.uuid4().hex[:16]
        conn.execute(
            "INSERT INTO assignments"
            " (id, teacher_id, title, description, start_at, end_at,"
            "  technique_id, technique_name, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                assignment_id, user["id"], title, payload.description.strip(),
                float(payload.start_at),
                None if payload.end_at is None else float(payload.end_at),
                technique_id, technique_name, timestamp, timestamp,
            ),
        )
        row = conn.execute("SELECT * FROM assignments WHERE id = ?", (assignment_id,)).fetchone()
    return _assignment_dict(row)


@router.put("/assignments/{assignment_id}")
def update_assignment(
    assignment_id: str, payload: AssignmentPayload, user: dict = Depends(require_teacher)
):
    title = _validate_payload(payload)
    with connect() as conn:
        _get_own_assignment(conn, assignment_id, user["id"])
        technique_id, technique_name = _resolve_technique(conn, payload.technique_id)
        conn.execute(
            "UPDATE assignments SET title = ?, description = ?, start_at = ?, end_at = ?,"
            " technique_id = ?, technique_name = ?, updated_at = ? WHERE id = ?",
            (
                title, payload.description.strip(), float(payload.start_at),
                None if payload.end_at is None else float(payload.end_at),
                technique_id, technique_name, time.time(), assignment_id,
            ),
        )
        row = conn.execute("SELECT * FROM assignments WHERE id = ?", (assignment_id,)).fetchone()
    return _assignment_dict(row)


@router.delete("/assignments/{assignment_id}")
def delete_assignment(assignment_id: str, user: dict = Depends(require_teacher)):
    with connect() as conn:
        _get_own_assignment(conn, assignment_id, user["id"])
        removed_scores = conn.execute(
            "SELECT COUNT(*) AS count FROM scores WHERE assignment_id = ?", (assignment_id,)
        ).fetchone()["count"]
        conn.execute("DELETE FROM assignments WHERE id = ?", (assignment_id,))
    return {"deleted": assignment_id, "removed_scores": removed_scores}


# ---------- 成绩 ----------
@router.put("/scores")
def update_scores(payload: ScoresPayload, user: dict = Depends(require_teacher)):
    """批量把选中的单元格设为同一分数；score=None 表示清空为未录入。"""
    cells = {(cell.student_id, cell.assignment_id) for cell in payload.cells}

    with connect() as conn:
        student_ids = {
            row["id"] for row in conn.execute(
                "SELECT id FROM users WHERE role = 'student' AND teacher_id = ?", (user["id"],)
            )
        }
        assignment_ids = {
            row["id"] for row in conn.execute(
                "SELECT id FROM assignments WHERE teacher_id = ?", (user["id"],)
            )
        }
        bad_students = {student_id for student_id, _ in cells if student_id not in student_ids}
        bad_assignments = {
            assignment_id for _, assignment_id in cells if assignment_id not in assignment_ids
        }
        if bad_students:
            raise HTTPException(status_code=400, detail="存在不属于当前教师的学生")
        if bad_assignments:
            raise HTTPException(status_code=400, detail="存在不属于当前教师的作业")

        timestamp = time.time()
        if payload.score is None:
            for student_id, assignment_id in cells:
                conn.execute(
                    "DELETE FROM scores WHERE student_id = ? AND assignment_id = ?",
                    (student_id, assignment_id),
                )
        else:
            for student_id, assignment_id in cells:
                conn.execute(
                    "INSERT INTO scores (assignment_id, student_id, score, updated_at)"
                    " VALUES (?, ?, ?, ?)"
                    " ON CONFLICT(assignment_id, student_id)"
                    " DO UPDATE SET score = excluded.score, updated_at = excluded.updated_at",
                    (assignment_id, student_id, payload.score, timestamp),
                )

    return {"updated": len(cells), "score": payload.score}


# ---------- 手法 ----------
@technique_router.get("")
def list_techniques(user: dict = Depends(require_teacher)):
    with connect() as conn:
        rows = conn.execute(
            "SELECT t.*, u.display_name AS creator_name FROM techniques t"
            " LEFT JOIN users u ON u.id = t.creator_id"
            " ORDER BY t.created_at DESC, t.name ASC"
        ).fetchall()
    return {"items": [_technique_dict(row) for row in rows]}


@technique_router.delete("/{technique_id}")
def delete_technique(technique_id: str, user: dict = Depends(require_teacher)):
    with connect() as conn:
        row = conn.execute("SELECT id FROM techniques WHERE id = ?", (technique_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="手法不存在")
        used = conn.execute(
            "SELECT COUNT(*) AS count FROM assignments WHERE technique_id = ?", (technique_id,)
        ).fetchone()["count"]
        if used:
            raise HTTPException(status_code=409, detail="该手法已被作业引用，无法删除")
        conn.execute("DELETE FROM techniques WHERE id = ?", (technique_id,))
    return {"deleted": technique_id}
