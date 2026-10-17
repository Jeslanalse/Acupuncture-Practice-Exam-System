# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'assignmentdialog.ui'
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
from PySide6.QtWidgets import (QAbstractButton, QApplication, QComboBox, QDateTimeEdit,
    QDialog, QDialogButtonBox, QFormLayout, QLabel,
    QLineEdit, QPlainTextEdit, QSizePolicy, QVBoxLayout,
    QWidget)

class Ui_AssignmentDialog(object):
    def setupUi(self, AssignmentDialog):
        if not AssignmentDialog.objectName():
            AssignmentDialog.setObjectName(u"AssignmentDialog")
        AssignmentDialog.resize(600, 480)
        self.verticalLayoutWidget = QWidget(AssignmentDialog)
        self.verticalLayoutWidget.setObjectName(u"verticalLayoutWidget")
        self.verticalLayoutWidget.setGeometry(QRect(0, 0, 601, 481))
        self.verticalLayout = QVBoxLayout(self.verticalLayoutWidget)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.formLayout = QFormLayout()
        self.formLayout.setObjectName(u"formLayout")
        self.label = QLabel(self.verticalLayoutWidget)
        self.label.setObjectName(u"label")
        font = QFont()
        font.setPointSize(16)
        self.label.setFont(font)

        self.formLayout.setWidget(0, QFormLayout.ItemRole.LabelRole, self.label)

        self.editAssignmentTitle = QLineEdit(self.verticalLayoutWidget)
        self.editAssignmentTitle.setObjectName(u"editAssignmentTitle")
        self.editAssignmentTitle.setFont(font)
        self.editAssignmentTitle.setMaxLength(32)

        self.formLayout.setWidget(0, QFormLayout.ItemRole.FieldRole, self.editAssignmentTitle)

        self.label_2 = QLabel(self.verticalLayoutWidget)
        self.label_2.setObjectName(u"label_2")
        self.label_2.setFont(font)

        self.formLayout.setWidget(1, QFormLayout.ItemRole.LabelRole, self.label_2)

        self.textAssignmentDescription = QPlainTextEdit(self.verticalLayoutWidget)
        self.textAssignmentDescription.setObjectName(u"textAssignmentDescription")
        self.textAssignmentDescription.setFont(font)

        self.formLayout.setWidget(1, QFormLayout.ItemRole.FieldRole, self.textAssignmentDescription)

        self.label_3 = QLabel(self.verticalLayoutWidget)
        self.label_3.setObjectName(u"label_3")
        self.label_3.setFont(font)

        self.formLayout.setWidget(2, QFormLayout.ItemRole.LabelRole, self.label_3)

        self.dateAssignmentStart = QDateTimeEdit(self.verticalLayoutWidget)
        self.dateAssignmentStart.setObjectName(u"dateAssignmentStart")
        self.dateAssignmentStart.setFont(font)
        self.dateAssignmentStart.setCalendarPopup(True)

        self.formLayout.setWidget(2, QFormLayout.ItemRole.FieldRole, self.dateAssignmentStart)

        self.label_4 = QLabel(self.verticalLayoutWidget)
        self.label_4.setObjectName(u"label_4")
        self.label_4.setFont(font)

        self.formLayout.setWidget(3, QFormLayout.ItemRole.LabelRole, self.label_4)

        self.dateAssignmentEnd = QDateTimeEdit(self.verticalLayoutWidget)
        self.dateAssignmentEnd.setObjectName(u"dateAssignmentEnd")
        self.dateAssignmentEnd.setFont(font)
        self.dateAssignmentEnd.setCalendarPopup(True)

        self.formLayout.setWidget(3, QFormLayout.ItemRole.FieldRole, self.dateAssignmentEnd)

        self.label_5 = QLabel(self.verticalLayoutWidget)
        self.label_5.setObjectName(u"label_5")
        self.label_5.setFont(font)

        self.formLayout.setWidget(4, QFormLayout.ItemRole.LabelRole, self.label_5)

        self.comboAssignmentTechnique = QComboBox(self.verticalLayoutWidget)
        self.comboAssignmentTechnique.setObjectName(u"comboAssignmentTechnique")
        self.comboAssignmentTechnique.setFont(font)

        self.formLayout.setWidget(4, QFormLayout.ItemRole.FieldRole, self.comboAssignmentTechnique)


        self.verticalLayout.addLayout(self.formLayout)

        self.labelAssignmentError = QLabel(self.verticalLayoutWidget)
        self.labelAssignmentError.setObjectName(u"labelAssignmentError")
        self.labelAssignmentError.setFont(font)
        self.labelAssignmentError.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.verticalLayout.addWidget(self.labelAssignmentError)

        self.buttonBox = QDialogButtonBox(self.verticalLayoutWidget)
        self.buttonBox.setObjectName(u"buttonBox")
        self.buttonBox.setFont(font)
        self.buttonBox.setStandardButtons(QDialogButtonBox.StandardButton.Cancel|QDialogButtonBox.StandardButton.Ok)
        self.buttonBox.setCenterButtons(True)

        self.verticalLayout.addWidget(self.buttonBox)


        self.retranslateUi(AssignmentDialog)

        QMetaObject.connectSlotsByName(AssignmentDialog)
    # setupUi

    def retranslateUi(self, AssignmentDialog):
        AssignmentDialog.setWindowTitle(QCoreApplication.translate("AssignmentDialog", u"Dialog", None))
        self.label.setText(QCoreApplication.translate("AssignmentDialog", u"\u9898\u76ee", None))
        self.label_2.setText(QCoreApplication.translate("AssignmentDialog", u"\u63cf\u8ff0", None))
        self.label_3.setText(QCoreApplication.translate("AssignmentDialog", u"\u8d77\u59cb\u65f6\u95f4", None))
        self.dateAssignmentStart.setDisplayFormat(QCoreApplication.translate("AssignmentDialog", u"yyyy/MM/dd HH:mm", None))
        self.label_4.setText(QCoreApplication.translate("AssignmentDialog", u"\u622a\u6b62\u65f6\u95f4", None))
        self.dateAssignmentEnd.setDisplayFormat(QCoreApplication.translate("AssignmentDialog", u"yyyy/MM/dd HH:mm", None))
        self.label_5.setText(QCoreApplication.translate("AssignmentDialog", u"\u6807\u51c6\u624b\u6cd5", None))
        self.labelAssignmentError.setText("")
    # retranslateUi

