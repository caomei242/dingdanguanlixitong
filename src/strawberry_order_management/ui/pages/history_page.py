from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from datetime import date, datetime, timedelta
import json
from typing import Any

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from strawberry_order_management.finance import (
    calculate_platform_fee_amount,
    format_money,
    parse_decimal,
)


_ORDER_SNAPSHOT_KEYS = (
    "order_id",
    "placed_at",
    "platform",
    "order_status",
    "product_name",
    "specification",
    "sku",
    "sku_image_path",
    "quantity",
    "order_amount",
    "income_amount",
    "recipient_name",
    "phone_number",
    "code",
    "address",
    "delivery_note",
    "procurement_tracking_number",
    "platform_fee_rate",
    "platform_fee_amount",
    "other_cost",
    "procurement_total_cost",
    "gross_profit",
    "custom_cost_labels",
    "custom_cost_values",
)
_FIXED_ORDER_STATUS_OPTIONS = ("已发货", "待发货", "已拍单未发货")
_ORDER_STATUS_ALIASES = {"未发货": "待发货", "已下单未发货": "已拍单未发货"}
_DEFAULT_PLATFORM_FEE_RATE = "0.06"


class _HistoryStatusCard(QFrame):
    clicked = Signal(str)

    def __init__(self, key: str, title: str) -> None:
        super().__init__()
        self.key = key
        self.setObjectName("HistoryStatusCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(2)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("HistoryStatTitle")
        self.value_label = QLabel("0")
        self.value_label.setObjectName("HistoryStatValue")
        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)

    def set_active(self, active: bool) -> None:
        self.setProperty("active", active)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.key)
        super().mousePressEvent(event)


class HistoryPage(QWidget):
    edit_requested = Signal(str)
    save_requested = Signal(str, object)
    delete_requested = Signal(str)
    resubmit_requested = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("HistoryPage")
        self._product_presets: list[dict[str, str]] = []
        self._all_rows: list[dict[str, Any]] = []
        self._filtered_rows: list[dict[str, Any]] = []
        self._active_quick_filter = "全部"
        self._specific_date_active = False

        title = QLabel("历史工作台")
        title.setObjectName("SectionTitle")
        self.quick_filter_buttons: dict[str, QPushButton] = {}
        self.shop_filter_combo = QComboBox()
        self.status_filter_combo = QComboBox()
        self.keyword_filter_edit = QLineEdit()
        self.date_filter_edit = QDateEdit()
        self.date_filter_edit.setCalendarPopup(True)
        self.date_filter_edit.setDisplayFormat("yyyy-MM-dd")
        self.date_filter_edit.setDate(QDate.currentDate())
        self.apply_filters_button = QPushButton("应用筛选")
        self.clear_filters_button = QPushButton("清空")
        filter_bar = self._build_filter_bar()

        self.summary_label = QLabel("暂无记录")
        self.summary_label.setObjectName("MutedText")

        self.status_summary_buttons: dict[str, _HistoryStatusCard] = {
            "全部订单": _HistoryStatusCard("全部状态", "全部订单"),
            "已发货": _HistoryStatusCard("已发货", "已发货"),
            "待发货": _HistoryStatusCard("待发货", "待发货"),
            "已拍单未发货": _HistoryStatusCard("已拍单未发货", "已拍单未发货"),
        }
        for key, card in self.status_summary_buttons.items():
            card.clicked.connect(self._handle_status_card_clicked)
            if key == "全部订单":
                card.set_active(True)

        self.stats_row_widget = QWidget()
        self.stats_row_widget.setObjectName("HistoryStatsRow")
        stats_row = QGridLayout(self.stats_row_widget)
        stats_row.setContentsMargins(0, 0, 0, 0)
        stats_row.setHorizontalSpacing(8)
        stats_row.setVerticalSpacing(8)
        stats_row.addWidget(self.status_summary_buttons["全部订单"], 0, 0)
        stats_row.addWidget(self.status_summary_buttons["已发货"], 0, 1)
        stats_row.addWidget(self.status_summary_buttons["待发货"], 0, 2)
        stats_row.addWidget(self.status_summary_buttons["已拍单未发货"], 0, 3)

        self.list_widget = QListWidget()
        self.list_widget.setObjectName("HistoryList")
        self.list_widget.currentItemChanged.connect(self._handle_current_item_changed)

        list_card = QFrame()
        list_card.setObjectName("HistoryListCard")
        list_card_layout = QVBoxLayout(list_card)
        list_card_layout.setContentsMargins(12, 12, 12, 12)
        list_card_layout.setSpacing(8)
        list_card_layout.addWidget(self.summary_label)
        list_card_layout.addWidget(self.list_widget, 1)

        self.detail_title_label = QLabel("请选择一条历史记录")
        self.detail_title_label.setObjectName("HistoryDetailTitle")
        self.detail_subtitle_label = QLabel("详情会显示订单快照、地址提取结果和同步轨迹")
        self.detail_subtitle_label.setObjectName("HistoryDetailMeta")

        self.order_id_value = self._build_text_value(minimum_height=36)
        self.placed_at_value = self._build_text_value(minimum_height=36)
        self.platform_value = self._build_text_value(minimum_height=36)
        self.order_status_value = QComboBox()
        self.order_status_value.setObjectName("OrderValueEdit")
        self.order_status_value.setMinimumHeight(36)
        self.order_status_value.addItems(list(_FIXED_ORDER_STATUS_OPTIONS))
        self.product_name_value = self._build_text_value(minimum_height=52)
        self.specification_value = self._build_text_value(minimum_height=36)
        self.sku_value = self._build_text_value(minimum_height=36)
        self.sku_image_value = QLabel("暂无 SKU 图片")
        self.sku_image_value.setObjectName("MutedText")
        self.sku_image_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sku_image_value.setMinimumSize(92, 92)
        self.quantity_value = self._build_text_value(minimum_height=36)
        self.order_amount_value = self._build_text_value(minimum_height=36)
        self.income_amount_value = self._build_text_value(minimum_height=36)
        self.recipient_name_value = self._build_text_value(minimum_height=36)
        self.phone_number_value = self._build_text_value(minimum_height=36)
        self.code_value = self._build_text_value(minimum_height=36)
        self.address_value = self._build_text_value(minimum_height=56)
        self.delivery_note_value = self._build_text_value(minimum_height=56)
        self.platform_fee_rate_value = self._build_line_edit()
        self.platform_fee_rate_value.setText(_DEFAULT_PLATFORM_FEE_RATE)
        self.platform_fee_amount_value = self._build_line_edit()
        self.other_cost_value = self._build_line_edit()
        self.procurement_total_cost_value = self._build_line_edit()
        self.gross_profit_value = self._build_line_edit()
        self.custom_cost_label_1 = QLabel("")
        self.custom_cost_label_2 = QLabel("")
        self.custom_cost_label_3 = QLabel("")
        self.custom_cost_value_1 = self._build_line_edit()
        self.custom_cost_value_2 = self._build_line_edit()
        self.custom_cost_value_3 = self._build_line_edit()

        order_form = QFormLayout()
        order_form.setLabelAlignment(Qt.AlignmentFlag.AlignTop)
        order_form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        order_form.addRow("订单编号", self.order_id_value)
        order_form.addRow("下单时间", self.placed_at_value)
        order_form.addRow("平台", self.platform_value)
        order_form.addRow("订单状态", self.order_status_value)
        order_form.addRow("商品名称", self.product_name_value)
        order_form.addRow("规格", self.specification_value)
        order_form.addRow("SKU 图片", self.sku_image_value)
        order_form.addRow("数量", self.quantity_value)
        order_form.addRow("订单金额", self.order_amount_value)
        order_form.addRow("收入", self.income_amount_value)
        order_form.addRow("收件人", self.recipient_name_value)
        order_form.addRow("手机号", self.phone_number_value)
        order_form.addRow("编号", self.code_value)
        order_form.addRow("收货地址", self.address_value)
        order_form.addRow("备注", self.delivery_note_value)

        order_section = self._build_section("订单基础信息", order_form)

        self.procurement_product_1_combo = self._build_procurement_combo()
        self.procurement_quantity_1_value = self._build_line_edit()
        self.procurement_cost_1_value = self._build_line_edit()
        self.procurement_tracking_1_value = self._build_line_edit()
        self.procurement_product_2_combo = self._build_procurement_combo()
        self.procurement_quantity_2_value = self._build_line_edit()
        self.procurement_cost_2_value = self._build_line_edit()
        self.procurement_tracking_2_value = self._build_line_edit()
        self.procurement_product_3_combo = self._build_procurement_combo()
        self.procurement_quantity_3_value = self._build_line_edit()
        self.procurement_cost_3_value = self._build_line_edit()
        self.procurement_tracking_3_value = self._build_line_edit()
        for combo in (
            self.procurement_product_1_combo,
            self.procurement_product_2_combo,
            self.procurement_product_3_combo,
        ):
            combo.currentTextChanged.connect(self._handle_procurement_product_changed)
        for widget in (
            self.procurement_quantity_1_value,
            self.procurement_quantity_2_value,
            self.procurement_quantity_3_value,
        ):
            widget.setText("1")

        procurement_form = QFormLayout()
        procurement_form.setLabelAlignment(Qt.AlignmentFlag.AlignTop)
        procurement_form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        procurement_form.addRow("采购 1 商品", self.procurement_product_1_combo)
        procurement_form.addRow("采购 1 数量", self.procurement_quantity_1_value)
        procurement_form.addRow("采购 1 成本", self.procurement_cost_1_value)
        procurement_form.addRow("采购 1 快递单号", self.procurement_tracking_1_value)
        procurement_form.addRow("采购 2 商品", self.procurement_product_2_combo)
        procurement_form.addRow("采购 2 数量", self.procurement_quantity_2_value)
        procurement_form.addRow("采购 2 成本", self.procurement_cost_2_value)
        procurement_form.addRow("采购 2 快递单号", self.procurement_tracking_2_value)
        procurement_form.addRow("采购 3 商品", self.procurement_product_3_combo)
        procurement_form.addRow("采购 3 数量", self.procurement_quantity_3_value)
        procurement_form.addRow("采购 3 成本", self.procurement_cost_3_value)
        procurement_form.addRow("采购 3 快递单号", self.procurement_tracking_3_value)

        procurement_section = self._build_section("采购信息", procurement_form)

        finance_form = QFormLayout()
        finance_form.setLabelAlignment(Qt.AlignmentFlag.AlignTop)
        finance_form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        finance_form.addRow("平台扣点比例", self.platform_fee_rate_value)
        finance_form.addRow("平台扣点金额", self.platform_fee_amount_value)
        finance_form.addRow("其他成本", self.other_cost_value)
        finance_form.addRow("采购总成本", self.procurement_total_cost_value)
        finance_form.addRow("毛利润", self.gross_profit_value)
        finance_form.addRow(self.custom_cost_label_1, self.custom_cost_value_1)
        finance_form.addRow(self.custom_cost_label_2, self.custom_cost_value_2)
        finance_form.addRow(self.custom_cost_label_3, self.custom_cost_value_3)

        finance_section = self._build_section("财务信息", finance_form)

        self.address_output_one = self._build_text_value(minimum_height=56, editable=False)
        self.address_output_two = self._build_text_value(minimum_height=56, editable=False)

        address_form = QFormLayout()
        address_form.setLabelAlignment(Qt.AlignmentFlag.AlignTop)
        address_form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        address_form.addRow("结果一", self.address_output_one)
        address_form.addRow("结果二", self.address_output_two)

        address_section = self._build_section("地址提取结果", address_form)

        self.sync_source_value = self._build_text_value(minimum_height=36, editable=False)
        self.status_value = self._build_text_value(minimum_height=36, editable=False)
        self.sync_message_value = self._build_text_value(minimum_height=64, editable=False)

        sync_form = QFormLayout()
        sync_form.setLabelAlignment(Qt.AlignmentFlag.AlignTop)
        sync_form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        sync_form.addRow("同步方式", self.sync_source_value)
        sync_form.addRow("当前状态", self.status_value)
        sync_form.addRow("最后状态说明", self.sync_message_value)

        sync_section = self._build_section("同步信息", sync_form)

        self.save_button = QPushButton("保存修改并重新写入飞书")
        self.save_button.setObjectName("SecondaryActionButton")
        self.delete_button = QPushButton("删除")
        self.delete_button.setObjectName("DangerActionButton")
        self.resubmit_button = QPushButton("重新写入飞书")
        self.resubmit_button.setObjectName("SecondaryActionButton")

        self.save_button.clicked.connect(self._emit_save_requested)
        self.delete_button.clicked.connect(self._emit_delete_requested)
        self.resubmit_button.clicked.connect(self._emit_resubmit_requested)

        detail_body = QWidget()
        detail_body.setObjectName("PageContent")
        detail_body_layout = QVBoxLayout(detail_body)
        detail_body_layout.setContentsMargins(0, 0, 0, 0)
        detail_body_layout.setSpacing(10)

        detail_header = QFrame()
        detail_header.setObjectName("HistoryStickyActionBar")
        detail_header_layout = QHBoxLayout(detail_header)
        detail_header_layout.setContentsMargins(0, 0, 0, 0)
        detail_header_layout.setSpacing(10)
        detail_header_text = QWidget()
        detail_header_text_layout = QVBoxLayout(detail_header_text)
        detail_header_text_layout.setContentsMargins(0, 0, 0, 0)
        detail_header_text_layout.setSpacing(2)
        detail_header_text_layout.addWidget(self.detail_title_label)
        detail_header_text_layout.addWidget(self.detail_subtitle_label)

        self.header_actions_widget = QWidget()
        header_actions_layout = QHBoxLayout(self.header_actions_widget)
        header_actions_layout.setContentsMargins(0, 0, 0, 0)
        header_actions_layout.setSpacing(8)
        header_actions_layout.addWidget(self.save_button)
        header_actions_layout.addWidget(self.delete_button)
        self.resubmit_button.hide()

        detail_header_layout.addWidget(detail_header_text, 1)
        detail_header_layout.addWidget(self.header_actions_widget, 0, Qt.AlignmentFlag.AlignTop)
        detail_body_layout.addWidget(detail_header)

        self.detail_summary_card = QFrame()
        self.detail_summary_card.setObjectName("HistorySummaryCard")
        detail_summary_layout = QGridLayout(self.detail_summary_card)
        detail_summary_layout.setContentsMargins(10, 10, 10, 10)
        detail_summary_layout.setHorizontalSpacing(8)
        detail_summary_layout.setVerticalSpacing(8)
        self.summary_income_card, self.summary_income_value = self._build_summary_value("收入")
        self.summary_order_amount_card, self.summary_order_amount_value = self._build_summary_value("订单金额")
        self.summary_product_card, self.summary_product_value = self._build_summary_value("商品")
        self.summary_procurement_card, self.summary_procurement_value = self._build_summary_value("采购")
        detail_summary_layout.addWidget(self.summary_income_card, 0, 0)
        detail_summary_layout.addWidget(self.summary_order_amount_card, 0, 1)
        detail_summary_layout.addWidget(self.summary_product_card, 0, 2)
        detail_summary_layout.addWidget(self.summary_procurement_card, 0, 3)

        detail_grid = QGridLayout()
        detail_grid.setContentsMargins(0, 0, 0, 0)
        detail_grid.setHorizontalSpacing(10)
        detail_grid.setVerticalSpacing(10)
        detail_grid.addWidget(order_section, 0, 0)
        detail_grid.addWidget(procurement_section, 0, 1)
        detail_grid.addWidget(finance_section, 1, 0)
        detail_grid.addWidget(address_section, 1, 1)
        detail_grid.addWidget(sync_section, 2, 0, 1, 2)

        detail_body_layout.addWidget(self.detail_summary_card)
        detail_body_layout.addLayout(detail_grid)
        detail_body_layout.addStretch(1)

        detail_scroll = QScrollArea()
        detail_scroll.setObjectName("HistoryDetailScroll")
        detail_scroll.setWidgetResizable(True)
        detail_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        detail_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        detail_scroll.setWidget(detail_body)

        detail_card = QFrame()
        detail_card.setObjectName("HistoryDetailPane")
        detail_card_layout = QVBoxLayout(detail_card)
        detail_card_layout.setContentsMargins(12, 12, 12, 12)
        detail_card_layout.addWidget(detail_scroll)

        self.left_column_widget = QFrame()
        self.left_column_widget.setObjectName("HistoryMasterPane")
        self.left_column_widget.setMaximumWidth(420)
        left_column_layout = QVBoxLayout(self.left_column_widget)
        left_column_layout.setContentsMargins(0, 0, 0, 0)
        left_column_layout.setSpacing(10)
        left_column_layout.addWidget(list_card, 1)

        workspace_row = QHBoxLayout()
        workspace_row.setContentsMargins(0, 0, 0, 0)
        workspace_row.setSpacing(10)
        workspace_row.addWidget(self.left_column_widget, 1)
        workspace_row.addWidget(detail_card, 2)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)
        root.addWidget(title)
        root.addWidget(filter_bar)
        root.addWidget(self.stats_row_widget)
        root.addLayout(workspace_row, 1)

        self._editable_widgets = [
            self.order_id_value,
            self.placed_at_value,
            self.platform_value,
            self.product_name_value,
            self.specification_value,
            self.quantity_value,
            self.order_amount_value,
            self.income_amount_value,
            self.recipient_name_value,
            self.phone_number_value,
            self.code_value,
            self.address_value,
            self.delivery_note_value,
            self.platform_fee_rate_value,
            self.platform_fee_amount_value,
            self.other_cost_value,
            self.procurement_total_cost_value,
            self.gross_profit_value,
            self.procurement_tracking_1_value,
            self.procurement_tracking_2_value,
            self.procurement_tracking_3_value,
            self.procurement_quantity_1_value,
            self.procurement_cost_1_value,
            self.procurement_quantity_2_value,
            self.procurement_cost_2_value,
            self.procurement_quantity_3_value,
            self.procurement_cost_3_value,
            self.custom_cost_value_1,
            self.custom_cost_value_2,
            self.custom_cost_value_3,
        ]

        self._set_widgets_read_only(False)
        self._update_action_state()
        self._wire_filter_events()
        self._wire_edit_events()
        self._show_empty_detail()

    def set_product_presets(self, product_presets: list[dict[str, str]]) -> None:
        self._product_presets = [
            {
                "name": self._text_value(item.get("name")),
                "default_cost": self._text_value(item.get("default_cost")),
            }
            for item in product_presets
            if self._text_value(item.get("name"))
        ]
        combos = (
            self.procurement_product_1_combo,
            self.procurement_product_2_combo,
            self.procurement_product_3_combo,
        )
        for combo in combos:
            current = combo.currentText().strip()
            combo.blockSignals(True)
            combo.clear()
            combo.addItem("")
            combo.addItems([item["name"] for item in self._product_presets])
            combo.setCurrentText(current)
            combo.blockSignals(False)
        self._apply_procurement_preset(self.procurement_product_1_combo, self.procurement_quantity_1_value, self.procurement_cost_1_value)
        self._apply_procurement_preset(self.procurement_product_2_combo, self.procurement_quantity_2_value, self.procurement_cost_2_value)
        self._apply_procurement_preset(self.procurement_product_3_combo, self.procurement_quantity_3_value, self.procurement_cost_3_value)

    def load_rows(self, rows: list[dict[str, Any]]) -> None:
        previous_record_id, previous_index = self._current_selection()
        self._all_rows = [self._normalize_row(row) for row in rows]
        self._refresh_shop_filter_options()
        self._apply_filters(previous_record_id, previous_index)

    def _apply_filters(self, previous_record_id: str | None = None, previous_index: int | None = None) -> None:
        self._filtered_rows = [row for row in self._all_rows if self._row_matches_filters(row)]
        self._update_stats()
        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        self.summary_label.setText(f"共 {len(self._filtered_rows)} 条记录")
        if not self._filtered_rows:
            self.list_widget.blockSignals(False)
            self._show_empty_detail()
            self._update_action_state()
            return

        for row in self._filtered_rows:
            item_text = self._build_row_text(row)
            self.list_widget.addItem(item_text)
            image_path = self._text_value((row.get("order_snapshot") or {}).get("sku_image_path"))
            if image_path:
                item = self.list_widget.item(self.list_widget.count() - 1)
                item.setIcon(QIcon(image_path))

        self.list_widget.blockSignals(False)
        selected_index = self._restore_selection(previous_record_id, previous_index)
        if selected_index is not None:
            self.list_widget.setCurrentRow(selected_index)
            self._show_row(selected_index)
        else:
            self._show_empty_detail()
        self._update_action_state()

    def _build_row_text(self, row: dict[str, Any]) -> str:
        shop_name = self._display_value(row.get("shop_name"))
        recipient_name = self._text_value((row.get("order_snapshot") or {}).get("recipient_name"))
        if not recipient_name:
            recipient_name = self._display_value(row.get("sync_source"))
        status = self._display_value(row.get("status"))
        order_id = self._text_value((row.get("order_snapshot") or {}).get("order_id")) or "-"
        tracking_number = self._text_value(
            (row.get("order_snapshot") or {}).get("procurement_tracking_number")
        )
        if not tracking_number:
            tracking_number = " / ".join(
                self._text_value(item.get("tracking_number"))
                for item in (row.get("order_snapshot") or {}).get("procurement_items", [])
                if isinstance(item, dict) and self._text_value(item.get("tracking_number"))
            )
        if tracking_number:
            return f"{shop_name} · {recipient_name} · {status} · {order_id} · {tracking_number}"
        return f"{shop_name} · {recipient_name} · {status} · {order_id}"

    def _handle_current_item_changed(self, current, previous) -> None:
        del current, previous
        self._show_row(self.list_widget.currentRow())
        self._update_action_state()

    def _emit_save_requested(self) -> None:
        row = self._current_row()
        if row is None:
            return
        record_id = self._text_value(row.get("record_id"))
        if not record_id:
            return
        patch = {"order_snapshot": self._build_order_snapshot_from_inputs(row.get("order_snapshot") or {})}
        self._merge_patch(row, patch)
        self._show_row(self.list_widget.currentRow())
        self._update_action_state()
        self.save_requested.emit(record_id, patch)

    def _emit_delete_requested(self) -> None:
        self._emit_action(self.delete_requested)

    def _emit_resubmit_requested(self) -> None:
        self._emit_action(self.resubmit_requested)

    def _emit_action(self, signal: Signal) -> None:
        row = self._current_row()
        if row is None:
            return
        record_id = self._text_value(row.get("record_id"))
        if not record_id:
            return
        signal.emit(record_id)

    def _show_row(self, row_index: int) -> None:
        if row_index < 0 or row_index >= len(self._filtered_rows):
            self._show_empty_detail()
            return

        row = self._filtered_rows[row_index]
        order_snapshot = row.get("order_snapshot") or {}
        address_snapshot = row.get("address_snapshot") or {}

        self.detail_title_label.setText(self._display_value(row.get("shop_name")))
        self.detail_subtitle_label.setText(
            f"{self._display_value(row.get('sync_source'))} · {self._display_value(row.get('status'))}"
        )

        self.order_id_value.setPlainText(self._text_value(order_snapshot.get("order_id")))
        self.placed_at_value.setPlainText(self._text_value(order_snapshot.get("placed_at")))
        self.platform_value.setPlainText(self._text_value(order_snapshot.get("platform")) or "抖店")
        self._set_order_status_value(self._text_value(order_snapshot.get("order_status")))
        self.product_name_value.setPlainText(self._text_value(order_snapshot.get("product_name")))
        self.specification_value.setPlainText(self._text_value(order_snapshot.get("specification")))
        self.sku_value.setPlainText(self._text_value(order_snapshot.get("sku")))
        self._set_sku_image(self._text_value(order_snapshot.get("sku_image_path")))
        self.quantity_value.setPlainText(self._text_value(order_snapshot.get("quantity")))
        self.order_amount_value.setPlainText(self._text_value(order_snapshot.get("order_amount")))
        self.income_amount_value.setPlainText(self._text_value(order_snapshot.get("income_amount")))
        self.recipient_name_value.setPlainText(self._text_value(order_snapshot.get("recipient_name")))
        self.phone_number_value.setPlainText(self._text_value(order_snapshot.get("phone_number")))
        self.code_value.setPlainText(self._text_value(order_snapshot.get("code")))
        self.address_value.setPlainText(self._text_value(order_snapshot.get("address")))
        self.delivery_note_value.setPlainText(self._text_value(order_snapshot.get("delivery_note")))
        self.platform_fee_rate_value.setText(
            self._text_value(order_snapshot.get("platform_fee_rate")) or _DEFAULT_PLATFORM_FEE_RATE
        )
        self.platform_fee_amount_value.setText(self._text_value(order_snapshot.get("platform_fee_amount")))
        self.other_cost_value.setText(self._text_value(order_snapshot.get("other_cost")))
        self.procurement_total_cost_value.setText(self._text_value(order_snapshot.get("procurement_total_cost")))
        self.gross_profit_value.setText(self._text_value(order_snapshot.get("gross_profit")))
        custom_labels = order_snapshot.get("custom_cost_labels") or ["", "", ""]
        custom_values = order_snapshot.get("custom_cost_values") or ["", "", ""]
        self._set_custom_cost_row(self.custom_cost_label_1, self.custom_cost_value_1, custom_labels, custom_values, 0)
        self._set_custom_cost_row(self.custom_cost_label_2, self.custom_cost_value_2, custom_labels, custom_values, 1)
        self._set_custom_cost_row(self.custom_cost_label_3, self.custom_cost_value_3, custom_labels, custom_values, 2)

        procurement_items = order_snapshot.get("procurement_items") or []
        procurement_widgets = [
            (
                self.procurement_product_1_combo,
                self.procurement_quantity_1_value,
                self.procurement_cost_1_value,
                self.procurement_tracking_1_value,
            ),
            (
                self.procurement_product_2_combo,
                self.procurement_quantity_2_value,
                self.procurement_cost_2_value,
                self.procurement_tracking_2_value,
            ),
            (
                self.procurement_product_3_combo,
                self.procurement_quantity_3_value,
                self.procurement_cost_3_value,
                self.procurement_tracking_3_value,
            ),
        ]
        for index, widgets in enumerate(procurement_widgets):
            item = procurement_items[index] if index < len(procurement_items) else {}
            if not isinstance(item, dict):
                item = {}
            if isinstance(widgets[0], QComboBox):
                widgets[0].setCurrentText(self._text_value(item.get("product_name")))
            widgets[1].setText(self._text_value(item.get("quantity")))
            widgets[2].setText(self._text_value(item.get("cost")))
            widgets[3].setText(self._text_value(item.get("tracking_number")))

        self.address_output_one.setPlainText(self._text_value(address_snapshot.get("output_one")))
        self.address_output_two.setPlainText(self._text_value(address_snapshot.get("output_two")))
        self.sync_source_value.setPlainText(self._display_value(row.get("sync_source")))
        self.status_value.setPlainText(self._display_value(row.get("status")))
        self.sync_message_value.setPlainText(self._build_sync_message(row))
        self._update_detail_summary(order_snapshot)
        self._set_widgets_read_only(False)

    def _show_empty_detail(self) -> None:
        self.detail_title_label.setText("请选择一条历史记录")
        self.detail_subtitle_label.setText("详情会显示订单快照、地址提取结果和同步轨迹")
        for widget in (
            self.order_id_value,
            self.placed_at_value,
            self.platform_value,
            self.product_name_value,
            self.specification_value,
            self.sku_value,
            self.quantity_value,
            self.order_amount_value,
            self.income_amount_value,
            self.recipient_name_value,
            self.phone_number_value,
            self.code_value,
            self.address_value,
            self.delivery_note_value,
            self.address_output_one,
            self.address_output_two,
            self.sync_source_value,
            self.status_value,
            self.sync_message_value,
        ):
            widget.setPlainText("")
        for widget in (
            self.platform_fee_amount_value,
            self.other_cost_value,
            self.procurement_total_cost_value,
            self.gross_profit_value,
            self.procurement_quantity_1_value,
            self.procurement_cost_1_value,
            self.procurement_tracking_1_value,
            self.procurement_quantity_2_value,
            self.procurement_cost_2_value,
            self.procurement_tracking_2_value,
            self.procurement_quantity_3_value,
            self.procurement_cost_3_value,
            self.procurement_tracking_3_value,
            self.custom_cost_value_1,
            self.custom_cost_value_2,
            self.custom_cost_value_3,
        ):
            widget.setText("")
        self.platform_fee_rate_value.setText(_DEFAULT_PLATFORM_FEE_RATE)
        self.procurement_product_1_combo.setCurrentText("")
        self.procurement_product_2_combo.setCurrentText("")
        self.procurement_product_3_combo.setCurrentText("")
        self._set_order_status_value("")
        self._set_sku_image("")
        self.custom_cost_label_1.setText("")
        self.custom_cost_label_2.setText("")
        self.custom_cost_label_3.setText("")
        for widget in (
            self.summary_income_value,
            self.summary_order_amount_value,
            self.summary_product_value,
            self.summary_procurement_value,
        ):
            widget.setText("-")
        self._set_widgets_read_only(False)

    def _build_order_snapshot_from_inputs(self, current_snapshot: dict[str, Any]) -> dict[str, Any]:
        order_snapshot = dict(current_snapshot)
        order_snapshot.update(
            {
                "order_id": self._text_value(self.order_id_value.toPlainText()),
                "placed_at": self._text_value(self.placed_at_value.toPlainText()),
                "platform": self._text_value(self.platform_value.toPlainText()) or "抖店",
                "order_status": self._normalize_order_status(self.order_status_value.currentText()),
                "product_name": self._text_value(self.product_name_value.toPlainText()),
                "specification": self._text_value(self.specification_value.toPlainText()),
                "sku": self._text_value(self.sku_value.toPlainText()),
                "sku_image_path": self._text_value(self.sku_image_value.property("imagePath")),
                "quantity": self._text_value(self.quantity_value.toPlainText()),
                "order_amount": self._text_value(self.order_amount_value.toPlainText()),
                "income_amount": self._text_value(self.income_amount_value.toPlainText()),
                "recipient_name": self._text_value(self.recipient_name_value.toPlainText()),
                "phone_number": self._text_value(self.phone_number_value.toPlainText()),
                "code": self._text_value(self.code_value.toPlainText()),
                "address": self._text_value(self.address_value.toPlainText()),
                "delivery_note": self._text_value(self.delivery_note_value.toPlainText()),
                "platform_fee_rate": self._text_value(self.platform_fee_rate_value.text()) or _DEFAULT_PLATFORM_FEE_RATE,
                "platform_fee_amount": self._text_value(self.platform_fee_amount_value.text()),
                "other_cost": self._text_value(self.other_cost_value.text()),
                "procurement_total_cost": self._text_value(self.procurement_total_cost_value.text()),
                "gross_profit": self._text_value(self.gross_profit_value.text()),
                "custom_cost_labels": [
                    self._text_value(self.custom_cost_label_1.text()),
                    self._text_value(self.custom_cost_label_2.text()),
                    self._text_value(self.custom_cost_label_3.text()),
                ],
                "custom_cost_values": [
                    self._text_value(self.custom_cost_value_1.text()),
                    self._text_value(self.custom_cost_value_2.text()),
                    self._text_value(self.custom_cost_value_3.text()),
                ],
                "procurement_items": [
                    self._build_procurement_item_snapshot(
                        self.procurement_product_1_combo,
                        self.procurement_quantity_1_value,
                        self.procurement_cost_1_value,
                        self.procurement_tracking_1_value,
                    ),
                    self._build_procurement_item_snapshot(
                        self.procurement_product_2_combo,
                        self.procurement_quantity_2_value,
                        self.procurement_cost_2_value,
                        self.procurement_tracking_2_value,
                    ),
                    self._build_procurement_item_snapshot(
                        self.procurement_product_3_combo,
                        self.procurement_quantity_3_value,
                        self.procurement_cost_3_value,
                        self.procurement_tracking_3_value,
                    ),
                ],
            }
        )
        order_snapshot["procurement_tracking_number"] = " / ".join(
            item["tracking_number"]
            for item in order_snapshot["procurement_items"]
            if self._text_value(item.get("tracking_number"))
        )
        order_snapshot = self._recalculate_financial_snapshot(order_snapshot)
        return order_snapshot

    def _normalize_row(self, row: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(row)

        order_snapshot = normalized.get("order_snapshot")
        if not isinstance(order_snapshot, dict):
            order_snapshot = {
                key: normalized.get(key)
                for key in (
                    "order_id",
                    "placed_at",
                    "platform",
                    "order_status",
                    "product_name",
                    "quantity",
                    "order_amount",
                    "income_amount",
                    "recipient_name",
                    "phone_number",
                    "code",
                    "address",
                    "delivery_note",
                )
            }
        else:
            order_snapshot = dict(order_snapshot)

        for key in _ORDER_SNAPSHOT_KEYS:
            if key in ("custom_cost_labels", "custom_cost_values"):
                continue
            order_snapshot[key] = self._text_value(order_snapshot.get(key))
        if not order_snapshot.get("platform_fee_rate"):
            order_snapshot["platform_fee_rate"] = _DEFAULT_PLATFORM_FEE_RATE
        custom_cost_labels = order_snapshot.get("custom_cost_labels")
        if not isinstance(custom_cost_labels, list):
            custom_cost_labels = ["", "", ""]
        custom_cost_values = order_snapshot.get("custom_cost_values")
        if not isinstance(custom_cost_values, list):
            custom_cost_values = ["", "", ""]
        order_snapshot["custom_cost_labels"] = [
            self._text_value(custom_cost_labels[index] if index < len(custom_cost_labels) else "")
            for index in range(3)
        ]
        order_snapshot["custom_cost_values"] = [
            self._text_value(custom_cost_values[index] if index < len(custom_cost_values) else "")
            for index in range(3)
        ]

        procurement_items = order_snapshot.get("procurement_items")
        normalized_items = []
        if isinstance(procurement_items, list):
            source_items = procurement_items
        else:
            source_items = []
        for index in range(3):
            item = source_items[index] if index < len(source_items) and isinstance(source_items[index], dict) else {}
            product_name = self._text_value(item.get("product_name"))
            quantity = self._text_value(item.get("quantity"))
            cost = self._text_value(item.get("cost"))
            tracking_number = self._text_value(item.get("tracking_number"))
            normalized_items.append(
                {
                    "product_name": product_name,
                    "quantity": (
                        quantity
                        if quantity != "1" or any((product_name, cost, tracking_number))
                        else ""
                    ) or ("1" if any((product_name, cost, tracking_number)) else ""),
                    "cost": cost,
                    **({"tracking_number": tracking_number} if tracking_number else {}),
                }
            )
        order_snapshot["procurement_items"] = normalized_items
        if not self._text_value(order_snapshot.get("procurement_tracking_number")):
            order_snapshot["procurement_tracking_number"] = " / ".join(
                self._text_value(item.get("tracking_number"))
                for item in normalized_items
                if self._text_value(item.get("tracking_number"))
            )

        address_snapshot = normalized.get("address_snapshot")
        if not isinstance(address_snapshot, dict):
            address_snapshot = {
                "output_one": normalized.get("output_one", ""),
                "output_two": normalized.get("output_two", ""),
            }
        else:
            address_snapshot = dict(address_snapshot)
        address_snapshot["output_one"] = self._text_value(address_snapshot.get("output_one"))
        address_snapshot["output_two"] = self._text_value(address_snapshot.get("output_two"))

        order_snapshot = self._recalculate_financial_snapshot(order_snapshot)
        normalized["order_snapshot"] = order_snapshot
        normalized["address_snapshot"] = address_snapshot
        normalized["sync_source"] = self._display_value(normalized.get("sync_source"))
        normalized["status"] = self._display_value(normalized.get("status"))
        normalized["message"] = self._text_value(normalized.get("message"))
        return normalized

    def _merge_patch(self, row: dict[str, Any], patch: dict[str, Any]) -> None:
        for key, value in patch.items():
            row[key] = value

    def _build_sync_message(self, row: dict[str, Any]) -> str:
        parts: list[str] = []
        message = self._text_value(row.get("message"))
        if message:
            parts.append(message)
        feishu_result = row.get("feishu_result")
        if feishu_result not in (None, ""):
            if isinstance(feishu_result, (dict, list)):
                parts.append(json.dumps(feishu_result, ensure_ascii=False, indent=2))
            else:
                parts.append(str(feishu_result))
        if parts:
            return "\n\n".join(parts)
        return self._display_value(row.get("status"))

    def _current_row(self) -> dict[str, Any] | None:
        index = self.list_widget.currentRow()
        if 0 <= index < len(self._filtered_rows):
            return self._filtered_rows[index]
        if self._filtered_rows:
            return self._filtered_rows[0]
        return None

    def _current_selection(self) -> tuple[str | None, int | None]:
        index = self.list_widget.currentRow()
        if 0 <= index < len(self._filtered_rows):
            record_id = self._text_value(self._filtered_rows[index].get("record_id"))
            if record_id:
                return record_id, index
        return None, None

    def _restore_selection(self, previous_record_id: str | None, previous_index: int | None) -> int | None:
        if not self._filtered_rows:
            return None
        if previous_record_id:
            for index, row in enumerate(self._filtered_rows):
                if self._text_value(row.get("record_id")) == previous_record_id:
                    return index
        if previous_index is not None:
            return min(previous_index, len(self._filtered_rows) - 1)
        return 0

    def _set_widgets_read_only(self, read_only: bool) -> None:
        for widget in self._editable_widgets:
            if hasattr(widget, "setReadOnly"):
                widget.setReadOnly(read_only)
        self.order_status_value.setEnabled(not read_only)
        for widget in (
            self.procurement_product_1_combo,
            self.procurement_product_2_combo,
            self.procurement_product_3_combo,
        ):
            widget.setEnabled(not read_only)

    def _update_action_state(self) -> None:
        has_row = self._current_row() is not None
        self.list_widget.setEnabled(True)
        self.save_button.setEnabled(has_row)
        self.delete_button.setEnabled(has_row)
        self.resubmit_button.setEnabled(has_row)
        self.header_actions_widget.setHidden(not has_row)

    def _update_stats(self) -> None:
        status_scope_rows = [row for row in self._all_rows if self._row_matches_filters(row, ignore_status=True)]
        total = len(status_scope_rows)
        counts = {
            "已发货": 0,
            "待发货": 0,
            "已拍单未发货": 0,
        }
        for row in status_scope_rows:
            status = self._normalize_order_status(self._text_value((row.get("order_snapshot") or {}).get("order_status")))
            if status in counts:
                counts[status] += 1
        self.status_summary_buttons["全部订单"].value_label.setText(str(total))
        self.status_summary_buttons["已发货"].value_label.setText(str(counts["已发货"]))
        self.status_summary_buttons["待发货"].value_label.setText(str(counts["待发货"]))
        self.status_summary_buttons["已拍单未发货"].value_label.setText(str(counts["已拍单未发货"]))
        current_status = self.status_filter_combo.currentText().strip()
        for key, button in self.status_summary_buttons.items():
            button.set_active(
                (key == "全部订单" and current_status == "全部状态")
                or (key != "全部订单" and key == current_status)
            )

    def _build_procurement_item_snapshot(
        self,
        combo: QComboBox,
        quantity_widget: QLineEdit,
        cost_widget: QLineEdit,
        tracking_widget: QLineEdit,
    ) -> dict[str, str]:
        product_name = self._text_value(combo.currentText())
        quantity = self._text_value(quantity_widget.text())
        cost = self._text_value(cost_widget.text())
        tracking_number = self._text_value(tracking_widget.text())
        if any((product_name, cost, tracking_number)):
            quantity = quantity or "1"
        elif quantity == "1":
            quantity = ""
        return {
            "product_name": product_name,
            "quantity": quantity,
            "cost": cost,
            **({"tracking_number": tracking_number} if tracking_number else {}),
        }

    def _update_detail_summary(self, order_snapshot: dict[str, Any]) -> None:
        procurement_items = order_snapshot.get("procurement_items") or []
        first_procurement = next(
            (item for item in procurement_items if isinstance(item, dict) and self._text_value(item.get("product_name"))),
            None,
        )
        if first_procurement:
            procurement_text = (
                f"{self._text_value(first_procurement.get('product_name'))} / "
                f"{self._text_value(first_procurement.get('quantity')) or '1'} / "
                f"{self._text_value(first_procurement.get('cost')) or '-'}"
            )
        else:
            procurement_text = "-"
        self.summary_income_value.setText(self._text_value(order_snapshot.get("income_amount")) or "-")
        self.summary_order_amount_value.setText(self._text_value(order_snapshot.get("order_amount")) or "-")
        self.summary_product_value.setText(self._text_value(order_snapshot.get("product_name")) or "-")
        self.summary_procurement_value.setText(procurement_text)

    def _build_filter_bar(self) -> QWidget:
        container = QFrame()
        container.setObjectName("HistoryFilterCard")
        layout = QHBoxLayout(container)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        for label in ("今天", "昨天", "近7天", "全部"):
            button = QPushButton(label)
            button.setCheckable(True)
            button.setObjectName("SecondaryActionButton")
            self.quick_filter_buttons[label] = button
            layout.addWidget(button)

        self.quick_filter_buttons["全部"].setChecked(True)
        self.keyword_filter_edit.setPlaceholderText("搜订单号 / 收件人 / 手机号 / 快递单号")
        self.keyword_filter_edit.setClearButtonEnabled(True)
        layout.addWidget(self.keyword_filter_edit, 1)
        layout.addWidget(self._label("日期"))
        layout.addWidget(self.date_filter_edit)
        layout.addWidget(self._label("店铺"))
        self.shop_filter_combo.addItem("全部店铺")
        layout.addWidget(self.shop_filter_combo)
        layout.addWidget(self._label("状态"))
        self.status_filter_combo.addItems(["全部状态", *_FIXED_ORDER_STATUS_OPTIONS])
        layout.addWidget(self.status_filter_combo)
        layout.addWidget(self.apply_filters_button)
        layout.addWidget(self.clear_filters_button)
        layout.addStretch(1)
        return container

    def _wire_filter_events(self) -> None:
        for label, button in self.quick_filter_buttons.items():
            button.clicked.connect(lambda checked=False, name=label: self._set_quick_filter(name))
        self.apply_filters_button.clicked.connect(self._apply_filters_from_ui)
        self.clear_filters_button.clicked.connect(self._clear_filters)
        self.date_filter_edit.dateChanged.connect(self._mark_specific_date_active)
        self.keyword_filter_edit.returnPressed.connect(self._apply_filters_from_ui)

    def _wire_edit_events(self) -> None:
        self.income_amount_value.textChanged.connect(self._recalculate_detail_financials)
        self.platform_fee_rate_value.textChanged.connect(self._recalculate_detail_financials)
        self.other_cost_value.textChanged.connect(self._recalculate_detail_financials)
        for widget in (
            self.procurement_quantity_1_value,
            self.procurement_cost_1_value,
            self.procurement_quantity_2_value,
            self.procurement_cost_2_value,
            self.procurement_quantity_3_value,
            self.procurement_cost_3_value,
            self.custom_cost_value_1,
            self.custom_cost_value_2,
            self.custom_cost_value_3,
        ):
            widget.textChanged.connect(self._recalculate_detail_financials)

    def _recalculate_detail_financials(self) -> None:
        row = self._current_row()
        if row is None:
            return
        snapshot = self._build_order_snapshot_from_inputs(row.get("order_snapshot") or {})
        self.platform_fee_amount_value.blockSignals(True)
        self.procurement_total_cost_value.blockSignals(True)
        self.gross_profit_value.blockSignals(True)
        self.platform_fee_amount_value.setText(self._text_value(snapshot.get("platform_fee_amount")))
        self.procurement_total_cost_value.setText(self._text_value(snapshot.get("procurement_total_cost")))
        self.gross_profit_value.setText(self._text_value(snapshot.get("gross_profit")))
        self.platform_fee_amount_value.blockSignals(False)
        self.procurement_total_cost_value.blockSignals(False)
        self.gross_profit_value.blockSignals(False)
        self._update_detail_summary(snapshot)

    def _mark_specific_date_active(self, _date: QDate) -> None:
        self._specific_date_active = True

    def _set_quick_filter(self, name: str) -> None:
        self._active_quick_filter = name
        for label, button in self.quick_filter_buttons.items():
            button.blockSignals(True)
            button.setChecked(label == name)
            button.blockSignals(False)
        today = QDate.currentDate()
        if name == "今天":
            self._specific_date_active = True
            self.date_filter_edit.setDate(today)
        elif name == "昨天":
            self._specific_date_active = True
            self.date_filter_edit.setDate(today.addDays(-1))
        elif name == "全部":
            self._specific_date_active = False
        else:
            self._specific_date_active = False
        self._apply_filters()

    def _clear_filters(self) -> None:
        self.shop_filter_combo.setCurrentIndex(0)
        self.status_filter_combo.setCurrentIndex(0)
        self.keyword_filter_edit.clear()
        self._active_quick_filter = "全部"
        for label, button in self.quick_filter_buttons.items():
            button.blockSignals(True)
            button.setChecked(label == "全部")
            button.blockSignals(False)
        self.date_filter_edit.blockSignals(True)
        self.date_filter_edit.setDate(QDate.currentDate())
        self.date_filter_edit.blockSignals(False)
        self._specific_date_active = False
        self._apply_filters()

    def _apply_filters_from_ui(self) -> None:
        self._apply_filters()

    def _refresh_shop_filter_options(self) -> None:
        current = self.shop_filter_combo.currentText()
        shop_names = ["全部店铺"]
        seen: set[str] = set()
        for row in self._all_rows:
            name = self._display_value(row.get("shop_name"))
            if name != "-" and name not in seen:
                seen.add(name)
                shop_names.append(name)
        self.shop_filter_combo.blockSignals(True)
        self.shop_filter_combo.clear()
        self.shop_filter_combo.addItems(shop_names)
        index = self.shop_filter_combo.findText(current)
        self.shop_filter_combo.setCurrentIndex(index if index >= 0 else 0)
        self.shop_filter_combo.blockSignals(False)

    def _row_matches_filters(self, row: dict[str, Any], ignore_status: bool = False) -> bool:
        order_snapshot = row.get("order_snapshot") or {}
        keyword = self.keyword_filter_edit.text().strip()
        if keyword:
            haystacks = (
                self._display_value(row.get("shop_name")),
                self._text_value(order_snapshot.get("order_id")),
                self._text_value(order_snapshot.get("recipient_name")),
                self._text_value(order_snapshot.get("phone_number")),
                self._text_value(order_snapshot.get("procurement_tracking_number")),
                self._text_value(order_snapshot.get("delivery_note")),
                *[
                    self._text_value(item.get("tracking_number"))
                    for item in order_snapshot.get("procurement_items", [])
                    if isinstance(item, dict)
                ],
            )
            if not any(keyword in value for value in haystacks if value):
                return False
        shop_filter = self.shop_filter_combo.currentText().strip()
        if shop_filter and shop_filter != "全部店铺":
            if self._display_value(row.get("shop_name")) != shop_filter:
                return False
        if not ignore_status:
            status_filter = self.status_filter_combo.currentText().strip()
            normalized_status = self._normalize_order_status(self._text_value(order_snapshot.get("order_status")))
            if status_filter and status_filter != "全部状态":
                if normalized_status != status_filter:
                    return False
        placed_date = self._extract_row_date(order_snapshot)
        if self._specific_date_active:
            selected = self.date_filter_edit.date().toPython()
            return placed_date == selected
        if self._active_quick_filter == "今天":
            return placed_date == date.today()
        if self._active_quick_filter == "昨天":
            return placed_date == date.today() - timedelta(days=1)
        if self._active_quick_filter == "近7天":
            return placed_date >= date.today() - timedelta(days=6)
        return True

    @staticmethod
    def _extract_row_date(order_snapshot: dict[str, Any]) -> date:
        placed_at = str(order_snapshot.get("placed_at", "")).strip()
        try:
            return datetime.strptime(placed_at, "%Y-%m-%d %H:%M:%S").date()
        except ValueError:
            return date.min

    @staticmethod
    def _normalize_order_status(value: str) -> str:
        cleaned = str(value or "").strip()
        return _ORDER_STATUS_ALIASES.get(cleaned, cleaned)

    def _set_order_status_value(self, value: str) -> None:
        normalized = self._normalize_order_status(value) or "待发货"
        index = self.order_status_value.findText(normalized)
        if index < 0:
            index = self.order_status_value.findText("待发货")
        self.order_status_value.setCurrentIndex(max(index, 0))

    def _set_sku_image(self, image_path: str) -> None:
        normalized = self._text_value(image_path)
        self.sku_image_value.setProperty("imagePath", normalized)
        if not normalized:
            self.sku_image_value.setPixmap(QPixmap())
            self.sku_image_value.setText("暂无 SKU 图片")
            return
        pixmap = QPixmap(normalized)
        if pixmap.isNull():
            self.sku_image_value.setPixmap(QPixmap())
            self.sku_image_value.setText("暂无 SKU 图片")
            return
        self.sku_image_value.setText("")
        self.sku_image_value.setPixmap(
            pixmap.scaled(
                88,
                88,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def _set_custom_cost_row(
        self,
        label_widget: QLabel,
        value_widget,
        labels: list[Any],
        values: list[Any],
        index: int,
    ) -> None:
        label_text = self._text_value(labels[index] if index < len(labels) else "")
        value_text = self._text_value(values[index] if index < len(values) else "")
        label_widget.setText(label_text)
        if hasattr(value_widget, "setPlainText"):
            value_widget.setPlainText(value_text)
        else:
            value_widget.setText(value_text)
        label_widget.setVisible(bool(label_text))
        value_widget.setVisible(bool(label_text))

    def _handle_status_card_clicked(self, status_key: str) -> None:
        self.status_filter_combo.setCurrentText(status_key)
        self._apply_filters()

    def _handle_procurement_product_changed(self, _: str) -> None:
        sender = self.sender()
        mapping = {
            self.procurement_product_1_combo: (self.procurement_quantity_1_value, self.procurement_cost_1_value),
            self.procurement_product_2_combo: (self.procurement_quantity_2_value, self.procurement_cost_2_value),
            self.procurement_product_3_combo: (self.procurement_quantity_3_value, self.procurement_cost_3_value),
        }
        if sender in mapping:
            quantity_widget, cost_widget = mapping[sender]
            self._apply_procurement_preset(sender, quantity_widget, cost_widget)

    def _apply_procurement_preset(self, combo: QComboBox, quantity_widget: QLineEdit, cost_widget: QLineEdit) -> None:
        selected_name = self._text_value(combo.currentText())
        if not quantity_widget.text().strip():
            quantity_widget.setText("1")
        if not selected_name:
            self._recalculate_detail_financials()
            return
        for item in self._product_presets:
            if item["name"] == selected_name:
                cost_widget.setText(item["default_cost"])
                self._recalculate_detail_financials()
                return
        self._recalculate_detail_financials()

    def _recalculate_financial_snapshot(self, order_snapshot: dict[str, Any]) -> dict[str, Any]:
        snapshot = dict(order_snapshot)
        income = parse_decimal(snapshot.get("income_amount"))
        if not self._text_value(snapshot.get("platform_fee_rate")):
            snapshot["platform_fee_rate"] = _DEFAULT_PLATFORM_FEE_RATE
        fee_amount = parse_decimal(
            calculate_platform_fee_amount(snapshot.get("income_amount"), snapshot.get("platform_fee_rate"))
        )
        procurement_total = Decimal("0")
        for item in snapshot.get("procurement_items", []):
            if not isinstance(item, dict):
                continue
            procurement_total += parse_decimal(item.get("quantity") or "1") * parse_decimal(item.get("cost"))
        procurement_total = procurement_total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        other_cost = parse_decimal(snapshot.get("other_cost"))
        custom_total = Decimal("0")
        for label, value in zip(snapshot.get("custom_cost_labels", []), snapshot.get("custom_cost_values", [])):
            if self._text_value(label):
                custom_total += parse_decimal(value)
        gross_profit = income - fee_amount - procurement_total - other_cost - custom_total
        snapshot["platform_fee_amount"] = format_money(fee_amount)
        snapshot["procurement_total_cost"] = format_money(procurement_total)
        snapshot["gross_profit"] = format_money(gross_profit)
        return snapshot

    @staticmethod
    def _build_text_value(minimum_height: int = 36, editable: bool = True) -> QTextEdit:
        widget = QTextEdit()
        widget.setAcceptRichText(False)
        widget.setMinimumHeight(minimum_height)
        if minimum_height <= 36:
            widget.setMaximumHeight(40)
        elif minimum_height <= 56:
            widget.setMaximumHeight(60)
        else:
            widget.setMaximumHeight(minimum_height + 12)
        widget.setObjectName("HistoryDetailValue")
        widget.setReadOnly(not editable)
        return widget

    @staticmethod
    def _build_line_edit(read_only: bool = False) -> QLineEdit:
        widget = QLineEdit()
        widget.setObjectName("OrderValueEdit")
        widget.setMinimumHeight(36)
        widget.setMaximumHeight(40)
        widget.setReadOnly(read_only)
        return widget

    @staticmethod
    def _build_procurement_combo() -> QComboBox:
        widget = QComboBox()
        widget.setEditable(True)
        widget.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        widget.setObjectName("OrderValueEdit")
        widget.setMinimumHeight(36)
        widget.addItem("")
        return widget

    @staticmethod
    def _build_section(title: str, form_layout: QFormLayout) -> QFrame:
        frame = QFrame()
        frame.setObjectName("CardFrame")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)
        header = QLabel(title)
        header.setObjectName("SectionTitle")
        layout.addWidget(header)
        layout.addLayout(form_layout)
        return frame

    @staticmethod
    def _build_stat_card(title: str, value: str) -> tuple[QFrame, QLabel]:
        card = QFrame()
        card.setObjectName("HistoryStatCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(2)
        title_label = QLabel(title)
        title_label.setObjectName("HistoryStatTitle")
        value_label = QLabel(value)
        value_label.setObjectName("HistoryStatValue")
        layout.addWidget(title_label)
        layout.addWidget(value_label)
        return card, value_label

    @staticmethod
    def _build_summary_value(title: str) -> tuple[QFrame, QLabel]:
        card = QFrame()
        card.setObjectName("HistoryMiniSummaryCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)
        title_label = QLabel(title)
        title_label.setObjectName("HistoryMiniSummaryTitle")
        value_label = QLabel("-")
        value_label.setObjectName("HistoryMiniSummaryValue")
        value_label.setWordWrap(True)
        layout.addWidget(title_label)
        layout.addWidget(value_label)
        return card, value_label

    @staticmethod
    def _label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("OrderFieldLabel")
        return label

    @staticmethod
    def _text_value(value: Any) -> str:
        return str(value or "").strip()

    @staticmethod
    def _display_value(value: Any) -> str:
        text = str(value or "").strip()
        return text or "-"
