from __future__ import annotations

from PySide6.QtWidgets import QFormLayout, QLabel, QLineEdit, QTextEdit, QWidget

from strawberry_order_management.models import ParsedOrder


class OrderCardWidget(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.order_id_edit = self._build_line_edit()
        self.placed_at_edit = self._build_line_edit()
        self.order_status_edit = self._build_line_edit()
        self.product_name_edit = self._build_text_edit("HighlightedValueEdit")
        self.quantity_edit = self._build_line_edit()
        self.order_amount_edit = self._build_line_edit()
        self.income_amount_edit = self._build_line_edit()
        self.recipient_name_edit = self._build_line_edit()
        self.phone_number_edit = self._build_line_edit()
        self.code_edit = self._build_line_edit()
        self.address_edit = self._build_text_edit("HighlightedValueEdit")
        self.delivery_note_edit = self._build_text_edit()

        layout = QFormLayout(self)
        layout.addRow(self._label("订单编号"), self.order_id_edit)
        layout.addRow(self._label("下单时间"), self.placed_at_edit)
        layout.addRow(self._label("订单状态"), self.order_status_edit)
        layout.addRow(self._label("商品名称"), self.product_name_edit)
        layout.addRow(self._label("数量"), self.quantity_edit)
        layout.addRow(self._label("订单金额"), self.order_amount_edit)
        layout.addRow(self._label("商家收入"), self.income_amount_edit)
        layout.addRow(self._label("收件人"), self.recipient_name_edit)
        layout.addRow(self._label("手机号"), self.phone_number_edit)
        layout.addRow(self._label("编号"), self.code_edit)
        layout.addRow(self._label("收货地址"), self.address_edit)
        layout.addRow(self._label("自动备注"), self.delivery_note_edit)

    def load_order(self, order) -> None:
        self.order_id_edit.setText(self._to_text(order.order_id))
        self.placed_at_edit.setText(self._to_text(order.placed_at))
        self.order_status_edit.setText(self._to_text(order.order_status))
        self.product_name_edit.setPlainText(self._to_text(order.product_name))
        self.quantity_edit.setText(self._to_text(order.quantity))
        self.order_amount_edit.setText(self._to_text(order.order_amount))
        self.income_amount_edit.setText(self._to_text(order.income_amount))
        self.recipient_name_edit.setText(self._to_text(order.recipient_name))
        self.phone_number_edit.setText(self._to_text(order.phone_number))
        self.code_edit.setText(self._to_text(order.code))
        self.address_edit.setPlainText(self._to_text(order.address))
        self.delivery_note_edit.setPlainText(self._to_text(order.delivery_note))

    def to_order(self) -> ParsedOrder:
        return ParsedOrder(
            order_id=self.order_id_edit.text().strip(),
            placed_at=self.placed_at_edit.text().strip(),
            order_status=self.order_status_edit.text().strip(),
            product_name=self.product_name_edit.toPlainText().strip(),
            quantity=self.quantity_edit.text().strip(),
            order_amount=self.order_amount_edit.text().strip(),
            income_amount=self.income_amount_edit.text().strip(),
            recipient_name=self.recipient_name_edit.text().strip(),
            phone_number=self.phone_number_edit.text().strip(),
            code=self.code_edit.text().strip(),
            address=self.address_edit.toPlainText().strip(),
            delivery_note=self.delivery_note_edit.toPlainText().strip(),
        )

    @staticmethod
    def _to_text(value) -> str:
        if value is None:
            return ""
        return str(value)

    @staticmethod
    def _build_line_edit() -> QLineEdit:
        widget = QLineEdit()
        widget.setObjectName("OrderValueEdit")
        return widget

    @staticmethod
    def _build_text_edit(object_name: str = "OrderValueEdit") -> QTextEdit:
        widget = QTextEdit()
        widget.setObjectName(object_name)
        widget.setMaximumHeight(92)
        return widget

    @staticmethod
    def _label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("OrderFieldLabel")
        return label
