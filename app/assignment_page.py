"""作业页：列出全部作业，支持新增、修改、删除。"""

from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QMessageBox,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .assignment_dialog import AssignmentDialog
from .helpers import assignment_status, format_timestamp

TITLE_COLUMN = 0
START_COLUMN = 1
END_COLUMN = 2
TECHNIQUE_COLUMN = 3
STATUS_COLUMN = 4
DESCRIPTION_COLUMN = 5


class AssignmentPage:

    def __init__(self, ui, client, on_reload: Callable[[], None]):
        self.ui = ui
        self.client = client
        self.on_reload = on_reload
        self.tab: QWidget = ui.tab_4
        self.table = ui.tableAssignments

        self._items: list[dict] = []
        self._techniques: list[dict] = []

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

        first_row = QHBoxLayout()
        first_row.setSpacing(8)
        for widget in (
            self.ui.assignmentSearchEdit,
            self.ui.btnAssignmentSearch,
            self.ui.btnAssignmentAll,
        ):
            first_row.addWidget(widget)
        first_row.addStretch(1)
        for widget in (
            self.ui.btnAddAssignment,
            self.ui.btnEditAssignment,
            self.ui.btnDeleteAssignment,
        ):
            first_row.addWidget(widget)

        second_row = QHBoxLayout()
        second_row.setSpacing(8)
        second_row.addWidget(self.ui.labelAssignmentSummary)
        second_row.addStretch(1)
        second_row.addWidget(self.ui.btnRefreshAssignments)

        layout.addLayout(first_row)
        layout.addLayout(second_row)
        layout.addWidget(self.table)

    def _setup_table(self):
        table = self.table
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setStretchLastSection(True)
        table.setWordWrap(False)

    def _connect(self):
        self.ui.assignmentSearchEdit.textChanged.connect(self._apply_filter)
        self.ui.assignmentSearchEdit.returnPressed.connect(self._apply_filter)
        self.ui.btnAssignmentSearch.clicked.connect(self._apply_filter)
        self.ui.btnAssignmentAll.clicked.connect(self._show_all)
        self.ui.btnRefreshAssignments.clicked.connect(self.on_reload)
        self.ui.btnAddAssignment.clicked.connect(lambda: self._open_dialog(None))
        self.ui.btnEditAssignment.clicked.connect(self._edit_current)
        self.ui.btnDeleteAssignment.clicked.connect(self._delete_current)
        self.table.itemSelectionChanged.connect(self._update_buttons)
        self.table.cellDoubleClicked.connect(lambda *_: self._edit_current())

    # ---------- 数据 ----------
    def set_techniques(self, techniques: list[dict]):
        self._techniques = list(techniques or [])

    def set_data(self, assignments: list[dict]):
        self._items = list(assignments or [])
        self._rebuild()
        self._apply_filter()

    def _rebuild(self):
        table = self.table
        table.setUpdatesEnabled(False)
        table.clearContents()
        table.setRowCount(len(self._items))
        table.setColumnCount(6)

        for row, assignment in enumerate(self._items):
            title_item = QTableWidgetItem(assignment.get("title", ""))
            title_item.setData(Qt.ItemDataRole.UserRole, assignment.get("id"))
            title_item.setToolTip(assignment.get("description", ""))
            table.setItem(row, TITLE_COLUMN, title_item)

            table.setItem(
                row, START_COLUMN,
                QTableWidgetItem(format_timestamp(assignment.get("start_at"))),
            )
            table.setItem(
                row, END_COLUMN,
                QTableWidgetItem(format_timestamp(assignment.get("end_at"))),
            )
            table.setItem(
                row, TECHNIQUE_COLUMN,
                QTableWidgetItem(assignment.get("technique_name", "")),
            )

            status_text, color = assignment_status(
                assignment.get("start_at"), assignment.get("end_at")
            )
            status_item = QTableWidgetItem(status_text)
            status_item.setForeground(QColor(color))
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(row, STATUS_COLUMN, status_item)

            preview = (assignment.get("description") or "").replace("\n", " ")
            if len(preview) > 60:
                preview = preview[:60] + "…"
            description_item = QTableWidgetItem(preview)
            description_item.setToolTip(assignment.get("description", ""))
            table.setItem(row, DESCRIPTION_COLUMN, description_item)

        for column, width in (
            (TITLE_COLUMN, 220),
            (START_COLUMN, 160),
            (END_COLUMN, 160),
            (TECHNIQUE_COLUMN, 140),
            (STATUS_COLUMN, 90),
        ):
            table.setColumnWidth(column, width)

        table.setUpdatesEnabled(True)
        self._update_buttons()

    def _apply_filter(self):
        keyword = self.ui.assignmentSearchEdit.text().strip().lower()
        visible = 0
        for row, assignment in enumerate(self._items):
            haystack = " ".join(
                str(assignment.get(key, ""))
                for key in ("title", "description", "technique_name")
            ).lower()
            match = not keyword or keyword in haystack
            self.table.setRowHidden(row, not match)
            if match:
                visible += 1

        total = len(self._items)
        text = f"共 {visible} 项作业"
        if keyword:
            text += f"（筛选自 {total} 项）"
        self.ui.labelAssignmentSummary.setText(text)

        self.table.clearSelection()
        self._update_buttons()

    def _show_all(self):
        self.ui.assignmentSearchEdit.clear()
        self._apply_filter()

    # ---------- 选择 ----------
    def _current(self) -> Optional[dict]:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        row = rows[0].row()
        if row < 0 or row >= len(self._items):
            return None
        return self._items[row]

    def _update_buttons(self):
        has_selection = self._current() is not None
        self.ui.btnEditAssignment.setEnabled(has_selection)
        self.ui.btnDeleteAssignment.setEnabled(has_selection)

    # ---------- 增删改 ----------
    def _open_dialog(self, assignment: Optional[dict]):
        dialog = AssignmentDialog(self.tab, self.client, self._techniques, assignment)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.on_reload()

    def _edit_current(self):
        assignment = self._current()
        if assignment is not None:
            self._open_dialog(assignment)

    def _delete_current(self):
        assignment = self._current()
        if assignment is None:
            return
        answer = QMessageBox.question(
            self.tab,
            "删除作业",
            f"确定删除「{assignment.get('title', '')}」及其全部成绩吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        response = self.client.delete_assignment(assignment["id"])
        if response is None:
            QMessageBox.warning(self.tab, "删除失败", self.client.error_text())
            return
        self.on_reload()
