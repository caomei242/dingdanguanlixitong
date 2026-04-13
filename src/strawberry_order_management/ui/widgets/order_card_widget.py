from __future__ import annotations

from functools import partial

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QWidget,
)

from strawberry_order_management.models import ParsedOrder, ProcurementItem


class OrderCardWidget(QWidget):
    product_library_requested = Signal(str, str)

    def __init__(self) -> None:
        super().__init__()
        self._product_presets: list[dict[str, str]] = []
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
        self.procurement_rows: list[tuple[QComboBox, QLineEdit, QLineEdit, QPushButton]] = []

        self.procurement_product_1_combo, self.procurement_quantity_1_edit, self.procurement_cost_1_edit, self.procurement_save_1_button = (
            self._build_procurement_row(0)
        )
        self.procurement_product_2_combo, self.procurement_quantity_2_edit, self.procurement_cost_2_edit, self.procurement_save_2_button = (
            self._build_procurement_row(1)
        )
        self.procurement_product_3_combo, self.procurement_quantity_3_edit, self.procurement_cost_3_edit, self.procurement_save_3_button = (
            self._build_procurement_row(2)
        )

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
        layout.addRow(self._label("采购1"), self._procurement_row_widget(0))
        layout.addRow(self._label("采购2"), self._procurement_row_widget(1))
        layout.addRow(self._label("采购3"), self._procurement_row_widget(2))

    def set_product_presets(self, product_presets: list[dict[str, str]]) -> None:
        self._product_presets = [
            {
                "name": self._to_text(item.get("name")).strip(),
                "default_cost": self._to_text(item.get("default_cost")).strip(),
            }
            for item in product_presets
            if self._to_text(item.get("name")).strip()
        ]
        for index, (combo, _, _, _) in enumerate(self.procurement_rows):
            current = combo.currentText().strip()
            combo.blockSignals(True)
            combo.clear()
            combo.addItem("")
            combo.addItems([item["name"] for item in self._product_presets])
            combo.setCurrentText(current)
            combo.blockSignals(False)
            self._apply_preset_to_slot(index)

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
        procurement_items = tuple(order.procurement_items) or ()
        for index, (combo, quantity_edit, cost_edit, _) in enumerate(self.procurement_rows):
            item = procurement_items[index] if index < len(procurement_items) else ProcurementItem("", "1", "")
            combo.setCurrentText(self._to_text(item.product_name))
            quantity_edit.setText(self._to_text(item.quantity) or "1")
            cost_edit.setText(self._to_text(item.cost))

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
            procurement_items=tuple(
                ProcurementItem(
                    combo.currentText().strip(),
                    quantity_edit.text().strip() or "1",
                    cost_edit.text().strip(),
                )
                for combo, quantity_edit, cost_edit, _ in self.procurement_rows
            ),
        )

    def emit_product_library_request(self, index: int) -> None:
        combo, _, cost_edit, _ = self.procurement_rows[index]
        product_name = combo.currentText().strip()
        cost = cost_edit.text().strip()
        if not product_name:
            return
        self.product_library_requested.emit(product_name, cost)

    def _build_procurement_row(self, index: int) -> tuple[QComboBox, QLineEdit, QLineEdit, QPushButton]:
        product_combo = QComboBox()
        product_combo.setEditable(True)
        product_combo.setObjectName("OrderValueEdit")
        product_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        product_combo.setMinimumWidth(220)

        quantity_edit = self._build_line_edit()
        quantity_edit.setPlaceholderText("数量")
        quantity_edit.setText("1")
        quantity_edit.setMaximumWidth(92)

        cost_edit = self._build_line_edit()
        cost_edit.setPlaceholderText("成本")
        cost_edit.setMaximumWidth(140)

        save_button = QPushButton("入库")
        save_button.setObjectName("SecondaryActionButton")
        save_button.setMaximumWidth(86)

        product_combo.currentTextChanged.connect(partial(self._handle_procurement_product_changed, index))
        save_button.clicked.connect(partial(self.emit_product_library_request, index))
        self.procurement_rows.append((product_combo, quantity_edit, cost_edit, save_button))
        return product_combo, quantity_edit, cost_edit, save_button

    def _procurement_row_widget(self, index: int) -> QWidget:
        combo, quantity_edit, cost_edit, save_button = self.procurement_rows[index]
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(combo, 3)
        layout.addWidget(quantity_edit, 1)
        layout.addWidget(cost_edit, 1)
        layout.addWidget(save_button, 0)
        return row

    def _handle_procurement_product_changed(self, index: int, _: str) -> None:
        self._apply_preset_to_slot(index)

    def _apply_preset_to_slot(self, index: int) -> None:
        combo, quantity_edit, cost_edit, _ = self.procurement_rows[index]
        selected_name = combo.currentText().strip()
        if not quantity_edit.text().strip():
            quantity_edit.setText("1")
        if not selected_name:
            return
        for item in self._product_presets:
            if item["name"] == selected_name:
                cost_edit.setText(item["default_cost"])
                return

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
