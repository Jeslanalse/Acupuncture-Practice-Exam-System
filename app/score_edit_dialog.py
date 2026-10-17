"""成绩批量修改对话框：只支持把选中的单元格设为同一个分数。"""

from __future__ import annotations

from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QMessageBox

from .ui_scoreeditdialog import Ui_Dialog


class ScoreEditDialog(QDialog):

    def __init__(self, parent=None, cells: int = 0, students: int = 0, assignments: int = 0):
        super().__init__(parent)
        self.ui = Ui_Dialog()
        self.ui.setupUi(self)

        if cells:
            self.setWindowTitle(f"修改成绩（{cells} 个单元格）")
            self.ui.label.setToolTip(f"涉及 {students} 名学生、{assignments} 项作业")
        else:
            self.setWindowTitle("修改成绩")

        self.ui.score.setMaxLength(3)
        self.ui.score.setPlaceholderText("0-100")
        self.ui.score.setValidator(QIntValidator(0, 100, self))
        self.ui.score.setFocus()

        self.ui.buttonBox.button(QDialogButtonBox.StandardButton.Ok).setText("确定")
        self.ui.buttonBox.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        self.ui.buttonBox.accepted.connect(self._on_accept)
        self.ui.buttonBox.rejected.connect(self.reject)

    def _on_accept(self):
        text = self.ui.score.text().strip()
        if not text.isdigit() or not 0 <= int(text) <= 100:
            QMessageBox.warning(self, "输入有误", "请输入 0-100 的整数分数")
            return
        self.accept()

    def value(self) -> int:
        return int(self.ui.score.text().strip())
