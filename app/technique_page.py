"""手法页：展示手法列表（只读 + 删除）。

新增手法依赖外部设备调用，本版本不实现，点击「新增」只给出提示。
"""

from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QMessageBox,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .helpers import format_timestamp

NAME_COLUMN = 0
CREATED_COLUMN = 1
CREATOR_COLUMN = 2
DESCRIPTION_COLUMN = 3


class TechniquePage:

    def __init__(self, ui, client, on_reload: Callable[[], None]):
        self.ui = ui
        self.client = client
        self.on_reload = on_reload
        self.tab: QWidget = ui.tab_2
        self.table = ui.tableTechniques

        self._items: list[dict] = []

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
            self.ui.techniqueSearchEdit,
            self.ui.btnTechniqueSearch,
            self.ui.btnTechniqueAll,
        ):
            first_row.addWidget(widget)
        first_row.addStretch(1)
        first_row.addWidget(self.ui.btnAddTechnique)
        first_row.addWidget(self.ui.btnDeleteTechnique)

        second_row = QHBoxLayout()
        second_row.setSpacing(8)
        second_row.addWidget(self.ui.labelTechniqueSummary)
        second_row.addStretch(1)
        second_row.addWidget(self.ui.btnRefreshTechnique)

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
        self.ui.techniqueSearchEdit.textChanged.connect(self._apply_filter)
        self.ui.techniqueSearchEdit.returnPressed.connect(self._apply_filter)
        self.ui.btnTechniqueSearch.clicked.connect(self._apply_filter)
        self.ui.btnTechniqueAll.clicked.connect(self._show_all)
        self.ui.btnRefreshTechnique.clicked.connect(self.on_reload)
        self.ui.btnAddTechnique.clicked.connect(self._show_add_hint)
        self.ui.btnDeleteTechnique.clicked.connect(self._delete_current)
        self.table.itemSelectionChanged.connect(self._update_buttons)

    # ---------- 数据 ----------
    def set_data(self, items: list[dict]):
        self._items = list(items or [])
        self._rebuild()
        self._apply_filter()

    def _rebuild(self):
        table = self.table
        table.setUpdatesEnabled(False)
        table.clearContents()
        table.setRowCount(len(self._items))

        for row, technique in enumerate(self._items):
            name_item = QTableWidgetItem(technique.get("name", ""))
            name_item.setData(Qt.ItemDataRole.UserRole, technique.get("id"))
            table.setItem(row, NAME_COLUMN, name_item)

            table.setItem(
                row, CREATED_COLUMN,
                QTableWidgetItem(format_timestamp(technique.get("created_at"))),
            )
            table.setItem(
                row, CREATOR_COLUMN,
                QTableWidgetItem(technique.get("creator_name", "")),
            )

            description = technique.get("description", "")
            description_item = QTableWidgetItem(description.replace("\n", " "))
            description_item.setToolTip(description)
            table.setItem(row, DESCRIPTION_COLUMN, description_item)

        for column, width in (
            (NAME_COLUMN, 200),
            (CREATED_COLUMN, 170),
            (CREATOR_COLUMN, 140),
        ):
            table.setColumnWidth(column, width)

        table.setUpdatesEnabled(True)
        self._update_buttons()

    def _apply_filter(self):
        keyword = self.ui.techniqueSearchEdit.text().strip().lower()
        visible = 0
        for row, technique in enumerate(self._items):
            haystack = f"{technique.get('name', '')} {technique.get('description', '')}".lower()
            match = not keyword or keyword in haystack
            self.table.setRowHidden(row, not match)
            if match:
                visible += 1

        total = len(self._items)
        text = f"共 {visible} 项手法"
        if keyword:
            text += f"（筛选自 {total} 项）"
        self.ui.labelTechniqueSummary.setText(text)

        self.table.clearSelection()
        self._update_buttons()

    def _show_all(self):
        self.ui.techniqueSearchEdit.clear()
        self._apply_filter()

    # ---------- 操作 ----------
    def _current(self) -> Optional[dict]:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        row = rows[0].row()
        if row < 0 or row >= len(self._items):
            return None
        return self._items[row]

    def _update_buttons(self):
        self.ui.btnDeleteTechnique.setEnabled(self._current() is not None)

    def _show_add_hint(self):
        QMessageBox.information(
            self.tab,
            "暂未实现",
            "新增手法需要连接外部设备采集手法数据，当前版本暂不支持。",
        )

    def _delete_current(self):
        technique = self._current()
        if technique is None:
            return
        answer = QMessageBox.question(
            self.tab,
            "删除手法",
            f"确定删除手法「{technique.get('name', '')}」吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        response = self.client.delete_technique(technique["id"])
        if response is None:
            QMessageBox.warning(self.tab, "删除失败", self.client.error_text())
            return
        self.on_reload()
