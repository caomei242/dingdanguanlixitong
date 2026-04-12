from __future__ import annotations

from PySide6.QtWidgets import QFormLayout, QLabel, QWidget


class OrderCardWidget(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.order_id_value = QLabel("-")
        self.placed_at_value = QLabel("-")
        self.order_status_value = QLabel("-")
        self.product_name_value = QLabel("-")
        self.quantity_value = QLabel("-")
        self.order_amount_value = QLabel("-")
        self.income_amount_value = QLabel("-")
        self.recipient_name_value = QLabel("-")
        self.phone_number_value = QLabel("-")
        self.code_value = QLabel("-")
        self.address_value = QLabel("-")
        self.delivery_note_value = QLabel("-")

        layout = QFormLayout(self)
        layout.addRow("订单编号", self.order_id_value)
        layout.addRow("下单时间", self.placed_at_value)
        layout.addRow("订单状态", self.order_status_value)
        layout.addRow("商品名称", self.product_name_value)
        layout.addRow("数量", self.quantity_value)
        layout.addRow("订单金额", self.order_amount_value)
        layout.addRow("商家收入", self.income_amount_value)
        layout.addRow("收件人", self.recipient_name_value)
        layout.addRow("手机号", self.phone_number_value)
        layout.addRow("编号", self.code_value)
        layout.addRow("收货地址", self.address_value)
        layout.addRow("自动备注", self.delivery_note_value)

    def load_order(self, order) -> None:
        self.order_id_value.setText(self._to_text(order.order_id))
        self.placed_at_value.setText(self._to_text(order.placed_at))
        self.order_status_value.setText(self._to_text(order.order_status))
        self.product_name_value.setText(self._to_text(order.product_name))
        self.quantity_value.setText(self._to_text(order.quantity))
        self.order_amount_value.setText(self._to_text(order.order_amount))
        self.income_amount_value.setText(self._to_text(order.income_amount))
        self.recipient_name_value.setText(self._to_text(order.recipient_name))
        self.phone_number_value.setText(self._to_text(order.phone_number))
        self.code_value.setText(self._to_text(order.code))
        self.address_value.setText(self._to_text(order.address))
        self.delivery_note_value.setText(self._to_text(order.delivery_note))

    @staticmethod
    def _to_text(value) -> str:
        if value is None:
            return "-"
        return str(value)
