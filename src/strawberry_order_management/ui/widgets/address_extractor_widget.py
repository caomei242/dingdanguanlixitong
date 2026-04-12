from __future__ import annotations

from PySide6.QtWidgets import (
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
        self.status_label = QLabel("等待输入")

        self.output_one.setReadOnly(True)
        self.output_two.setReadOnly(True)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("输入"))
        layout.addWidget(self.input_edit)
        layout.addWidget(self.extract_button)
        layout.addWidget(QLabel("提取结果一"))
        layout.addWidget(self.output_one)
        layout.addWidget(QLabel("提取结果二"))
        layout.addWidget(self.output_two)
        layout.addWidget(self.status_label)

        self.extract_button.clicked.connect(self._extract)

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
