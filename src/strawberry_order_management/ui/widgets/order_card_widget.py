from __future__ import annotations

from functools import partial

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
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

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        layout.addWidget(
            self._build_section_card(
                "订单概览",
                "编号、状态和金额放在一起，方便快速核对。",
                "OrderSummaryCard",
                self._build_overview_body(),
            )
        )
        layout.addWidget(
            self._build_section_card(
                "收件信息",
                "收件人、电话、地址与备注单独收拢。",
                "OrderShippingCard",
                self._build_shipping_body(),
            )
        )
        layout.addWidget(
            self._build_section_card(
                "采购信息",
                "三条采购槽位用于入库或补录商品库信息。",
                "ProcurementSectionCard",
                self._build_procurement_body(),
            )
        )
        layout.addStretch(1)

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

    def _build_overview_body(self) -> QWidget:
        body = QWidget()
        grid = QGridLayout(body)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)

        grid.addWidget(self._field_block("订单编号", self.order_id_edit), 0, 0)
        grid.addWidget(self._field_block("下单时间", self.placed_at_edit), 0, 1)
        grid.addWidget(self._field_block("订单状态", self.order_status_edit), 1, 0)
        grid.addWidget(self._field_block("数量", self.quantity_edit), 1, 1)
        grid.addWidget(self._field_block("商品名称", self.product_name_edit), 2, 0, 1, 2)
        grid.addWidget(self._field_block("订单金额", self.order_amount_edit), 3, 0)
        grid.addWidget(self._field_block("商家收入", self.income_amount_edit), 3, 1)
        return body

    def _build_shipping_body(self) -> QWidget:
        body = QWidget()
        grid = QGridLayout(body)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)

        grid.addWidget(self._field_block("收件人", self.recipient_name_edit), 0, 0)
        grid.addWidget(self._field_block("手机号", self.phone_number_edit), 0, 1)
        grid.addWidget(self._field_block("编号", self.code_edit), 1, 0)
        grid.addWidget(self._field_block("收货地址", self.address_edit), 1, 1)
        grid.addWidget(self._field_block("自动备注", self.delivery_note_edit), 2, 0, 1, 2)
        return body

    def _build_procurement_body(self) -> QWidget:
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        layout.addWidget(self._build_procurement_row_card("采购1", self._procurement_row_widget(0)))
        layout.addWidget(self._build_procurement_row_card("采购2", self._procurement_row_widget(1)))
        layout.addWidget(self._build_procurement_row_card("采购3", self._procurement_row_widget(2)))
        return body

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

    def _build_procurement_row_card(self, title: str, row_widget: QWidget) -> QWidget:
        card = QFrame()
        card.setObjectName("ProcurementRowCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        label = QLabel(title)
        label.setObjectName("OrderFieldLabel")
        layout.addWidget(label)
        layout.addWidget(row_widget)
        return card

    def _procurement_row_widget(self, index: int) -> QWidget:
        combo, quantity_edit, cost_edit, save_button = self.procurement_rows[index]
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
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

    def _build_section_card(
        self,
        title_text: str,
        subtitle_text: str,
        object_name: str,
        body_widget: QWidget,
    ) -> QFrame:
        card = QFrame()
        card.setObjectName(object_name)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(10)

        title = QLabel(title_text)
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        subtitle = QLabel(subtitle_text)
        subtitle.setObjectName("MutedText")
        layout.addWidget(subtitle)
        layout.addWidget(body_widget)
        return card

    def _field_block(self, label_text: str, widget: QWidget) -> QWidget:
        block = QWidget()
        layout = QVBoxLayout(block)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self._label(label_text))
        layout.addWidget(widget)
        return block

    @staticmethod
    def _to_text(value) -> str:
        if value is None:
            return ""
        return str(value)

    @staticmethod
    def _build_line_edit() -> QLineEdit:
        widget = QLineEdit()
        widget.setObjectName("OrderValueEdit")
        widget.setMinimumHeight(36)
        return widget

    @staticmethod
    def _build_text_edit(object_name: str = "OrderValueEdit") -> QTextEdit:
        widget = QTextEdit()
        widget.setObjectName(object_name)
        widget.setMaximumHeight(84)
        return widget

    @staticmethod
    def _label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("OrderFieldLabel")
        return label
