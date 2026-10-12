# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'login.ui'
##
## Created by: Qt User Interface Compiler version 6.12.0
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QApplication, QLabel, QLineEdit, QPushButton,
    QSizePolicy, QWidget)

class Ui_Login(object):
    def setupUi(self, Login):
        if not Login.objectName():
            Login.setObjectName(u"Login")
        Login.resize(400, 300)
        self.password = QLineEdit(Login)
        self.password.setObjectName(u"password")
        self.password.setGeometry(QRect(130, 150, 200, 30))
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setClearButtonEnabled(True)
        self.textPassword = QLabel(Login)
        self.textPassword.setObjectName(u"textPassword")
        self.textPassword.setGeometry(QRect(60, 150, 70, 30))
        font = QFont()
        font.setPointSize(16)
        self.textPassword.setFont(font)
        self.textPassword.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.btnLogin = QPushButton(Login)
        self.btnLogin.setObjectName(u"btnLogin")
        self.btnLogin.setGeometry(QRect(130, 200, 100, 30))
        self.btnLogin.setFont(font)
        self.account = QLineEdit(Login)
        self.account.setObjectName(u"account")
        self.account.setGeometry(QRect(130, 100, 200, 30))
        self.account.setClearButtonEnabled(True)
        self.textAccount = QLabel(Login)
        self.textAccount.setObjectName(u"textAccount")
        self.textAccount.setGeometry(QRect(60, 100, 70, 30))
        self.textAccount.setFont(font)
        self.textAccount.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.textWarning = QLabel(Login)
        self.textWarning.setObjectName(u"textWarning")
        self.textWarning.setGeometry(QRect(130, 50, 200, 30))
        self.textWarning.setFont(font)
        self.textWarning.setAlignment(Qt.AlignmentFlag.AlignCenter)
        QWidget.setTabOrder(self.account, self.password)
        QWidget.setTabOrder(self.password, self.btnLogin)

        self.retranslateUi(Login)

        QMetaObject.connectSlotsByName(Login)
    # setupUi

    def retranslateUi(self, Login):
        Login.setWindowTitle(QCoreApplication.translate("Login", u"\u9488\u523a\u624b\u6cd5\u89c4\u8303\u7cfb\u7edf - \u767b\u5f55", None))
        self.textPassword.setText(QCoreApplication.translate("Login", u"\u5bc6\u7801", None))
        self.btnLogin.setText(QCoreApplication.translate("Login", u"\u767b\u5f55", None))
        self.textAccount.setText(QCoreApplication.translate("Login", u"\u8d26\u53f7", None))
        self.textWarning.setText("")
    # retranslateUi

