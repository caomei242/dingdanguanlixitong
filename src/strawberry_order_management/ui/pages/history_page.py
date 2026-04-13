from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QScrollArea,
    QFormLayout,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class HistoryPage(QWidget):
    edit_requested = Signal(str)
    delete_requested = Signal(str)
    resubmit_requested = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("HistoryPage")
        self._rows: list[dict[str, Any]] = []

        title = QLabel("历史工作台")
        title.setObjectName("SectionTitle")
        subtitle = QLabel("左侧浏览历史记录，右侧查看详情并执行后续操作")
        subtitle.setObjectName("MutedText")

        self.summary_label = QLabel("暂无记录")
        self.summary_label.setObjectName("MutedText")

        self.list_widget = QListWidget()
        self.list_widget.setObjectName("HistoryList")
        self.list_widget.currentItemChanged.connect(self._handle_current_item_changed)

        list_card = QFrame()
        list_card.setObjectName("HistoryListCard")
        list_card_layout = QVBoxLayout(list_card)
        list_card_layout.addWidget(self.summary_label)
        list_card_layout.addWidget(self.list_widget, 1)

        self.detail_title_label = QLabel("请选择一条历史记录")
        self.detail_title_label.setObjectName("HistoryDetailTitle")
        self.detail_subtitle_label = QLabel("详情会显示店铺、来源、状态和地址快照")
        self.detail_subtitle_label.setObjectName("HistoryDetailMeta")

        self.order_id_value = QTextEdit()
        self.recipient_name_value = QTextEdit()
        self.address_output_one = QTextEdit()
        self.address_output_two = QTextEdit()

        for widget in (
            self.order_id_value,
            self.recipient_name_value,
            self.address_output_one,
            self.address_output_two,
        ):
            widget.setReadOnly(True)
            widget.setObjectName("HistoryDetailValue")
            widget.setMinimumHeight(64)

        detail_form = QFormLayout()
        detail_form.setLabelAlignment(Qt.AlignmentFlag.AlignTop)
        detail_form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        detail_form.addRow("订单编号", self.order_id_value)
        detail_form.addRow("收件人", self.recipient_name_value)
        detail_form.addRow("地址输出 1", self.address_output_one)
        detail_form.addRow("地址输出 2", self.address_output_two)

        self.edit_button = QPushButton("编辑")
        self.edit_button.setObjectName("SecondaryActionButton")
        self.delete_button = QPushButton("删除")
        self.delete_button.setObjectName("DangerActionButton")
        self.resubmit_button = QPushButton("重新提交")
        self.resubmit_button.setObjectName("SecondaryActionButton")

        self.edit_button.clicked.connect(self._emit_edit_requested)
        self.delete_button.clicked.connect(self._emit_delete_requested)
        self.resubmit_button.clicked.connect(self._emit_resubmit_requested)

        action_row = QHBoxLayout()
        action_row.addWidget(self.edit_button)
        action_row.addWidget(self.delete_button)
        action_row.addWidget(self.resubmit_button)

        detail_body = QWidget()
        detail_body_layout = QVBoxLayout(detail_body)
        detail_body_layout.addWidget(self.detail_title_label)
        detail_body_layout.addWidget(self.detail_subtitle_label)
        detail_body_layout.addLayout(detail_form)
        detail_body_layout.addLayout(action_row)
        detail_body_layout.addStretch(1)

        detail_card = QFrame()
        detail_card.setObjectName("HistoryDetailCard")
        detail_card_layout = QVBoxLayout(detail_card)
        detail_card_layout.addWidget(detail_body)

        content = QWidget()
        content.setObjectName("PageContent")
        content_layout = QHBoxLayout(content)
        content_layout.addWidget(list_card, 2)
        content_layout.addWidget(detail_card, 3)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll_area.setWidget(content)

        root = QVBoxLayout(self)
        root.addWidget(title)
        root.addWidget(subtitle)
        root.addWidget(scroll_area)

        self._update_action_state()

    def load_rows(self, rows: list[dict[str, Any]]) -> None:
        previous_record_id, previous_index = self._current_selection()
        self._rows = [self._normalize_row(row) for row in rows]
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
        recipient_name = self._row_value(row, "recipient_name")
        if recipient_name == "-":
            recipient_name = self._display_value(row.get("sync_source"))
        status = self._display_value(row.get("status"))
        order_id = self._row_value(row, "order_id")
        return f"{shop_name} · {recipient_name} · {status} · {order_id}"

    def _handle_current_item_changed(self, current, previous) -> None:
        del current, previous
        row_index = self.list_widget.currentRow()
        self._show_row(row_index)
        self._update_action_state()

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
        self.order_id_value.setPlainText(self._display_value(order_snapshot.get("order_id")))
        self.recipient_name_value.setPlainText(self._display_value(order_snapshot.get("recipient_name")))
        self.address_output_one.setPlainText(self._display_value(address_snapshot.get("output_one")))
        self.address_output_two.setPlainText(self._display_value(address_snapshot.get("output_two")))

    def _show_empty_detail(self) -> None:
        self.detail_title_label.setText("请选择一条历史记录")
        self.detail_subtitle_label.setText("详情会显示店铺、来源、状态和地址快照")
        self.order_id_value.setPlainText("")
        self.recipient_name_value.setPlainText("")
        self.address_output_one.setPlainText("")
        self.address_output_two.setPlainText("")

    def _normalize_row(self, row: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(row)

        order_snapshot = normalized.get("order_snapshot")
        if not isinstance(order_snapshot, dict):
            order_snapshot = {
                key: normalized[key]
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
                if normalized.get(key) is not None
            }
        normalized["order_snapshot"] = dict(order_snapshot)

        address_snapshot = normalized.get("address_snapshot")
        if not isinstance(address_snapshot, dict):
            address_snapshot = {
                key: normalized[key]
                for key in ("output_one", "output_two", "output_three", "address")
                if normalized.get(key) is not None
            }
        address_snapshot = dict(address_snapshot)
        address_snapshot.setdefault("output_one", "")
        address_snapshot.setdefault("output_two", "")
        normalized["address_snapshot"] = address_snapshot

        normalized["sync_source"] = self._display_value(normalized.get("sync_source"))
        return normalized

    def _row_value(self, row: dict[str, Any], key: str) -> str:
        value = row.get(key)
        if value is None:
            order_snapshot = row.get("order_snapshot")
            if isinstance(order_snapshot, dict):
                value = order_snapshot.get(key)
        return self._display_value(value)

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
            record_id = self._display_value(self._rows[index].get("record_id"))
            if record_id != "-":
                return record_id, index
        return None, None

    def _restore_selection(
        self,
        previous_record_id: str | None,
        previous_index: int | None,
    ) -> int | None:
        if not self._rows:
            return None
        if previous_record_id:
            for index, row in enumerate(self._rows):
                if self._display_value(row.get("record_id")) == previous_record_id:
                    return index
        if previous_index is not None:
            return min(previous_index, len(self._rows) - 1)
        return 0

    def _emit_edit_requested(self) -> None:
        self._emit_action(self.edit_requested)

    def _emit_delete_requested(self) -> None:
        self._emit_action(self.delete_requested)

    def _emit_resubmit_requested(self) -> None:
        self._emit_action(self.resubmit_requested)

    def _emit_action(self, signal: Signal) -> None:
        row = self._current_row()
        if not row:
            return
        record_id = self._display_value(row.get("record_id"))
        if record_id == "-":
            return
        signal.emit(record_id)

    def _update_action_state(self) -> None:
        has_row = self._current_row() is not None and self.list_widget.currentRow() >= 0
        self.edit_button.setEnabled(has_row)
        self.delete_button.setEnabled(has_row)
        self.resubmit_button.setEnabled(has_row)

    @staticmethod
    def _display_value(value: Any) -> str:
        if value is None:
            return "-"
        text = str(value).strip()
        return text if text else "-"
