from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtWidgets import (
    QDateEdit,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QComboBox,
    QMessageBox,
)

from strawberry_order_management.services.auto_order import (
    AUTO_ORDER_ITEM_STATUS_FAILED,
    AUTO_ORDER_ITEM_STATUS_READY_TO_PAY,
    AUTO_ORDER_STATUS_OPTIONS,
    normalize_procurement_items,
    procurement_item_auto_status,
    procurement_item_has_content,
    row_auto_order_status,
    row_has_auto_order_scope,
    unresolved_procurement_indices,
)


def _text(value: Any) -> str:
    return str(value or "").strip()


class _AutoOrderProcessDialog(QDialog):
    def __init__(self, row: dict[str, Any], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("最近一次自动拍单过程")
        self.setModal(False)
        self.resize(560, 420)

        debug_payload = dict(row.get("auto_order_debug") or {})

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        summary_form = QVBoxLayout()
        summary_form.setContentsMargins(0, 0, 0, 0)
        summary_form.setSpacing(8)

        self.status_value_label = QLabel(_text(row.get("auto_order_status")) or "待处理")
        self.status_value_label.setObjectName("HistoryDetailTitle")
        self.summary_value_label = QLabel(_text(debug_payload.get("summary")) or _text(row.get("auto_order_message")) or "-")
        self.summary_value_label.setWordWrap(True)
        self.updated_at_value_label = QLabel(_text(debug_payload.get("updated_at")) or _text(row.get("auto_order_last_run_at")) or "-")
        self.updated_at_value_label.setObjectName("MutedText")
        self.stage_value_label = QLabel(_text(debug_payload.get("stage")) or "-")
        self.stage_value_label.setObjectName("MutedText")
        self.screenshot_path_label = QLabel(_text(debug_payload.get("screenshot_path")) or "")
        self.screenshot_path_label.setWordWrap(True)
        self.screenshot_path_label.setObjectName("MutedText")
        self.steps_text = QTextEdit()
        self.steps_text.setReadOnly(True)
        self.steps_text.setPlainText(self._format_steps(debug_payload.get("steps")))

        summary_form.addWidget(QLabel("最近任务状态"))
        summary_form.addWidget(self.status_value_label)
        summary_form.addWidget(QLabel("最终结果"))
        summary_form.addWidget(self.summary_value_label)
        summary_form.addWidget(QLabel("最近阶段"))
        summary_form.addWidget(self.stage_value_label)
        summary_form.addWidget(QLabel("最近更新时间"))
        summary_form.addWidget(self.updated_at_value_label)
        summary_form.addWidget(QLabel("失败截图"))
        summary_form.addWidget(self.screenshot_path_label)
        summary_form.addWidget(QLabel("步骤日志"))
        summary_form.addWidget(self.steps_text, 1)

        root.addLayout(summary_form)

    @staticmethod
    def _format_steps(value: Any) -> str:
        lines: list[str] = []
        for item in list(value or []):
            if not isinstance(item, dict):
                continue
            at = _text(item.get("at"))
            text = _text(item.get("text"))
            if not at and not text:
                continue
            lines.append(f"{at} {text}".strip())
        return "\n".join(lines) if lines else "暂无过程记录"


class _AutoOrderSlotRow(QFrame):
    action_requested = Signal(int)

    def __init__(self, slot_index: int, item: dict[str, Any]) -> None:
        super().__init__()
        self.slot_index = slot_index
        self.item = item
        self.setObjectName("AutoOrderSlotRow")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(12)

        self.slot_name_label = QLabel(f"采购{slot_index + 1}")
        self.slot_name_label.setObjectName("OrderFieldLabel")
        self.product_label = QLabel(_text(item.get("product_name")) or "-")
        self.quantity_label = QLabel(_text(item.get("quantity")) or "-")
        self.status_label = QLabel(procurement_item_auto_status(item) or "-")
        self.jd_order_id_label = QLabel(_text(item.get("jd_order_id")) or "-")
        self.action_button = QPushButton(self._action_text(item))
        self.action_button.setObjectName("SecondaryActionButton")

        layout.addWidget(self.slot_name_label, 1)
        layout.addWidget(self.product_label, 3)
        layout.addWidget(self.quantity_label, 1)
        layout.addWidget(self.status_label, 2)
        layout.addWidget(self.jd_order_id_label, 2)
        layout.addWidget(self.action_button, 1)
        self.action_button.clicked.connect(lambda: self.action_requested.emit(self.slot_index))

    @staticmethod
    def _action_text(item: dict[str, Any]) -> str:
        status = procurement_item_auto_status(item)
        if status == AUTO_ORDER_ITEM_STATUS_READY_TO_PAY:
            return "重新发起"
        if status == AUTO_ORDER_ITEM_STATUS_FAILED:
            return "重拍"
        return "开始"


class _AutoOrderGroupWidget(QFrame):
    request_requested = Signal(str, object)
    history_view_requested = Signal(str)
    process_view_requested = Signal(str)

    def __init__(self, row: dict[str, Any]) -> None:
        super().__init__()
        self.record_id = _text(row.get("record_id"))
        self.row = row
        self.slot_rows: list[_AutoOrderSlotRow] = []
        self.setObjectName("AutoOrderGroupCard")

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(10)
        title_column = QVBoxLayout()
        title_column.setContentsMargins(0, 0, 0, 0)
        title_column.setSpacing(4)

        title = QLabel(
            f"{_text(row.get('shop_name')) or '-'} / {_text((row.get('order_snapshot') or {}).get('recipient_name')) or '-'}"
        )
        title.setObjectName("HistoryDetailTitle")
        subtitle = QLabel(
            f"订单号尾号 {_text((row.get('order_snapshot') or {}).get('order_id'))[-4:] or '-'} · 下单时间 {_text((row.get('order_snapshot') or {}).get('placed_at')) or '-'}"
        )
        subtitle.setObjectName("MutedText")
        title_column.addWidget(title)
        title_column.addWidget(subtitle)

        action_column = QHBoxLayout()
        action_column.setContentsMargins(0, 0, 0, 0)
        action_column.setSpacing(8)
        self.header_status_badge = QLabel(row_auto_order_status(row))
        self.header_status_badge.setObjectName("MutedText")
        self.view_process_button = QPushButton("查看过程")
        self.view_process_button.setObjectName("SecondaryActionButton")
        self.view_process_button.clicked.connect(lambda: self.process_view_requested.emit(self.record_id))
        self.history_jump_button = QPushButton("跳转历史")
        self.history_jump_button.setObjectName("SecondaryActionButton")
        self.history_jump_button.clicked.connect(lambda: self.history_view_requested.emit(self.record_id))
        self.primary_action_button = QPushButton(self._primary_action_text(row))
        self.primary_action_button.setObjectName("SecondaryActionButton")
        self.primary_action_button.clicked.connect(self._handle_primary_action)
        action_column.addWidget(self.header_status_badge)
        action_column.addWidget(self.view_process_button)
        action_column.addWidget(self.history_jump_button)
        action_column.addWidget(self.primary_action_button)

        header.addLayout(title_column, 1)
        header.addLayout(action_column, 0)
        root.addLayout(header)

        table_header = QFrame()
        table_header.setObjectName("AutoOrderTableHeader")
        table_header_layout = QHBoxLayout(table_header)
        table_header_layout.setContentsMargins(12, 8, 12, 8)
        table_header_layout.setSpacing(12)
        for title_text, stretch in (
            ("采购位", 1),
            ("商品", 3),
            ("数量", 1),
            ("状态", 2),
            ("京东单号", 2),
            ("操作", 1),
        ):
            label = QLabel(title_text)
            label.setObjectName("OrderFieldLabel")
            table_header_layout.addWidget(label, stretch)
        root.addWidget(table_header)

        procurement_items = normalize_procurement_items((row.get("order_snapshot") or {}).get("procurement_items"))
        for index, item in enumerate(procurement_items):
            if not procurement_item_has_content(item):
                continue
            slot_row = _AutoOrderSlotRow(index, item)
            slot_row.action_requested.connect(self._handle_slot_action)
            self.slot_rows.append(slot_row)
            root.addWidget(slot_row)

        failure_summary = self._failure_summary(procurement_items, _text(row.get("auto_order_resume_hint")))
        self.failure_summary_label = QLabel(failure_summary)
        self.failure_summary_label.setObjectName("MutedText")
        self.failure_summary_label.setVisible(bool(failure_summary))
        root.addWidget(self.failure_summary_label)

    def _handle_primary_action(self) -> None:
        indices = self._requestable_indices()
        if not indices:
            self.history_view_requested.emit(self.record_id)
            return
        if self._requires_confirmation(indices) and not self._confirm_request("整单"):
            return
        self.request_requested.emit(self.record_id, indices)

    def _handle_slot_action(self, slot_index: int) -> None:
        item = self.slot_rows_by_index().get(slot_index)
        if item is not None and procurement_item_auto_status(item.item) == AUTO_ORDER_ITEM_STATUS_READY_TO_PAY:
            if not self._confirm_request(f"采购{slot_index + 1}"):
                return
        self.request_requested.emit(self.record_id, (slot_index,))

    @staticmethod
    def _primary_action_text(row: dict[str, Any]) -> str:
        status = row_auto_order_status(row)
        if status in ("部分成功", "失败"):
            return "重拍未成功采购位"
        if status == "已到待付款":
            return "重新发起订单"
        return "开始拍单"

    @staticmethod
    def _failure_summary(items: list[dict[str, Any]], resume_hint: str = "") -> str:
        parts: list[str] = []
        for index, item in enumerate(items, start=1):
            if procurement_item_auto_status(item) != AUTO_ORDER_ITEM_STATUS_FAILED:
                continue
            error_message = _text(item.get("jd_error_message"))
            if error_message:
                parts.append(f"采购{index}：{error_message}")
        if resume_hint:
            parts.append(resume_hint)
        return "失败摘要： " + "；".join(parts) if parts else ""

    def _requestable_indices(self) -> tuple[int, ...]:
        unresolved = unresolved_procurement_indices(self.row)
        if unresolved:
            return unresolved
        items = normalize_procurement_items((self.row.get("order_snapshot") or {}).get("procurement_items"))
        return tuple(index for index, item in enumerate(items) if procurement_item_has_content(item))

    def _requires_confirmation(self, indices: tuple[int, ...]) -> bool:
        items = normalize_procurement_items((self.row.get("order_snapshot") or {}).get("procurement_items"))
        return any(
            index < len(items) and procurement_item_auto_status(items[index]) == AUTO_ORDER_ITEM_STATUS_READY_TO_PAY
            for index in indices
        )

    def _confirm_request(self, scope_label: str) -> bool:
        confirm = QMessageBox.question(
            self,
            "二次确认",
            f"这会再次生成新的待付款订单，确定重新发起{scope_label}吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return confirm == QMessageBox.StandardButton.Yes

    def slot_rows_by_index(self) -> dict[int, _AutoOrderSlotRow]:
        return {slot_row.slot_index: slot_row for slot_row in self.slot_rows}


class AutoOrderPage(QWidget):
    auto_order_requested = Signal(str, object)
    history_view_requested = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("AutoOrderPage")
        self._all_rows: list[dict[str, Any]] = []
        self._filtered_rows: list[dict[str, Any]] = []
        self._active_quick_filter = "全部"
        self._specific_date_active = False
        self.order_group_widgets: list[_AutoOrderGroupWidget] = []
        self._focused_record_id = ""
        self._process_dialog: _AutoOrderProcessDialog | None = None

        title = QLabel("自动拍单")
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
        self.summary_label = QLabel("共 0 单")
        self.summary_label.setObjectName("MutedText")

        filter_bar = self._build_filter_bar()

        self.group_container = QWidget()
        self.group_layout = QVBoxLayout(self.group_container)
        self.group_layout.setContentsMargins(0, 0, 0, 0)
        self.group_layout.setSpacing(22)
        self.group_layout.addStretch(1)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll_area.setWidget(self.group_container)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)
        root.addWidget(title)
        root.addWidget(filter_bar)
        root.addWidget(self.summary_label)
        root.addWidget(scroll_area, 1)

        self._wire_events()

    def load_rows(self, rows: list[dict[str, Any]]) -> None:
        self._all_rows = [self._normalize_row(row) for row in rows if row_has_auto_order_scope(row)]
        self._refresh_shop_filter_options()
        self._apply_filters()

    def focus_record(self, record_id: str) -> None:
        self._focused_record_id = _text(record_id)
        self._apply_filters()

    def _normalize_row(self, row: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(row)
        order_snapshot = dict(normalized.get("order_snapshot") or {})
        order_snapshot["order_id"] = _text(order_snapshot.get("order_id"))
        order_snapshot["placed_at"] = _text(order_snapshot.get("placed_at"))
        order_snapshot["recipient_name"] = _text(order_snapshot.get("recipient_name"))
        order_snapshot["procurement_items"] = normalize_procurement_items(order_snapshot.get("procurement_items"))
        normalized["order_snapshot"] = order_snapshot
        normalized["shop_name"] = _text(normalized.get("shop_name"))
        normalized["auto_order_status"] = _text(normalized.get("auto_order_status"))
        normalized["auto_order_message"] = _text(normalized.get("auto_order_message"))
        normalized["auto_order_last_run_at"] = _text(normalized.get("auto_order_last_run_at"))
        normalized["auto_order_resume_hint"] = _text(normalized.get("auto_order_resume_hint"))
        normalized["auto_order_debug"] = dict(normalized.get("auto_order_debug") or {})
        return normalized

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

        self.keyword_filter_edit.setPlaceholderText("搜店铺 / 收件人 / 订单号尾号")
        self.keyword_filter_edit.setClearButtonEnabled(True)
        layout.addWidget(self.keyword_filter_edit, 1)
        layout.addWidget(self._label("日期"))
        layout.addWidget(self.date_filter_edit)
        layout.addWidget(self._label("店铺"))
        self.shop_filter_combo.addItem("全部店铺")
        layout.addWidget(self.shop_filter_combo)
        layout.addWidget(self._label("拍单状态"))
        self.status_filter_combo.addItems(["全部状态", *AUTO_ORDER_STATUS_OPTIONS])
        layout.addWidget(self.status_filter_combo)
        layout.addWidget(self.apply_filters_button)
        layout.addWidget(self.clear_filters_button)
        layout.addStretch(1)
        return container

    def _wire_events(self) -> None:
        for label, button in self.quick_filter_buttons.items():
            button.clicked.connect(lambda checked=False, name=label: self._set_quick_filter(name))
        self.apply_filters_button.clicked.connect(self._apply_filters)
        self.clear_filters_button.clicked.connect(self._clear_filters)
        self.keyword_filter_edit.returnPressed.connect(self._apply_filters)
        self.date_filter_edit.dateChanged.connect(self._mark_specific_date_active)

    def _refresh_shop_filter_options(self) -> None:
        current = self.shop_filter_combo.currentText().strip()
        shop_names = ["全部店铺"]
        seen: set[str] = set()
        for row in self._all_rows:
            shop_name = _text(row.get("shop_name"))
            if shop_name and shop_name not in seen:
                seen.add(shop_name)
                shop_names.append(shop_name)
        self.shop_filter_combo.blockSignals(True)
        self.shop_filter_combo.clear()
        self.shop_filter_combo.addItems(shop_names)
        index = self.shop_filter_combo.findText(current)
        self.shop_filter_combo.setCurrentIndex(index if index >= 0 else 0)
        self.shop_filter_combo.blockSignals(False)

    def _apply_filters(self) -> None:
        filtered_rows = [row for row in self._all_rows if self._row_matches_filters(row)]
        if self._focused_record_id:
            focus_matches = [
                row for row in filtered_rows if _text(row.get("record_id")) == self._focused_record_id
            ]
            if focus_matches:
                filtered_rows = focus_matches + [row for row in filtered_rows if row not in focus_matches]
        self._filtered_rows = filtered_rows
        self.summary_label.setText(f"共 {len(self._filtered_rows)} 单")

        while self.group_layout.count():
            item = self.group_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.order_group_widgets = []

        for row in self._filtered_rows:
            widget = _AutoOrderGroupWidget(row)
            widget.request_requested.connect(self.auto_order_requested.emit)
            widget.history_view_requested.connect(self.history_view_requested.emit)
            widget.process_view_requested.connect(self._open_process_dialog)
            self.order_group_widgets.append(widget)
            self.group_layout.addWidget(widget)
        self.group_layout.addStretch(1)

    def _open_process_dialog(self, record_id: str) -> None:
        target_row = next(
            (row for row in self._filtered_rows if _text(row.get("record_id")) == _text(record_id)),
            None,
        )
        if target_row is None:
            return
        self._process_dialog = _AutoOrderProcessDialog(target_row, self)
        self._process_dialog.show()

    def _row_matches_filters(self, row: dict[str, Any]) -> bool:
        order_snapshot = row.get("order_snapshot") or {}
        keyword = self.keyword_filter_edit.text().strip()
        if keyword:
            haystacks = (
                _text(row.get("shop_name")),
                _text(order_snapshot.get("recipient_name")),
                _text(order_snapshot.get("order_id")),
            )
            if not any(keyword in value for value in haystacks if value):
                return False
        shop_filter = self.shop_filter_combo.currentText().strip()
        if shop_filter and shop_filter != "全部店铺":
            if _text(row.get("shop_name")) != shop_filter:
                return False
        status_filter = self.status_filter_combo.currentText().strip()
        if status_filter and status_filter != "全部状态":
            if row_auto_order_status(row) != status_filter:
                return False
        placed_date = self._extract_row_date(_text(order_snapshot.get("placed_at")))
        if self._specific_date_active:
            return placed_date == self.date_filter_edit.date().toPython()
        if self._active_quick_filter == "今天":
            return placed_date == date.today()
        if self._active_quick_filter == "昨天":
            return placed_date == date.today() - timedelta(days=1)
        if self._active_quick_filter == "近7天":
            return placed_date >= date.today() - timedelta(days=6)
        return True

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
        self._focused_record_id = ""
        self._apply_filters()

    def _mark_specific_date_active(self, _date: QDate) -> None:
        self._specific_date_active = True

    @staticmethod
    def _extract_row_date(value: str) -> date:
        try:
            return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").date()
        except ValueError:
            return date.min

    @staticmethod
    def _label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("OrderFieldLabel")
        return label
