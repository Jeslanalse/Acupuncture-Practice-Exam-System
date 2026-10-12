from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QCloseEvent

from .ui_mainwindow import Ui_MainWindow

class MainWindow(QWidget):

    logout = Signal()

    token: str = None

    def __init__(self, client):
        super().__init__()
        self.client = client

        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self.ui.btnLogout.clicked.connect(self.on_logout_clicked)

        self.ui.textGreets.setText(f"早上好、中午好、晚上好！{self.client.get_user_id()}")

    def on_logout_clicked(self):
        self.ui.btnLogout.setEnabled(False)
        self.client.logout()
        self.logout.emit()