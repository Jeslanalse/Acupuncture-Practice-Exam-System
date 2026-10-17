from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget

from .ui_login import Ui_Login

class Login(QWidget):

    login_success = Signal()

    def __init__(self, client):
        super().__init__()
        self.client = client

        self.ui = Ui_Login()
        self.ui.setupUi(self)

        self.ui.btnLogin.clicked.connect(self.on_login_clicked)
        self.ui.account.textChanged.connect(self.clear_warning)
        self.ui.password.textChanged.connect(self.clear_warning)

        self.ui.account.returnPressed.connect(lambda: self.ui.password.setFocus())
        self.ui.password.returnPressed.connect(lambda: self.on_login_clicked())

        self.ui.account.setFocus()

    def clear_warning(self):
        self.ui.textWarning.setText("")

    def on_login_clicked(self):

        self.ui.btnLogin.setEnabled(False)
        self.ui.account.setEnabled(False)
        self.ui.password.setEnabled(False)

        account = self.ui.account.text()
        password = self.ui.password.text()

        if not account or not password:
            self.on_login_failed("请输入账号和密码")
            return

        if not self.client.login(account, password):
            if self.client.is_tls_error():
                self.on_login_failed("安全连接失败，请确认证书已生成（先启动服务端）")
            elif self.client.last_status is None:
                self.on_login_failed("无法连接服务器，请确认服务已启动")
            elif self.client.last_status == 401:
                self.on_login_failed("账号或密码错误")
            else:
                self.on_login_failed(f"登录失败（HTTP {self.client.last_status}）")
        else:
            self.on_login_success()

    def on_login_success(self):
        self.login_success.emit()

    def show_warning(self, message: str):
        self.ui.textWarning.setStyleSheet("color: red;")
        self.ui.textWarning.setText(message)

    def on_login_failed(self, message: str):
        self.show_warning(message)

        self.ui.account.setEnabled(True)
        self.ui.password.setEnabled(True)
        self.ui.btnLogin.setEnabled(True)