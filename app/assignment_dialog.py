"""作业新增/修改对话框：题目、描述、起止时间、标准手法（内置「人工批阅」）。"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QDateTime, Qt
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QVBoxLayout

from .helpers import MANUAL_TECHNIQUE_NAME
from .ui_assignmentdialog import Ui_AssignmentDialog

MAX_TITLE_LENGTH = 32
MAX_DESCRIPTION_LENGTH = 2000


class AssignmentDialog(QDialog):

    def __init__(self, parent, client, techniques: list[dict], assignment: Optional[dict] = None):
        super().__init__(parent)
        self.ui = Ui_AssignmentDialog()
        self.ui.setupUi(self)

        self.client = client
        self.assignment = assignment
        self.setWindowTitle("修改作业" if assignment else "布置作业")

        # UI 里没给错误标签设颜色，这里补上
        self.ui.labelAssignmentError.setStyleSheet("color: #b23b3b;")
        self.ui.labelAssignmentError.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # UI 的控件都包在一个固定几何的 QWidget 里，放进对话框布局才能随窗口缩放
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.ui.verticalLayoutWidget)

        self._fill_techniques(techniques)
        self._fill_fields()

        self.ui.buttonBox.button(QDialogButtonBox.StandardButton.Ok).setText("确定")
        self.ui.buttonBox.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        self.ui.buttonBox.accepted.connect(self._on_accept)
        self.ui.buttonBox.rejected.connect(self.reject)

    # ---------- 初始化 ----------
    def _fill_techniques(self, techniques: list[dict]):
        combo = self.ui.comboAssignmentTechnique
        combo.clear()
        combo.addItem(MANUAL_TECHNIQUE_NAME, None)
        for technique in techniques:
            combo.addItem(technique["name"], technique["id"])

    def _fill_fields(self):
        now = QDateTime.currentDateTime()
        if self.assignment:
            self.ui.editAssignmentTitle.setText(self.assignment.get("title", ""))
            self.ui.textAssignmentDescription.setPlainText(self.assignment.get("description", ""))
            start = QDateTime.fromSecsSinceEpoch(int(self.assignment["start_at"]))
            end_value = self.assignment.get("end_at")
            end = (
                QDateTime.fromSecsSinceEpoch(int(end_value))
                if end_value is not None
                else start.addDays(7)
            )
            technique_id = self.assignment.get("technique_id")
            index = self.ui.comboAssignmentTechnique.findData(technique_id)
            self.ui.comboAssignmentTechnique.setCurrentIndex(index if index >= 0 else 0)
        else:
            start = now
            end = now.addDays(7)

        self.ui.dateAssignmentStart.setDateTime(start)
        self.ui.dateAssignmentEnd.setDateTime(end)
        self.ui.editAssignmentTitle.setFocus()

    # ---------- 提交 ----------
    def _error(self, message: str):
        self.ui.labelAssignmentError.setText(message)

    def _payload(self) -> dict:
        return {
            "title": self.ui.editAssignmentTitle.text().strip(),
            "description": self.ui.textAssignmentDescription.toPlainText().strip(),
            "start_at": float(self.ui.dateAssignmentStart.dateTime().toSecsSinceEpoch()),
            "end_at": float(self.ui.dateAssignmentEnd.dateTime().toSecsSinceEpoch()),
            "technique_id": self.ui.comboAssignmentTechnique.currentData(),
        }

    def _on_accept(self):
        payload = self._payload()
        if not payload["title"]:
            self._error("题目不能为空")
            return
        if len(payload["title"]) > MAX_TITLE_LENGTH:
            self._error(f"题目不能超过 {MAX_TITLE_LENGTH} 个字符")
            return
        if len(payload["description"]) > MAX_DESCRIPTION_LENGTH:
            self._error(f"描述不能超过 {MAX_DESCRIPTION_LENGTH} 个字符")
            return
        if payload["end_at"] <= payload["start_at"]:
            self._error("截止时间必须晚于起始时间")
            return

        if self.assignment:
            response = self.client.update_assignment(self.assignment["id"], payload)
        else:
            response = self.client.create_assignment(payload)

        if response is None:
            self._error(self.client.error_text())
            return
        self.accept()
