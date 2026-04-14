from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from functools import partial
from pathlib import Path
import re

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
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

from strawberry_order_management.finance import (
    calculate_platform_fee_amount,
    format_money,
    parse_decimal,
)
from strawberry_order_management.models import ParsedOrder, ProcurementItem


class OrderCardWidget(QWidget):
    product_library_requested = Signal(str, str)
    procurement_template_requested = Signal(object)
    ORDER_STATUS_OPTIONS = ("已发货", "待发货", "已拍单未发货")
    DEFAULT_PLATFORM_FEE_RATE = "0.06"
    DEFAULT_DELIVERY_NOTE_PATTERN = re.compile(r"^请电话送货上门谢谢【\d+】$")

    def __init__(self) -> None:
        super().__init__()
        self._product_presets: list[dict[str, str]] = []
        self._procurement_templates: list[dict[str, object]] = []
        self.order_id_edit = self._build_line_edit()
        self.placed_at_edit = self._build_line_edit()
        self.order_status_edit = QComboBox()
        self.order_status_edit.addItems(list(self.ORDER_STATUS_OPTIONS))
        self.order_status_edit.setObjectName("OrderValueEdit")
        self.order_status_edit.setMinimumHeight(36)
        self.product_name_edit = self._build_text_edit("HighlightedValueEdit")
        self.specification_edit = self._build_line_edit()
        self.sku_edit = self._build_line_edit()
        self.sku_image_label = QLabel("暂无 SKU 图片")
        self.sku_image_label.setObjectName("MutedText")
        self.sku_image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sku_image_label.setMinimumSize(92, 92)
        self.quantity_edit = self._build_line_edit()
        self.order_amount_edit = self._build_line_edit()
        self.income_amount_edit = self._build_line_edit()
        self.recipient_name_edit = self._build_line_edit()
        self.phone_number_edit = self._build_line_edit()
        self.code_edit = self._build_line_edit()
        self.address_edit = self._build_text_edit("HighlightedValueEdit")
        self.delivery_note_edit = self._build_text_edit()
        self.platform_fee_rate_edit = self._build_line_edit()
        self.platform_fee_amount_edit = self._build_line_edit()
        self.other_cost_edit = self._build_line_edit()
        self.procurement_total_cost_edit = self._build_line_edit(read_only=True)
        self.gross_profit_edit = self._build_line_edit(read_only=True)
        self.custom_cost_label_edits = [QLabel("") for _ in range(3)]
        self.custom_cost_value_edits = [self._build_line_edit() for _ in range(3)]
        self.custom_cost_row_widgets: list[QWidget] = []
        self._platform_fee_amount_overridden = False
        self._suspend_financial_recalculation = False
        self.procurement_rows: list[tuple[QComboBox, QLineEdit, QLineEdit, QLineEdit, QPushButton]] = []

        self.procurement_product_1_combo, self.procurement_quantity_1_edit, self.procurement_cost_1_edit, self.procurement_tracking_number_1_edit, self.procurement_save_1_button = (
            self._build_procurement_row(0)
        )
        self.procurement_product_2_combo, self.procurement_quantity_2_edit, self.procurement_cost_2_edit, self.procurement_tracking_number_2_edit, self.procurement_save_2_button = (
            self._build_procurement_row(1)
        )
        self.procurement_product_3_combo, self.procurement_quantity_3_edit, self.procurement_cost_3_edit, self.procurement_tracking_number_3_edit, self.procurement_save_3_button = (
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
        layout.addWidget(
            self._build_section_card(
                "财务信息",
                "补平台扣点、自定义成本，并自动计算采购总成本和毛利润。",
                "FinancialSectionCard",
                self._build_financial_body(),
            )
        )
        layout.addStretch(1)
        self._wire_financial_recalculation()
        self.set_custom_cost_labels(["", "", ""])

    def set_product_presets(self, product_presets: list[dict[str, str]]) -> None:
        self._product_presets = [
            {
                "name": self._to_text(item.get("name")).strip(),
                "default_cost": self._to_text(item.get("default_cost")).strip(),
            }
            for item in product_presets
            if self._to_text(item.get("name")).strip()
        ]
        for index, (combo, _, _, _, _) in enumerate(self.procurement_rows):
            current = combo.currentText().strip()
            combo.blockSignals(True)
            combo.clear()
            combo.addItem("")
            combo.addItems([item["name"] for item in self._product_presets])
            combo.setCurrentText(current)
            combo.blockSignals(False)
            self._apply_preset_to_slot(index)

    def set_procurement_templates(self, procurement_templates: list[dict[str, object]]) -> None:
        self._procurement_templates = [
            self._normalize_procurement_template(item)
            for item in procurement_templates
            if isinstance(item, dict)
        ]

    def set_custom_cost_labels(self, labels: list[str] | tuple[str, str, str]) -> None:
        normalized = list(labels[:3]) + [""] * max(0, 3 - len(labels))
        for index, label in enumerate(self.custom_cost_label_edits):
            text = self._to_text(normalized[index]).strip()
            label.setText(text)
            row_widget = self.custom_cost_row_widgets[index]
            row_widget.setVisible(bool(text))
            if not text:
                self.custom_cost_value_edits[index].clear()
        self._recalculate_financials()

    def load_order(self, order) -> None:
        has_prefilled_financials = any(
            self._to_text(value).strip()
            for value in (
                getattr(order, "platform_fee_rate", ""),
                getattr(order, "platform_fee_amount", ""),
                getattr(order, "other_cost", ""),
                getattr(order, "procurement_total_cost", ""),
                getattr(order, "gross_profit", ""),
                *(getattr(order, "custom_cost_values", ("", "", "")) or ("", "", "")),
            )
        )
        self._suspend_financial_recalculation = True
        self.order_id_edit.setText(self._to_text(order.order_id))
        self.placed_at_edit.setText(self._to_text(order.placed_at))
        self._set_status_text(self._to_text(order.order_status))
        self.product_name_edit.setPlainText(self._to_text(order.product_name))
        self.specification_edit.setText(self._to_text(getattr(order, "specification", "")))
        self.sku_edit.setText(self._to_text(getattr(order, "sku", "")))
        self.quantity_edit.setText(self._to_text(order.quantity))
        self.order_amount_edit.setText(self._to_text(order.order_amount))
        self.income_amount_edit.setText(self._to_text(order.income_amount))
        self.recipient_name_edit.setText(self._to_text(order.recipient_name))
        self.phone_number_edit.setText(self._to_text(order.phone_number))
        self.code_edit.setText(self._to_text(order.code))
        self.address_edit.setPlainText(self._to_text(order.address))
        delivery_note = self._to_text(order.delivery_note)
        if self._is_default_delivery_note(delivery_note):
            delivery_note = ""
        self.delivery_note_edit.setPlainText(delivery_note)
        self._load_sku_image(self._to_text(getattr(order, "sku_image_path", "")))
        fee_rate_value = self._to_text(order.platform_fee_rate).strip() or self.DEFAULT_PLATFORM_FEE_RATE
        self.platform_fee_rate_edit.setText(fee_rate_value)
        self.platform_fee_amount_edit.setText(self._to_text(order.platform_fee_amount))
        self.other_cost_edit.setText(self._to_text(order.other_cost))
        self.procurement_total_cost_edit.setText(self._to_text(order.procurement_total_cost))
        self.gross_profit_edit.setText(self._to_text(order.gross_profit))
        custom_labels = tuple(order.custom_cost_labels) if getattr(order, "custom_cost_labels", None) else ("", "", "")
        self.set_custom_cost_labels(list(custom_labels))
        custom_values = tuple(order.custom_cost_values) if getattr(order, "custom_cost_values", None) else ("", "", "")
        for index, edit in enumerate(self.custom_cost_value_edits):
            edit.setText(self._to_text(custom_values[index] if index < len(custom_values) else ""))
        procurement_items = tuple(order.procurement_items) or ()
        normalized_items = list(procurement_items[:3])
        while len(normalized_items) < 3:
            normalized_items.append(ProcurementItem("", "", "", ""))
        if self._should_apply_template(normalized_items, self._to_text(getattr(order, "specification", ""))):
            normalized_items = self._procurement_items_from_template(
                self._find_template_for_specification(self._to_text(getattr(order, "specification", "")))
            )
        for index, (combo, quantity_edit, cost_edit, tracking_edit, _) in enumerate(self.procurement_rows):
            item = normalized_items[index] if index < len(normalized_items) else ProcurementItem("", "", "", "")
            combo.setCurrentText(self._to_text(item.product_name))
            quantity_edit.setText(self._to_text(item.quantity))
            cost_edit.setText(self._to_text(item.cost))
            tracking_edit.setText(self._to_text(getattr(item, "tracking_number", "")))
        should_recalculate = False
        if self._to_text(order.platform_fee_rate).strip():
            self._platform_fee_amount_overridden = False
            should_recalculate = True
        elif self._to_text(order.platform_fee_amount).strip():
            self._platform_fee_amount_overridden = True
        self._suspend_financial_recalculation = False
        if should_recalculate or not has_prefilled_financials:
            self._recalculate_financials()

    def to_order(self) -> ParsedOrder:
        return ParsedOrder(
            order_id=self.order_id_edit.text().strip(),
            placed_at=self.placed_at_edit.text().strip(),
            order_status=self.order_status_edit.currentText().strip(),
            product_name=self.product_name_edit.toPlainText().strip(),
            specification=self.specification_edit.text().strip(),
            sku=self.sku_edit.text().strip(),
            sku_image_path=self._to_text(self.sku_image_label.property("imagePath")).strip(),
            quantity=self.quantity_edit.text().strip(),
            order_amount=self.order_amount_edit.text().strip(),
            income_amount=self.income_amount_edit.text().strip(),
            recipient_name=self.recipient_name_edit.text().strip(),
            phone_number=self.phone_number_edit.text().strip(),
            code=self.code_edit.text().strip(),
            address=self.address_edit.toPlainText().strip(),
            delivery_note=self.delivery_note_edit.toPlainText().strip(),
            procurement_tracking_number=self._combined_procurement_tracking_number(),
            platform_fee_rate=self.platform_fee_rate_edit.text().strip(),
            platform_fee_amount=self.platform_fee_amount_edit.text().strip(),
            other_cost=self.other_cost_edit.text().strip(),
            procurement_total_cost=self.procurement_total_cost_edit.text().strip(),
            gross_profit=self.gross_profit_edit.text().strip(),
            custom_cost_labels=tuple(label.text().strip() for label in self.custom_cost_label_edits),
            custom_cost_values=tuple(edit.text().strip() for edit in self.custom_cost_value_edits),
            procurement_items=tuple(
                ProcurementItem(*self._normalized_procurement_row_values(combo, quantity_edit, cost_edit, tracking_edit))
                for combo, quantity_edit, cost_edit, tracking_edit, _ in self.procurement_rows
            ),
        )

    def emit_product_library_request(self, index: int) -> None:
        combo, _, cost_edit, _, _ = self.procurement_rows[index]
        product_name = combo.currentText().strip()
        cost = cost_edit.text().strip()
        if not product_name:
            return
        self.product_library_requested.emit(product_name, cost)
        specification = self.specification_edit.text().strip()
        if not specification:
            return
        self.procurement_template_requested.emit(
            {
                "specification": specification,
                "procurement_items": [
                    {
                        "product_name": product_name,
                        "quantity": quantity,
                        "cost": cost,
                        "tracking_number": "",
                    }
                    for product_name, quantity, cost, _ in (
                        self._normalized_procurement_row_values(combo, quantity_edit, cost_edit, tracking_edit)
                        for combo, quantity_edit, cost_edit, tracking_edit, _ in self.procurement_rows
                    )
                ],
            }
        )

    def _build_overview_body(self) -> QWidget:
        body = QWidget()
        grid = QGridLayout(body)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)

        grid.addWidget(self._field_block("下单时间", self.placed_at_edit), 0, 0)
        grid.addWidget(self._field_block("订单状态", self.order_status_edit), 0, 1)
        grid.addWidget(self._field_block("数量", self.quantity_edit), 1, 0)
        grid.addWidget(self._field_block("商品名称", self.product_name_edit), 2, 0, 1, 2)
        grid.addWidget(self._field_block("规格", self.specification_edit), 3, 0, 1, 2)
        grid.addWidget(self._field_block("SKU 图片", self.sku_image_label), 4, 0)
        grid.addWidget(self._field_block("订单金额", self.order_amount_edit), 4, 1)
        grid.addWidget(self._field_block("商家收入", self.income_amount_edit), 5, 0, 1, 2)
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
        grid.addWidget(self._field_block("备注", self.delivery_note_edit), 2, 0, 1, 2)
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

    def _build_financial_body(self) -> QWidget:
        body = QWidget()
        grid = QGridLayout(body)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)

        grid.addWidget(self._field_block("平台扣点比例", self.platform_fee_rate_edit), 0, 0)
        grid.addWidget(self._field_block("平台扣点金额", self.platform_fee_amount_edit), 0, 1)
        grid.addWidget(self._field_block("其他成本", self.other_cost_edit), 1, 0)
        grid.addWidget(self._field_block("采购总成本", self.procurement_total_cost_edit), 1, 1)
        grid.addWidget(self._field_block("毛利润", self.gross_profit_edit), 2, 0, 1, 2)

        for index in range(3):
            row_widget = self._build_custom_cost_row(index)
            self.custom_cost_row_widgets.append(row_widget)
            grid.addWidget(row_widget, 3 + index, 0, 1, 2)
        return body

    def _build_procurement_row(self, index: int) -> tuple[QComboBox, QLineEdit, QLineEdit, QLineEdit, QPushButton]:
        product_combo = QComboBox()
        product_combo.setEditable(True)
        product_combo.setObjectName("OrderValueEdit")
        product_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        product_combo.setMinimumWidth(220)

        quantity_edit = self._build_line_edit()
        quantity_edit.setPlaceholderText("数量")
        quantity_edit.setMaximumWidth(92)

        cost_edit = self._build_line_edit()
        cost_edit.setPlaceholderText("成本")
        cost_edit.setMaximumWidth(140)

        tracking_edit = self._build_line_edit()
        tracking_edit.setPlaceholderText("快递单号")
        tracking_edit.setMinimumWidth(170)

        save_button = QPushButton("入库")
        save_button.setObjectName("SecondaryActionButton")
        save_button.setMaximumWidth(86)

        product_combo.currentTextChanged.connect(partial(self._handle_procurement_product_changed, index))
        save_button.clicked.connect(partial(self.emit_product_library_request, index))
        self.procurement_rows.append((product_combo, quantity_edit, cost_edit, tracking_edit, save_button))
        return product_combo, quantity_edit, cost_edit, tracking_edit, save_button

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
        combo, quantity_edit, cost_edit, tracking_edit, save_button = self.procurement_rows[index]
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(combo, 3)
        layout.addWidget(quantity_edit, 1)
        layout.addWidget(cost_edit, 1)
        layout.addWidget(tracking_edit, 2)
        layout.addWidget(save_button, 0)
        return row

    def _handle_procurement_product_changed(self, index: int, _: str) -> None:
        self._apply_preset_to_slot(index)

    def _apply_preset_to_slot(self, index: int) -> None:
        combo, _, cost_edit, _, _ = self.procurement_rows[index]
        selected_name = combo.currentText().strip()
        if not selected_name:
            return
        for item in self._product_presets:
            if item["name"] == selected_name:
                cost_edit.setText(item["default_cost"])
                self._recalculate_financials()
                return
        self._recalculate_financials()

    def _build_custom_cost_row(self, index: int) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        label = self.custom_cost_label_edits[index]
        label.setObjectName("OrderFieldLabel")
        label.setMinimumWidth(88)
        layout.addWidget(label, 1)
        layout.addWidget(self.custom_cost_value_edits[index], 2)
        return row

    def _wire_financial_recalculation(self) -> None:
        self.income_amount_edit.textChanged.connect(self._recalculate_financials)
        self.platform_fee_rate_edit.textChanged.connect(self._handle_platform_fee_rate_changed)
        self.platform_fee_amount_edit.textEdited.connect(self._handle_platform_fee_amount_edited)
        self.other_cost_edit.textChanged.connect(self._recalculate_financials)
        for _, quantity_edit, cost_edit, _, _ in self.procurement_rows:
            quantity_edit.textChanged.connect(self._recalculate_financials)
            cost_edit.textChanged.connect(self._recalculate_financials)
        for edit in self.custom_cost_value_edits:
            edit.textChanged.connect(self._recalculate_financials)

    def _handle_platform_fee_rate_changed(self, _: str) -> None:
        self._platform_fee_amount_overridden = False
        self._recalculate_financials()

    def _handle_platform_fee_amount_edited(self, _: str) -> None:
        self._platform_fee_amount_overridden = True
        self._recalculate_financials()

    def _recalculate_financials(self) -> None:
        if self._suspend_financial_recalculation:
            return
        income = parse_decimal(self.income_amount_edit.text())
        fee_rate = parse_decimal(self.platform_fee_rate_edit.text())
        fee_amount = parse_decimal(self.platform_fee_amount_edit.text())
        if not self._platform_fee_amount_overridden:
            fee_amount = parse_decimal(calculate_platform_fee_amount(income, fee_rate))
            self._set_line_edit_text(self.platform_fee_amount_edit, format_money(fee_amount))
        procurement_total = self._sum_procurement_costs()
        self._set_line_edit_text(
            self.procurement_total_cost_edit,
            format_money(procurement_total),
        )
        other_cost = parse_decimal(self.other_cost_edit.text())
        custom_total = sum(
            (
                parse_decimal(edit.text())
                for label, edit in zip(self.custom_cost_label_edits, self.custom_cost_value_edits)
                if label.text().strip()
            ),
            Decimal("0"),
        )
        gross_profit = income - fee_amount - procurement_total - other_cost - custom_total
        self._set_line_edit_text(
            self.gross_profit_edit,
            format_money(gross_profit),
        )

    def _sum_procurement_costs(self) -> Decimal:
        total = Decimal("0")
        for _, quantity_edit, cost_edit, _, _ in self.procurement_rows:
            quantity = parse_decimal(quantity_edit.text() or "1")
            cost = parse_decimal(cost_edit.text())
            total += quantity * cost
        return total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def _combined_procurement_tracking_number(self) -> str:
        values = [tracking_edit.text().strip() for _, _, _, tracking_edit, _ in self.procurement_rows if tracking_edit.text().strip()]
        return " / ".join(values)

    def _should_apply_template(self, procurement_items: list[ProcurementItem], specification: str) -> bool:
        if not specification.strip():
            return False
        if self._find_template_for_specification(specification) is None:
            return False
        return not any(
            item.product_name.strip() or item.cost.strip() or item.tracking_number.strip()
            for item in procurement_items
        )

    def _find_template_for_specification(self, specification: str) -> dict[str, object] | None:
        normalized = specification.strip()
        for item in self._procurement_templates:
            if self._to_text(item.get("specification")).strip() == normalized:
                return item
        return None

    def _procurement_items_from_template(self, template: dict[str, object] | None) -> list[ProcurementItem]:
        if not template:
            return [ProcurementItem("", "", "", "") for _ in range(3)]
        items = []
        for item in list(template.get("procurement_items") or [])[:3]:
            if not isinstance(item, dict):
                item = {}
            product_name = self._to_text(item.get("product_name")).strip()
            quantity = self._to_text(item.get("quantity")).strip()
            cost = self._to_text(item.get("cost")).strip()
            items.append(
                ProcurementItem(
                    product_name,
                    (
                        quantity
                        if quantity != "1" or any((product_name, cost))
                        else ""
                    ) or ("1" if any((product_name, cost)) else ""),
                    cost,
                    "",
                )
            )
        while len(items) < 3:
            items.append(ProcurementItem("", "", "", ""))
        return items

    @staticmethod
    def _normalize_procurement_template(template: dict[str, object]) -> dict[str, object]:
        items = []
        raw_items = template.get("procurement_items")
        if isinstance(raw_items, list):
            source_items = raw_items
        else:
            source_items = []
        for index in range(3):
            item = source_items[index] if index < len(source_items) and isinstance(source_items[index], dict) else {}
            product_name = str(item.get("product_name", "")).strip()
            quantity = str(item.get("quantity", "")).strip()
            cost = str(item.get("cost", "")).strip()
            items.append(
                {
                    "product_name": product_name,
                    "quantity": (
                        quantity
                        if quantity != "1" or any((product_name, cost))
                        else ""
                    ) or ("1" if any((product_name, cost)) else ""),
                    "cost": cost,
                }
            )
        return {
            "specification": str(template.get("specification", "")).strip(),
            "procurement_items": items,
        }

    def _normalized_procurement_row_values(
        self,
        combo: QComboBox,
        quantity_edit: QLineEdit,
        cost_edit: QLineEdit,
        tracking_edit: QLineEdit,
    ) -> tuple[str, str, str, str]:
        product_name = combo.currentText().strip()
        quantity = quantity_edit.text().strip()
        cost = cost_edit.text().strip()
        tracking_number = tracking_edit.text().strip()
        if any((product_name, cost, tracking_number)):
            quantity = quantity or "1"
        elif quantity == "1":
            quantity = ""
        return product_name, quantity, cost, tracking_number

    @staticmethod
    def _set_line_edit_text(widget: QLineEdit, value: str) -> None:
        if widget.text() == value:
            return
        widget.blockSignals(True)
        widget.setText(value)
        widget.blockSignals(False)

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
    def _build_line_edit(read_only: bool = False) -> QLineEdit:
        widget = QLineEdit()
        widget.setObjectName("OrderValueEdit")
        widget.setMinimumHeight(36)
        widget.setReadOnly(read_only)
        return widget

    @staticmethod
    def _build_text_edit(object_name: str = "OrderValueEdit") -> QTextEdit:
        widget = QTextEdit()
        widget.setObjectName(object_name)
        widget.setMaximumHeight(84)
        return widget

    def _set_status_text(self, value: str) -> None:
        status = value.strip() or "待发货"
        if status == "未发货":
            status = "待发货"
        if status == "已下单未发货":
            status = "已拍单未发货"
        index = self.order_status_edit.findText(status)
        if index < 0:
            index = self.order_status_edit.findText("待发货")
        self.order_status_edit.setCurrentIndex(max(index, 0))

    def _load_sku_image(self, image_path: str) -> None:
        normalized = image_path.strip()
        self.sku_image_label.setProperty("imagePath", normalized)
        if not normalized or not Path(normalized).exists():
            self.sku_image_label.setPixmap(QPixmap())
            self.sku_image_label.setText("暂无 SKU 图片")
            return
        pixmap = QPixmap(normalized)
        if pixmap.isNull():
            self.sku_image_label.setPixmap(QPixmap())
            self.sku_image_label.setText("暂无 SKU 图片")
            return
        self.sku_image_label.setText("")
        self.sku_image_label.setPixmap(
            pixmap.scaled(
                88,
                88,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    @classmethod
    def _is_default_delivery_note(cls, value: str) -> bool:
        return bool(cls.DEFAULT_DELIVERY_NOTE_PATTERN.match(str(value).strip()))

    @staticmethod
    def _label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("OrderFieldLabel")
        return label
