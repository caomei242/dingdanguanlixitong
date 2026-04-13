from __future__ import annotations

import json
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


_ORDER_SNAPSHOT_KEYS = (
    "order_id",
    "placed_at",
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


class HistoryPage(QWidget):
    edit_requested = Signal(str)
    save_requested = Signal(str, object)
    delete_requested = Signal(str)
    resubmit_requested = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("HistoryPage")
        self._rows: list[dict[str, Any]] = []
        self.is_editing = False

        title = QLabel("历史工作台")
        title.setObjectName("SectionTitle")
        subtitle = QLabel("左侧浏览历史记录，右侧查看完整订单快照、同步信息并支持原地编辑")
        subtitle.setObjectName("MutedText")

        self.summary_label = QLabel("暂无记录")
        self.summary_label.setObjectName("MutedText")

        self.total_count_card, self.total_count_value = self._build_stat_card("总记录", "0")
        self.written_count_card, self.written_count_value = self._build_stat_card("已写飞书", "0")
        self.draft_count_card, self.draft_count_value = self._build_stat_card("仅存历史", "0")
        self.failed_count_card, self.failed_count_value = self._build_stat_card("写入失败", "0")

        stats_row = QGridLayout()
        stats_row.setContentsMargins(0, 0, 0, 0)
        stats_row.setHorizontalSpacing(12)
        stats_row.setVerticalSpacing(12)
        stats_row.addWidget(self.total_count_card, 0, 0)
        stats_row.addWidget(self.written_count_card, 0, 1)
        stats_row.addWidget(self.draft_count_card, 0, 2)
        stats_row.addWidget(self.failed_count_card, 0, 3)

        self.list_widget = QListWidget()
        self.list_widget.setObjectName("HistoryList")
        self.list_widget.currentItemChanged.connect(self._handle_current_item_changed)

        list_card = QFrame()
        list_card.setObjectName("HistoryListCard")
        list_card_layout = QVBoxLayout(list_card)
        list_card_layout.addWidget(self.summary_label)
        list_card_layout.addWidget(self.list_widget, 1)

        self.action_card = QFrame()
        self.action_card.setObjectName("HistoryActionCard")

        self.detail_title_label = QLabel("请选择一条历史记录")
        self.detail_title_label.setObjectName("HistoryDetailTitle")
        self.detail_subtitle_label = QLabel("详情会显示订单快照、地址提取结果和同步轨迹")
        self.detail_subtitle_label.setObjectName("HistoryDetailMeta")

        self.order_id_value = self._build_text_value()
        self.placed_at_value = self._build_text_value()
        self.order_status_value = self._build_text_value()
        self.product_name_value = self._build_text_value()
        self.quantity_value = self._build_text_value()
        self.order_amount_value = self._build_text_value()
        self.income_amount_value = self._build_text_value()
        self.recipient_name_value = self._build_text_value()
        self.phone_number_value = self._build_text_value()
        self.code_value = self._build_text_value()
        self.address_value = self._build_text_value(minimum_height=72)
        self.delivery_note_value = self._build_text_value(minimum_height=72)

        order_form = QFormLayout()
        order_form.setLabelAlignment(Qt.AlignmentFlag.AlignTop)
        order_form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        order_form.addRow("订单编号", self.order_id_value)
        order_form.addRow("下单时间", self.placed_at_value)
        order_form.addRow("订单状态", self.order_status_value)
        order_form.addRow("商品名称", self.product_name_value)
        order_form.addRow("数量", self.quantity_value)
        order_form.addRow("订单金额", self.order_amount_value)
        order_form.addRow("收入", self.income_amount_value)
        order_form.addRow("收件人", self.recipient_name_value)
        order_form.addRow("手机号", self.phone_number_value)
        order_form.addRow("编号", self.code_value)
        order_form.addRow("收货地址", self.address_value)
        order_form.addRow("自动备注", self.delivery_note_value)

        order_section = self._build_section("订单基础信息", order_form)

        self.procurement_product_1_value = self._build_text_value()
        self.procurement_quantity_1_value = self._build_text_value()
        self.procurement_cost_1_value = self._build_text_value()
        self.procurement_product_2_value = self._build_text_value()
        self.procurement_quantity_2_value = self._build_text_value()
        self.procurement_cost_2_value = self._build_text_value()
        self.procurement_product_3_value = self._build_text_value()
        self.procurement_quantity_3_value = self._build_text_value()
        self.procurement_cost_3_value = self._build_text_value()

        procurement_form = QFormLayout()
        procurement_form.setLabelAlignment(Qt.AlignmentFlag.AlignTop)
        procurement_form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        procurement_form.addRow("采购 1 商品", self.procurement_product_1_value)
        procurement_form.addRow("采购 1 数量", self.procurement_quantity_1_value)
        procurement_form.addRow("采购 1 成本", self.procurement_cost_1_value)
        procurement_form.addRow("采购 2 商品", self.procurement_product_2_value)
        procurement_form.addRow("采购 2 数量", self.procurement_quantity_2_value)
        procurement_form.addRow("采购 2 成本", self.procurement_cost_2_value)
        procurement_form.addRow("采购 3 商品", self.procurement_product_3_value)
        procurement_form.addRow("采购 3 数量", self.procurement_quantity_3_value)
        procurement_form.addRow("采购 3 成本", self.procurement_cost_3_value)

        procurement_section = self._build_section("采购信息", procurement_form)

        self.address_output_one = self._build_text_value(minimum_height=72, editable=False)
        self.address_output_two = self._build_text_value(minimum_height=72, editable=False)

        address_form = QFormLayout()
        address_form.setLabelAlignment(Qt.AlignmentFlag.AlignTop)
        address_form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        address_form.addRow("结果一", self.address_output_one)
        address_form.addRow("结果二", self.address_output_two)

        address_section = self._build_section("地址提取结果", address_form)

        self.sync_source_value = self._build_text_value(editable=False)
        self.status_value = self._build_text_value(editable=False)
        self.sync_message_value = self._build_text_value(minimum_height=96, editable=False)

        sync_form = QFormLayout()
        sync_form.setLabelAlignment(Qt.AlignmentFlag.AlignTop)
        sync_form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        sync_form.addRow("同步方式", self.sync_source_value)
        sync_form.addRow("当前状态", self.status_value)
        sync_form.addRow("最后状态说明", self.sync_message_value)

        sync_section = self._build_section("同步信息", sync_form)

        self.edit_button = QPushButton("编辑")
        self.edit_button.setObjectName("SecondaryActionButton")
        self.save_button = QPushButton("保存修改")
        self.save_button.setObjectName("SecondaryActionButton")
        self.cancel_button = QPushButton("取消编辑")
        self.cancel_button.setObjectName("SecondaryActionButton")
        self.delete_button = QPushButton("删除")
        self.delete_button.setObjectName("DangerActionButton")
        self.resubmit_button = QPushButton("重新写入飞书")
        self.resubmit_button.setObjectName("SecondaryActionButton")

        self.edit_button.clicked.connect(self._enter_edit_mode)
        self.save_button.clicked.connect(self._emit_save_requested)
        self.cancel_button.clicked.connect(self._cancel_editing)
        self.delete_button.clicked.connect(self._emit_delete_requested)
        self.resubmit_button.clicked.connect(self._emit_resubmit_requested)

        action_row = QHBoxLayout()
        action_row.addWidget(self.edit_button)
        action_row.addWidget(self.save_button)
        action_row.addWidget(self.cancel_button)
        action_row.addStretch(1)

        action_stack = QVBoxLayout(self.action_card)
        action_stack.setContentsMargins(16, 16, 16, 16)
        action_stack.setSpacing(12)
        action_title = QLabel("快捷操作")
        action_title.setObjectName("SectionTitle")
        action_hint = QLabel("把当前选中记录直接编辑、删除或重新写入飞书")
        action_hint.setObjectName("MutedText")
        primary_action_row = QHBoxLayout()
        primary_action_row.addWidget(self.edit_button)
        primary_action_row.addWidget(self.resubmit_button)
        secondary_action_row = QHBoxLayout()
        secondary_action_row.addWidget(self.save_button)
        secondary_action_row.addWidget(self.cancel_button)
        secondary_action_row.addWidget(self.delete_button)
        action_stack.addWidget(action_title)
        action_stack.addWidget(action_hint)
        action_stack.addLayout(primary_action_row)
        action_stack.addLayout(secondary_action_row)

        detail_body = QWidget()
        detail_body_layout = QVBoxLayout(detail_body)
        detail_body_layout.addWidget(self.detail_title_label)
        detail_body_layout.addWidget(self.detail_subtitle_label)

        self.detail_summary_card = QFrame()
        self.detail_summary_card.setObjectName("HistorySummaryCard")
        detail_summary_layout = QGridLayout(self.detail_summary_card)
        detail_summary_layout.setContentsMargins(16, 16, 16, 16)
        detail_summary_layout.setHorizontalSpacing(12)
        detail_summary_layout.setVerticalSpacing(12)
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
        detail_grid.setHorizontalSpacing(14)
        detail_grid.setVerticalSpacing(14)
        detail_grid.addWidget(order_section, 0, 0)
        detail_grid.addWidget(procurement_section, 0, 1)
        detail_grid.addWidget(address_section, 1, 0)
        detail_grid.addWidget(sync_section, 1, 1)

        detail_body_layout.addWidget(self.detail_summary_card)
        detail_body_layout.addLayout(detail_grid)
        detail_body_layout.addStretch(1)

        detail_card = QFrame()
        detail_card.setObjectName("HistoryDetailCard")
        detail_card_layout = QVBoxLayout(detail_card)
        detail_card_layout.addWidget(detail_body)

        left_column = QWidget()
        left_column_layout = QVBoxLayout(left_column)
        left_column_layout.setContentsMargins(0, 0, 0, 0)
        left_column_layout.setSpacing(14)
        left_column_layout.addWidget(list_card, 1)
        left_column_layout.addWidget(self.action_card)

        content = QWidget()
        content.setObjectName("PageContent")
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(18)
        content_layout.addLayout(stats_row)

        workspace_row = QHBoxLayout()
        workspace_row.setSpacing(18)
        workspace_row.addWidget(left_column, 2)
        workspace_row.addWidget(detail_card, 3)
        content_layout.addLayout(workspace_row)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll_area.setWidget(content)

        root = QVBoxLayout(self)
        root.addWidget(title)
        root.addWidget(subtitle)
        root.addWidget(scroll_area)

        self._editable_widgets = [
            self.order_id_value,
            self.placed_at_value,
            self.order_status_value,
            self.product_name_value,
            self.quantity_value,
            self.order_amount_value,
            self.income_amount_value,
            self.recipient_name_value,
            self.phone_number_value,
            self.code_value,
            self.address_value,
            self.delivery_note_value,
            self.procurement_product_1_value,
            self.procurement_quantity_1_value,
            self.procurement_cost_1_value,
            self.procurement_product_2_value,
            self.procurement_quantity_2_value,
            self.procurement_cost_2_value,
            self.procurement_product_3_value,
            self.procurement_quantity_3_value,
            self.procurement_cost_3_value,
        ]

        self._set_widgets_read_only(True)
        self._update_action_state()

    def load_rows(self, rows: list[dict[str, Any]]) -> None:
        previous_record_id, previous_index = self._current_selection()
        self.is_editing = False
        self._rows = [self._normalize_row(row) for row in rows]
        self._update_stats()
        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        self.summary_label.setText(f"共 {len(self._rows)} 条记录")
        if not self._rows:
            self.list_widget.addItem("暂无历史记录")
            self.list_widget.blockSignals(False)
            self._show_empty_detail()
            self._update_action_state()
            return

        for row in self._rows:
            self.list_widget.addItem(self._build_row_text(row))

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
        return f"{shop_name} · {recipient_name} · {status} · {order_id}"

    def _handle_current_item_changed(self, current, previous) -> None:
        del current, previous
        if self.is_editing:
            self.is_editing = False
        self._show_row(self.list_widget.currentRow())
        self._update_action_state()

    def _enter_edit_mode(self) -> None:
        row = self._current_row()
        if row is None:
            return
        self.is_editing = True
        self._show_row(self.list_widget.currentRow())
        self._update_action_state()
        record_id = self._text_value(row.get("record_id"))
        if record_id:
            self.edit_requested.emit(record_id)

    def _cancel_editing(self) -> None:
        if not self.is_editing:
            return
        self.is_editing = False
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
        self.is_editing = False
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
        if row_index < 0 or row_index >= len(self._rows):
            self._show_empty_detail()
            return

        row = self._rows[row_index]
        order_snapshot = row.get("order_snapshot") or {}
        address_snapshot = row.get("address_snapshot") or {}

        self.detail_title_label.setText(self._display_value(row.get("shop_name")))
        self.detail_subtitle_label.setText(
            f"{self._display_value(row.get('sync_source'))} · {self._display_value(row.get('status'))}"
        )

        self.order_id_value.setPlainText(self._text_value(order_snapshot.get("order_id")))
        self.placed_at_value.setPlainText(self._text_value(order_snapshot.get("placed_at")))
        self.order_status_value.setPlainText(self._text_value(order_snapshot.get("order_status")))
        self.product_name_value.setPlainText(self._text_value(order_snapshot.get("product_name")))
        self.quantity_value.setPlainText(self._text_value(order_snapshot.get("quantity")))
        self.order_amount_value.setPlainText(self._text_value(order_snapshot.get("order_amount")))
        self.income_amount_value.setPlainText(self._text_value(order_snapshot.get("income_amount")))
        self.recipient_name_value.setPlainText(self._text_value(order_snapshot.get("recipient_name")))
        self.phone_number_value.setPlainText(self._text_value(order_snapshot.get("phone_number")))
        self.code_value.setPlainText(self._text_value(order_snapshot.get("code")))
        self.address_value.setPlainText(self._text_value(order_snapshot.get("address")))
        self.delivery_note_value.setPlainText(self._text_value(order_snapshot.get("delivery_note")))

        procurement_items = order_snapshot.get("procurement_items") or []
        procurement_widgets = [
            (
                self.procurement_product_1_value,
                self.procurement_quantity_1_value,
                self.procurement_cost_1_value,
            ),
            (
                self.procurement_product_2_value,
                self.procurement_quantity_2_value,
                self.procurement_cost_2_value,
            ),
            (
                self.procurement_product_3_value,
                self.procurement_quantity_3_value,
                self.procurement_cost_3_value,
            ),
        ]
        for index, widgets in enumerate(procurement_widgets):
            item = procurement_items[index] if index < len(procurement_items) else {}
            if not isinstance(item, dict):
                item = {}
            widgets[0].setPlainText(self._text_value(item.get("product_name")))
            widgets[1].setPlainText(self._text_value(item.get("quantity")) or "1")
            widgets[2].setPlainText(self._text_value(item.get("cost")))

        self.address_output_one.setPlainText(self._text_value(address_snapshot.get("output_one")))
        self.address_output_two.setPlainText(self._text_value(address_snapshot.get("output_two")))
        self.sync_source_value.setPlainText(self._display_value(row.get("sync_source")))
        self.status_value.setPlainText(self._display_value(row.get("status")))
        self.sync_message_value.setPlainText(self._build_sync_message(row))
        self._update_detail_summary(order_snapshot)
        self._set_widgets_read_only(not self.is_editing)

    def _show_empty_detail(self) -> None:
        self.detail_title_label.setText("请选择一条历史记录")
        self.detail_subtitle_label.setText("详情会显示订单快照、地址提取结果和同步轨迹")
        for widget in (
            self.order_id_value,
            self.placed_at_value,
            self.order_status_value,
            self.product_name_value,
            self.quantity_value,
            self.order_amount_value,
            self.income_amount_value,
            self.recipient_name_value,
            self.phone_number_value,
            self.code_value,
            self.address_value,
            self.delivery_note_value,
            self.procurement_product_1_value,
            self.procurement_quantity_1_value,
            self.procurement_cost_1_value,
            self.procurement_product_2_value,
            self.procurement_quantity_2_value,
            self.procurement_cost_2_value,
            self.procurement_product_3_value,
            self.procurement_quantity_3_value,
            self.procurement_cost_3_value,
            self.address_output_one,
            self.address_output_two,
            self.sync_source_value,
            self.status_value,
            self.sync_message_value,
        ):
            widget.setPlainText("")
        for widget in (
            self.summary_income_value,
            self.summary_order_amount_value,
            self.summary_product_value,
            self.summary_procurement_value,
        ):
            widget.setText("-")
        self._set_widgets_read_only(True)

    def _build_order_snapshot_from_inputs(self, current_snapshot: dict[str, Any]) -> dict[str, Any]:
        order_snapshot = dict(current_snapshot)
        order_snapshot.update(
            {
                "order_id": self._text_value(self.order_id_value.toPlainText()),
                "placed_at": self._text_value(self.placed_at_value.toPlainText()),
                "order_status": self._text_value(self.order_status_value.toPlainText()),
                "product_name": self._text_value(self.product_name_value.toPlainText()),
                "quantity": self._text_value(self.quantity_value.toPlainText()),
                "order_amount": self._text_value(self.order_amount_value.toPlainText()),
                "income_amount": self._text_value(self.income_amount_value.toPlainText()),
                "recipient_name": self._text_value(self.recipient_name_value.toPlainText()),
                "phone_number": self._text_value(self.phone_number_value.toPlainText()),
                "code": self._text_value(self.code_value.toPlainText()),
                "address": self._text_value(self.address_value.toPlainText()),
                "delivery_note": self._text_value(self.delivery_note_value.toPlainText()),
                "procurement_items": [
                {
                    "product_name": self._text_value(self.procurement_product_1_value.toPlainText()),
                    "quantity": self._text_value(self.procurement_quantity_1_value.toPlainText()) or "1",
                    "cost": self._text_value(self.procurement_cost_1_value.toPlainText()),
                },
                {
                    "product_name": self._text_value(self.procurement_product_2_value.toPlainText()),
                    "quantity": self._text_value(self.procurement_quantity_2_value.toPlainText()) or "1",
                    "cost": self._text_value(self.procurement_cost_2_value.toPlainText()),
                },
                {
                    "product_name": self._text_value(self.procurement_product_3_value.toPlainText()),
                    "quantity": self._text_value(self.procurement_quantity_3_value.toPlainText()) or "1",
                    "cost": self._text_value(self.procurement_cost_3_value.toPlainText()),
                },
                ],
            }
        )
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
            order_snapshot[key] = self._text_value(order_snapshot.get(key))

        procurement_items = order_snapshot.get("procurement_items")
        normalized_items = []
        if isinstance(procurement_items, list):
            source_items = procurement_items
        else:
            source_items = []
        for index in range(3):
            item = source_items[index] if index < len(source_items) and isinstance(source_items[index], dict) else {}
            normalized_items.append(
                {
                    "product_name": self._text_value(item.get("product_name")),
                    "quantity": self._text_value(item.get("quantity")) or "1",
                    "cost": self._text_value(item.get("cost")),
                }
            )
        order_snapshot["procurement_items"] = normalized_items

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
        if 0 <= index < len(self._rows):
            return self._rows[index]
        if self._rows:
            return self._rows[0]
        return None

    def _current_selection(self) -> tuple[str | None, int | None]:
        index = self.list_widget.currentRow()
        if 0 <= index < len(self._rows):
            record_id = self._text_value(self._rows[index].get("record_id"))
            if record_id:
                return record_id, index
        return None, None

    def _restore_selection(self, previous_record_id: str | None, previous_index: int | None) -> int | None:
        if not self._rows:
            return None
        if previous_record_id:
            for index, row in enumerate(self._rows):
                if self._text_value(row.get("record_id")) == previous_record_id:
                    return index
        if previous_index is not None:
            return min(previous_index, len(self._rows) - 1)
        return 0

    def _set_widgets_read_only(self, read_only: bool) -> None:
        for widget in self._editable_widgets:
            widget.setReadOnly(read_only)

    def _update_action_state(self) -> None:
        has_row = self._current_row() is not None
        self.list_widget.setEnabled(has_row and not self.is_editing)
        self.edit_button.setEnabled(has_row and not self.is_editing)
        self.save_button.setEnabled(has_row and self.is_editing)
        self.cancel_button.setEnabled(has_row and self.is_editing)
        self.delete_button.setEnabled(has_row and not self.is_editing)
        self.resubmit_button.setEnabled(has_row and not self.is_editing)

    def _update_stats(self) -> None:
        total = len(self._rows)
        written = sum(1 for row in self._rows if self._display_value(row.get("status")) == "已写入飞书")
        draft = sum(1 for row in self._rows if self._display_value(row.get("status")) == "仅存历史")
        failed = sum(1 for row in self._rows if self._display_value(row.get("status")) == "写入失败")
        self.total_count_value.setText(str(total))
        self.written_count_value.setText(str(written))
        self.draft_count_value.setText(str(draft))
        self.failed_count_value.setText(str(failed))

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

    @staticmethod
    def _build_text_value(minimum_height: int = 44, editable: bool = True) -> QTextEdit:
        widget = QTextEdit()
        widget.setAcceptRichText(False)
        widget.setMinimumHeight(minimum_height)
        widget.setObjectName("HistoryDetailValue")
        widget.setReadOnly(not editable)
        return widget

    @staticmethod
    def _build_section(title: str, form_layout: QFormLayout) -> QFrame:
        frame = QFrame()
        frame.setObjectName("CardFrame")
        layout = QVBoxLayout(frame)
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
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(6)
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
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)
        title_label = QLabel(title)
        title_label.setObjectName("HistoryMiniSummaryTitle")
        value_label = QLabel("-")
        value_label.setObjectName("HistoryMiniSummaryValue")
        value_label.setWordWrap(True)
        layout.addWidget(title_label)
        layout.addWidget(value_label)
        return card, value_label

    @staticmethod
    def _text_value(value: Any) -> str:
        return str(value or "").strip()

    @staticmethod
    def _display_value(value: Any) -> str:
        text = str(value or "").strip()
        return text or "-"
