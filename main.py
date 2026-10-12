import sys
from PySide6.QtWidgets import QApplication
from app.login import Login
from app.mainwindow import MainWindow

from app.client import Client

class AppController:
    def __init__(self):
        self.client = Client()

        self.login_window = None
        self.main_window = None

    def _create_login_window(self):
        self.login_window = Login(self.client)
        self.login_window.login_success.connect(self.on_login_success)
        self.login_window.show()

    def _delete_login_window(self):
        if self.login_window:
            self.login_window.close()
            self.login_window.deleteLater()
            self.login_window = None

    def _create_main_window(self):
        self.main_window = MainWindow(self.client)
        self.main_window.logout.connect(self.on_logout)
        self.main_window.show()

    def _delete_main_window(self):
        if self.main_window:
            self.main_window.close()
            self.main_window.deleteLater()
            self.main_window = None

    def start(self):
        self._create_login_window()

    def on_login_success(self):
        self._delete_login_window()
        self._create_main_window()

    def on_logout(self):
        self._delete_main_window()
        self._create_login_window()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    controller = AppController()
    controller.start()
    sys.exit(app.exec())