"""学生页：列出教师名下学生与各次作业成绩，支持筛选和批量改分。

交互：
- 鼠标/Ctrl/Shift 选择单元格；点列头选中整列；点行号选中整行；
- 「修改成绩」把选中的成绩一次性设为同一分数；
- 姓名（第 0 列）与学号（第 1 列）不参与修改。
"""

from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QMessageBox,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .helpers import format_timestamp
from .score_edit_dialog import ScoreEditDialog

NAME_COLUMN = 0
ID_COLUMN = 1
FIRST_SCORE_COLUMN = 2


class StudentPage:

    def __init__(self, ui, client, on_reload: Callable[[], None]):
        self.ui = ui
        self.client = client
        self.on_reload = on_reload
        self.tab: QWidget = ui.tab_3
        self.table = ui.tableStudents

        self._students: list[dict] = []
        self._assignments: list[dict] = []
        self._scores: dict = {}

        self._build_layout()
        self._setup_table()
        self._connect()

    # ---------- 界面 ----------
    def _build_layout(self):
        if self.tab.layout() is not None:
            return
        layout = QVBoxLayout(self.tab)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        bar = QHBoxLayout()
        bar.setSpacing(8)
        for widget in (self.ui.studentSearchEdit, self.ui.btnStudentSearch, self.ui.btnStudentAll):
            bar.addWidget(widget)
        bar.addStretch(1)
        bar.addWidget(self.ui.labelStudentSummary)
        bar.addWidget(self.ui.btnRefreshStudents)
        bar.addWidget(self.ui.btnEditScores)
        layout.addLayout(bar)
        layout.addWidget(self.table)

    def _setup_table(self):
        table = self.table
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(True)
        table.horizontalHeader().setSectionsClickable(True)
        table.horizontalHeader().setStretchLastSection(True)
        table.setWordWrap(False)

    def _connect(self):
        self.ui.btnStudentSearch.clicked.connect(self._apply_filter)
        self.ui.btnStudentAll.clicked.connect(self._show_all)
        self.ui.btnRefreshStudents.clicked.connect(self.on_reload)
        self.ui.btnEditScores.clicked.connect(self._edit_scores)
        self.ui.studentSearchEdit.textChanged.connect(self._apply_filter)
        self.ui.studentSearchEdit.returnPressed.connect(self._apply_filter)
        self.table.itemSelectionChanged.connect(self._update_edit_button)
        self.table.horizontalHeader().sectionClicked.connect(self._on_header_clicked)
        self.table.verticalHeader().sectionClicked.connect(self._on_row_clicked)

    # ---------- 数据 ----------
    def set_data(self, data: dict):
        self._students = data.get("students") or []
        self._assignments = data.get("assignments") or []
        self._scores = data.get("scores") or {}
        self._rebuild()
        self._apply_filter()

    def _rebuild(self):
        table = self.table
        table.setUpdatesEnabled(False)
        table.clear()
        column_count = FIRST_SCORE_COLUMN + len(self._assignments)
        table.setColumnCount(column_count)
        table.setHorizontalHeaderLabels(
            ["姓名", "学号"] + [assignment.get("title", "") for assignment in self._assignments]
        )
        table.setRowCount(len(self._students))

        for row, student in enumerate(self._students):
            name_item = QTableWidgetItem(student.get("name") or student.get("id", ""))
            name_item.setData(Qt.ItemDataRole.UserRole, student.get("id"))
            name_item.setToolTip(student.get("name") or "")
            table.setItem(row, NAME_COLUMN, name_item)

            id_item = QTableWidgetItem(student.get("id", ""))
            table.setItem(row, ID_COLUMN, id_item)

            for index, assignment in enumerate(self._assignments):
                score = (self._scores.get(student.get("id")) or {}).get(assignment.get("id"))
                item = QTableWidgetItem("" if score is None else str(score))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setData(
                    Qt.ItemDataRole.UserRole, (student.get("id"), assignment.get("id"))
                )
                table.setItem(row, FIRST_SCORE_COLUMN + index, item)

        for index, assignment in enumerate(self._assignments):
            column = FIRST_SCORE_COLUMN + index
            header = table.horizontalHeaderItem(column)
            if header is not None:
                header.setToolTip(
                    f"{assignment.get('title', '')}\n"
                    f"标准手法：{assignment.get('technique_name', '')}\n"
                    f"起始：{format_timestamp(assignment.get('start_at'))}\n"
                    f"截止：{format_timestamp(assignment.get('end_at'))}\n"
                    f"{assignment.get('description', '')}"
                )
            table.setColumnWidth(column, 150)

        table.setColumnWidth(NAME_COLUMN, 120)
        table.setColumnWidth(ID_COLUMN, 150)
        table.setUpdatesEnabled(True)
        self._update_edit_button()

    def _apply_filter(self):
        keyword = self.ui.studentSearchEdit.text().strip().lower()
        visible = 0
        for row, student in enumerate(self._students):
            name = (student.get("name") or "").lower()
            student_id = (student.get("id") or "").lower()
            match = not keyword or keyword in name or keyword in student_id
            self.table.setRowHidden(row, not match)
            if match:
                visible += 1

        total = len(self._students)
        text = f"共 {visible} 名学生"
        if keyword:
            text += f"（筛选自 {total} 名）"
        self.ui.labelStudentSummary.setText(text)

        self.table.clearSelection()
        self._update_edit_button()

    def _show_all(self):
        self.ui.studentSearchEdit.clear()
        self._apply_filter()

    # ---------- 选择 ----------
    def _visible_rows(self) -> list[int]:
        return [
            row for row in range(self.table.rowCount()) if not self.table.isRowHidden(row)
        ]

    def _on_header_clicked(self, column: int):
        if column < FIRST_SCORE_COLUMN:
            # 姓名/学号列不可修改：清空选择，避免误改上一次选中的成绩
            self.table.clearSelection()
            self._update_edit_button()
            return
        self.table.clearSelection()
        for row in self._visible_rows():
            self.table.setRangeSelected(_cell_range(row, column), True)
        self._update_edit_button()

    def _on_row_clicked(self, row: int):
        last_column = self.table.columnCount() - 1
        if last_column < FIRST_SCORE_COLUMN or row < 0 or row >= self.table.rowCount():
            return
        self.table.clearSelection()
        self.table.setRangeSelected(
            _range(row, FIRST_SCORE_COLUMN, row, last_column), True
        )
        self._update_edit_button()

    def selected_cells(self) -> list[dict]:
        cells: dict[tuple[str, str], dict] = {}
        for index in self.table.selectedIndexes():
            if index.column() < FIRST_SCORE_COLUMN:
                continue
            item = self.table.item(index.row(), index.column())
            if item is None:
                continue
            data = item.data(Qt.ItemDataRole.UserRole)
            if not data:
                continue
            student_id, assignment_id = data
            cells[(student_id, assignment_id)] = {
                "student_id": student_id,
                "assignment_id": assignment_id,
            }
        return list(cells.values())

    def _update_edit_button(self):
        count = len(self.selected_cells())
        self.ui.btnEditScores.setEnabled(count > 0)
        self.ui.btnEditScores.setText(f"修改成绩（{count}）" if count else "修改成绩")

    # ---------- 批量改分 ----------
    def _edit_scores(self):
        cells = self.selected_cells()
        if not cells:
            return
        students = {cell["student_id"] for cell in cells}
        assignments = {cell["assignment_id"] for cell in cells}

        dialog = ScoreEditDialog(self.tab, len(cells), len(students), len(assignments))
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        response = self.client.batch_update_scores(cells, dialog.value())
        if response is None:
            QMessageBox.warning(self.tab, "修改失败", self.client.error_text())
            return

        QMessageBox.information(
            self.tab, "修改成功", f"已更新 {response.get('updated', 0)} 个成绩"
        )
        self.on_reload()


def _cell_range(row: int, column: int):
    return _range(row, column, row, column)


def _range(top: int, left: int, bottom: int, right: int):
    from PySide6.QtWidgets import QTableWidgetSelectionRange

    return QTableWidgetSelectionRange(top, left, bottom, right)
