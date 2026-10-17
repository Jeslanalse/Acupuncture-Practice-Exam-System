from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from PySide6.QtGui import QCloseEvent

from .assignment_page import AssignmentPage
from .student_page import StudentPage
from .technique_page import TechniquePage
from .ui_mainwindow import Ui_MainWindow

# 心跳间隔：服务端空闲超时为 20 分钟，5 分钟一次可留足余量
HEARTBEAT_INTERVAL_MS = 5 * 60 * 1000


class MainWindow(QWidget):

    logout = Signal()
    session_expired = Signal()

    def __init__(self, client):
        super().__init__()
        self.client = client

        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self._build_layout()

        self.technique_page = TechniquePage(self.ui, client, self.reload_techniques)
        self.assignment_page = AssignmentPage(self.ui, client, self.reload_gradebook)
        self.student_page = StudentPage(self.ui, client, self.reload_gradebook)

        self.ui.btnLogout.clicked.connect(self.on_logout_clicked)

        self._heartbeat = QTimer(self)
        self._heartbeat.setInterval(HEARTBEAT_INTERVAL_MS)
        self._heartbeat.timeout.connect(self._check_session)
        self._heartbeat.start()

        self.ui.textGreets.setText(f"早上好、中午好、晚上好！{self.client.get_user_id()}")
        self.reload_all()

    # ---------- 布局 ----------
    def _build_layout(self):
        """把 UI 里的绝对定位控件装进布局，窗口缩放时不错位。"""
        if self.layout() is not None:
            return
        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 8, 10, 8)
        outer.setSpacing(8)

        top_bar = QHBoxLayout()
        top_bar.addStretch(1)
        top_bar.addWidget(self.ui.textGreets)
        top_bar.addWidget(self.ui.btnLogout)

        outer.addLayout(top_bar)
        outer.addWidget(self.ui.tabWidget)
        self.setMinimumSize(1000, 640)

    # ---------- 数据加载 ----------
    def reload_all(self):
        self.reload_techniques()
        self.reload_gradebook()

    def reload_gradebook(self):
        data = self.client.get_gradebook()
        if not isinstance(data, dict):
            message = f"加载失败：{self.client.error_text()}"
            self.ui.labelStudentSummary.setText(message)
            self.ui.labelAssignmentSummary.setText(message)
            self._handle_auth_error()
            return

        self.student_page.set_data(data)
        self.assignment_page.set_data(data.get("assignments") or [])

    def reload_techniques(self):
        data = self.client.get_techniques()
        items = data.get("items", []) if isinstance(data, dict) else []
        self.technique_page.set_data(items)
        self.assignment_page.set_techniques(items)
        if not isinstance(data, dict):
            self.ui.labelTechniqueSummary.setText(f"加载失败：{self.client.error_text()}")
            self._handle_auth_error()

    def _handle_auth_error(self):
        if self.client.is_session_expired():
            self._heartbeat.stop()
            self.session_expired.emit()

    # ---------- 会话 ----------
    def _check_session(self):
        """心跳续期；服务端判定会话失效时退回登录页。"""
        if not self.client.heartbeat() and self.client.is_session_expired():
            self._heartbeat.stop()
            self.session_expired.emit()

    def on_logout_clicked(self):
        self._heartbeat.stop()
        self.ui.btnLogout.setEnabled(False)
        self.client.logout()
        self.logout.emit()

    def closeEvent(self, event: QCloseEvent):
        """直接关窗口（没点退出登录）时也要撤销服务端会话，避免留下可用的悬挂 token。"""
        self._heartbeat.stop()
        if self.client.token:
            self.client.logout()
        event.accept()
