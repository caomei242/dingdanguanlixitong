from __future__ import annotations

from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from strawberry_order_management.extractors.address import extract_address_payload


class AddressExtractorWidget(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.input_edit = QTextEdit()
        self.extract_button = QPushButton("一键提取")
        self.output_one = QTextEdit()
        self.output_two = QTextEdit()
        self.copy_output_one_button = QPushButton("复制")
        self.copy_output_two_button = QPushButton("复制")
        self.status_label = QLabel("等待输入")

        self.output_one.setReadOnly(True)
        self.output_two.setReadOnly(True)

        output_one_header = QHBoxLayout()
        output_one_header.addWidget(QLabel("提取结果一"))
        output_one_header.addStretch(1)
        output_one_header.addWidget(self.copy_output_one_button)

        output_two_header = QHBoxLayout()
        output_two_header.addWidget(QLabel("提取结果二"))
        output_two_header.addStretch(1)
        output_two_header.addWidget(self.copy_output_two_button)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("输入"))
        layout.addWidget(self.input_edit)
        layout.addWidget(self.extract_button)
        layout.addLayout(output_one_header)
        layout.addWidget(self.output_one)
        layout.addLayout(output_two_header)
        layout.addWidget(self.output_two)
        layout.addWidget(self.status_label)

        self.extract_button.clicked.connect(self._extract)
        self.copy_output_one_button.clicked.connect(
            lambda: self._copy_output(self.output_one.toPlainText(), "已复制结果一")
        )
        self.copy_output_two_button.clicked.connect(
            lambda: self._copy_output(self.output_two.toPlainText(), "已复制结果二")
        )

    def load_from_order(self, order) -> None:
        payload = extract_address_payload(
            f"{order.recipient_name}[{order.code}]"
            f"{order.phone_number}{''.join(str(order.address).split())}[{order.code}]"
        )
        self.output_one.setPlainText(payload.cleaned_text)
        self.output_two.setPlainText(payload.delivery_note)
        self.status_label.setText("已同步订单地址结果")

    def _extract(self) -> None:
        try:
            payload = extract_address_payload(self.input_edit.toPlainText())
        except ValueError as exc:
            self.output_one.clear()
            self.output_two.clear()
            self.status_label.setText(str(exc))
            return

        self.output_one.setPlainText(payload.cleaned_text)
        self.output_two.setPlainText(payload.delivery_note)
        self.status_label.setText("提取成功")

    def _copy_output(self, text: str, status_message: str) -> None:
        if not text.strip():
            self.status_label.setText("没有可复制的内容")
            return
        QGuiApplication.clipboard().setText(text)
        self.status_label.setText(status_message)
