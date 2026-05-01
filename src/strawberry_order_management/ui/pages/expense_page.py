from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from strawberry_order_management.finance import format_money, parse_decimal

_SCOPE_TYPES = ("订单级", "店铺级", "项目级")
_PLATFORM_OPTIONS = ("", "抖店", "微信小店")
_CATEGORY_OPTIONS = (
    "售后补偿",
    "软件服务",
    "设备采购",
    "广告投放",
    "仓配物流",
    "人工运营",
    "项目杂项",
)


class _ExpenseStatCard(QFrame):
    def __init__(self, title: str) -> None:
        super().__init__()
        self.setObjectName("HistoryStatCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(2)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("HistoryStatTitle")
        self.value_label = QLabel("0.00")
        self.value_label.setObjectName("HistoryStatValue")
        self.meta_label = QLabel("")
        self.meta_label.setObjectName("MutedText")
        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)
        layout.addWidget(self.meta_label)


class _ExpenseSummaryChip(QFrame):
    def __init__(self, title: str) -> None:
        super().__init__()
        self.setObjectName("HistoryMiniSummaryCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(2)
        title_label = QLabel(title)
        title_label.setObjectName("HistoryMiniSummaryTitle")
        self.value_label = QLabel("—")
        self.value_label.setObjectName("HistoryMiniSummaryValue")
        layout.addWidget(title_label)
        layout.addWidget(self.value_label)


class ExpensePage(QWidget):
    save_requested = Signal(str, object)
    delete_requested = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._rows: list[dict[str, Any]] = []
        self._filtered_rows: list[dict[str, Any]] = []
        self._history_rows: list[dict[str, Any]] = []
        self._shop_names: list[str] = []
        self._selected_record_id = ""
        self._current_scope = "订单级"

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索：备注 / 店铺 / 订单号 / 分类")
        self.month_filter_combo = QComboBox()
        self.scope_filter_combo = QComboBox()
        self.scope_filter_combo.addItems(["全部层级", *_SCOPE_TYPES])
        self.shop_filter_combo = QComboBox()
        self.apply_filters_button = QPushButton("应用筛选")
        self.clear_filters_button = QPushButton("清空")
        self.status_label = QLabel("")
        self.status_label.setObjectName("MutedText")

        self.total_card = _ExpenseStatCard("本期经营开支")
        self.project_card = _ExpenseStatCard("项目级开支")
        self.store_card = _ExpenseStatCard("店铺级开支")
        self.order_card = _ExpenseStatCard("订单级开支")

        self.scope_buttons: dict[str, QPushButton] = {}
        self.expense_date_edit = QDateEdit()
        self.expense_date_edit.setCalendarPopup(True)
        self.expense_date_edit.setDisplayFormat("yyyy-MM-dd")
        self.expense_date_edit.setDate(QDate.currentDate())
        self.category_combo = QComboBox()
        self.category_combo.setEditable(True)
        self.category_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.category_combo.setToolTip("可直接输入分类，也可以点右侧下拉选择常用分类。")
        self.category_combo.addItems(list(_CATEGORY_OPTIONS))
        self.shop_combo = QComboBox()
        self.platform_combo = QComboBox()
        self.platform_combo.addItems(list(_PLATFORM_OPTIONS))
        self.platform_combo.setToolTip("订单级会先跟随关联订单自动带入，也可以手动修正。")
        self.order_combo = QComboBox()
        self.amount_edit = QLineEdit()
        self.amount_edit.setPlaceholderText("输入金额")
        self.remark_edit = QTextEdit()
        self.save_button = QPushButton("保存开支")
        self.clear_button = QPushButton("清空")
        self.clear_button.setObjectName("SecondaryActionButton")

        self.list_widget = QListWidget()
        self.list_widget.setObjectName("HistoryList")
        self.list_summary_label = QLabel("暂无开支记录")
        self.list_summary_label.setObjectName("MutedText")

        self.detail_title_label = QLabel("请选择一条开支记录")
        self.detail_title_label.setObjectName("HistoryDetailTitle")
        self.detail_scope_chip = _ExpenseSummaryChip("归属层级")
        self.detail_shop_chip = _ExpenseSummaryChip("关联店铺")
        self.detail_order_chip = _ExpenseSummaryChip("关联订单")
        self.detail_amount_chip = _ExpenseSummaryChip("金额")
        self.detail_category_value = self._build_detail_value()
        self.detail_platform_value = self._build_detail_value()
        self.detail_date_value = self._build_detail_value()
        self.detail_remark_value = self._build_detail_value(min_height=92)
        self.detail_effect_label = QLabel("—")
        self.detail_effect_label.setObjectName("MutedText")
        self.delete_button = QPushButton("删除开支")
        self.delete_button.setObjectName("DangerActionButton")
        self.delete_button.setEnabled(False)

        self._build_ui()
        self._connect_signals()
        self._set_scope("订单级")
        self._refresh_filter_options()
        self._apply_filters()

    def set_shop_names(self, shop_names: list[str]) -> None:
        self._shop_names = [str(name).strip() for name in shop_names if str(name).strip()]
        current_form_shop = self.shop_combo.currentText().strip()
        current_filter_shop = self.shop_filter_combo.currentText().strip()

        self.shop_combo.blockSignals(True)
        self.shop_combo.clear()
        self.shop_combo.addItems(self._shop_names)
        if current_form_shop:
            index = self.shop_combo.findText(current_form_shop)
            if index >= 0:
                self.shop_combo.setCurrentIndex(index)
        self.shop_combo.blockSignals(False)

        self.shop_filter_combo.blockSignals(True)
        self.shop_filter_combo.clear()
        self.shop_filter_combo.addItem("全部店铺")
        self.shop_filter_combo.addItems(self._shop_names)
        if current_filter_shop:
            index = self.shop_filter_combo.findText(current_filter_shop)
            self.shop_filter_combo.setCurrentIndex(index if index >= 0 else 0)
        self.shop_filter_combo.blockSignals(False)

    def set_order_rows(self, rows: list[dict[str, Any]]) -> None:
        self._history_rows = list(rows)
        self._refresh_order_options()

    def load_rows(self, rows: list[dict[str, Any]], selected_record_id: str = "") -> None:
        self._rows = sorted(
            [self._normalize_row(row) for row in rows],
            key=lambda item: (
                item["expense_date"],
                item["updated_at"],
                item["created_at"],
                item["record_id"],
            ),
            reverse=True,
        )
        self._selected_record_id = selected_record_id or self._selected_record_id
        self._refresh_filter_options()
        self._apply_filters()

    def prefill_from_history_row(self, row: dict[str, Any]) -> None:
        snapshot = row.get("order_snapshot") if isinstance(row.get("order_snapshot"), dict) else {}
        order_id = str(snapshot.get("order_id", "")).strip()
        self.list_widget.blockSignals(True)
        self.list_widget.clearSelection()
        self.list_widget.setCurrentRow(-1)
        self.list_widget.blockSignals(False)
        self._selected_record_id = ""
        self._clear_detail()
        self._set_scope("订单级")
        self.expense_date_edit.setDate(QDate.currentDate())
        self.category_combo.setCurrentIndex(-1)
        self.category_combo.setEditText("")
        self.amount_edit.clear()
        self.remark_edit.clear()
        self._refresh_order_options(order_id)
        self._handle_order_selection_changed()
        if order_id:
            self.set_status(f"已从历史订单带入：{order_id}")
        else:
            self.set_status("已从历史订单带入")

    def set_status(self, text: str) -> None:
        self.status_label.setText(str(text or "").strip())

    def _build_ui(self) -> None:
        action_bar = QFrame()
        action_bar.setObjectName("EntryActionBar")
        action_layout = QVBoxLayout(action_bar)
        action_layout.setContentsMargins(16, 14, 16, 14)
        action_layout.setSpacing(12)

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        title_box = QVBoxLayout()
        title_box.setContentsMargins(0, 0, 0, 0)
        title_box.setSpacing(2)
        title = QLabel("经营开支")
        title.setObjectName("HistoryDetailTitle")
        title_box.addWidget(title)
        title_box.addWidget(self.status_label)
        header_row.addLayout(title_box)
        header_row.addStretch(1)
        action_layout.addLayout(header_row)

        filter_row = QHBoxLayout()
        filter_row.setContentsMargins(0, 0, 0, 0)
        filter_row.setSpacing(10)
        filter_row.addWidget(self.search_edit, 2)
        filter_row.addWidget(self.month_filter_combo, 1)
        filter_row.addWidget(self.scope_filter_combo, 1)
        filter_row.addWidget(self.shop_filter_combo, 1)
        filter_row.addWidget(self.apply_filters_button)
        filter_row.addWidget(self.clear_filters_button)
        action_layout.addLayout(filter_row)

        stats_grid = QGridLayout()
        stats_grid.setContentsMargins(0, 0, 0, 0)
        stats_grid.setHorizontalSpacing(10)
        stats_grid.setVerticalSpacing(10)
        stats_grid.addWidget(self.total_card, 0, 0)
        stats_grid.addWidget(self.project_card, 0, 1)
        stats_grid.addWidget(self.store_card, 0, 2)
        stats_grid.addWidget(self.order_card, 0, 3)
        action_layout.addLayout(stats_grid)

        left_card = QFrame()
        left_card.setObjectName("HistoryDetailPane")
        left_layout = QVBoxLayout(left_card)
        left_layout.setContentsMargins(16, 16, 16, 16)
        left_layout.setSpacing(12)

        form_header = QHBoxLayout()
        form_header.setContentsMargins(0, 0, 0, 0)
        form_title = QLabel("开支录入")
        form_title.setObjectName("SectionTitle")
        form_header.addWidget(form_title)
        form_header.addStretch(1)
        form_header.addWidget(self.clear_button)
        left_layout.addLayout(form_header)

        scope_row = QHBoxLayout()
        scope_row.setContentsMargins(0, 0, 0, 0)
        scope_row.setSpacing(8)
        for scope in _SCOPE_TYPES:
            button = QPushButton(scope)
            button.clicked.connect(lambda _checked=False, value=scope: self._set_scope(value))
            self.scope_buttons[scope] = button
            scope_row.addWidget(button)
        scope_row.addStretch(1)
        left_layout.addLayout(scope_row)

        form_grid = QGridLayout()
        form_grid.setContentsMargins(0, 0, 0, 0)
        form_grid.setHorizontalSpacing(10)
        form_grid.setVerticalSpacing(8)
        self._add_form_field(form_grid, 0, 0, "开支日期", self.expense_date_edit)
        self._add_form_field(form_grid, 0, 1, "分类", self.category_combo)
        self._add_form_field(form_grid, 1, 0, "店铺", self.shop_combo)
        self._add_form_field(form_grid, 1, 1, "平台", self.platform_combo)
        self._add_form_field(form_grid, 2, 0, "关联订单", self.order_combo, span=2)
        self._add_form_field(form_grid, 3, 0, "金额", self.amount_edit)
        self._add_form_field(form_grid, 4, 0, "备注", self.remark_edit, span=2)
        left_layout.addLayout(form_grid)
        left_layout.addWidget(self.save_button, 0, Qt.AlignmentFlag.AlignRight)
        left_layout.addStretch(1)

        list_card = QFrame()
        list_card.setObjectName("HistoryListCard")
        list_layout = QVBoxLayout(list_card)
        list_layout.setContentsMargins(14, 14, 14, 14)
        list_layout.setSpacing(8)
        list_title = QLabel("最近开支")
        list_title.setObjectName("SectionTitle")
        list_layout.addWidget(list_title)
        list_layout.addWidget(self.list_summary_label)
        list_layout.addWidget(self.list_widget, 1)

        detail_card = QFrame()
        detail_card.setObjectName("HistoryDetailCard")
        detail_layout = QVBoxLayout(detail_card)
        detail_layout.setContentsMargins(14, 14, 14, 14)
        detail_layout.setSpacing(12)
        detail_header = QHBoxLayout()
        detail_header.setContentsMargins(0, 0, 0, 0)
        detail_header.addWidget(self.detail_title_label)
        detail_header.addStretch(1)
        detail_header.addWidget(self.delete_button)
        detail_layout.addLayout(detail_header)

        chip_row = QGridLayout()
        chip_row.setContentsMargins(0, 0, 0, 0)
        chip_row.setHorizontalSpacing(10)
        chip_row.setVerticalSpacing(10)
        chip_row.addWidget(self.detail_scope_chip, 0, 0)
        chip_row.addWidget(self.detail_shop_chip, 0, 1)
        chip_row.addWidget(self.detail_order_chip, 0, 2)
        chip_row.addWidget(self.detail_amount_chip, 0, 3)
        detail_layout.addLayout(chip_row)

        detail_grid = QGridLayout()
        detail_grid.setContentsMargins(0, 0, 0, 0)
        detail_grid.setHorizontalSpacing(10)
        detail_grid.setVerticalSpacing(8)
        self._add_form_field(detail_grid, 0, 0, "分类", self.detail_category_value)
        self._add_form_field(detail_grid, 0, 1, "平台", self.detail_platform_value)
        self._add_form_field(detail_grid, 1, 0, "开支日期", self.detail_date_value)
        detail_layout.addLayout(detail_grid)

        effect_title = QLabel("利润影响")
        effect_title.setObjectName("SectionTitle")
        detail_layout.addWidget(effect_title)
        detail_layout.addWidget(self.detail_effect_label)
        self._add_vertical_field(detail_layout, "备注", self.detail_remark_value)
        detail_layout.addStretch(1)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(14)
        right_layout.addWidget(list_card, 1)
        right_layout.addWidget(detail_card, 1)

        workspace = QWidget()
        workspace_layout = QHBoxLayout(workspace)
        workspace_layout.setContentsMargins(0, 0, 0, 0)
        workspace_layout.setSpacing(16)
        workspace_layout.addWidget(left_card, 0)
        workspace_layout.addWidget(right_panel, 1)

        content = QWidget()
        content.setObjectName("PageContent")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(16, 16, 16, 16)
        content_layout.setSpacing(14)
        content_layout.addWidget(action_bar)
        content_layout.addWidget(workspace, 1)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll_area.setWidget(content)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(scroll_area)

    def _connect_signals(self) -> None:
        self.apply_filters_button.clicked.connect(self._apply_filters)
        self.clear_filters_button.clicked.connect(self._clear_filters)
        self.list_widget.currentItemChanged.connect(self._handle_current_item_changed)
        self.order_combo.currentIndexChanged.connect(self._handle_order_selection_changed)
        self.save_button.clicked.connect(self._handle_save_clicked)
        self.clear_button.clicked.connect(self.clear_editor)
        self.delete_button.clicked.connect(self._handle_delete_clicked)

    def _add_form_field(
        self,
        layout: QGridLayout,
        row: int,
        column: int,
        label_text: str,
        widget: QWidget,
        *,
        span: int = 1,
    ) -> None:
        label = QLabel(label_text)
        label.setObjectName("OrderFieldLabel")
        wrapper = QVBoxLayout()
        wrapper.setContentsMargins(0, 0, 0, 0)
        wrapper.setSpacing(4)
        wrapper.addWidget(label)
        wrapper.addWidget(widget)
        layout.addLayout(wrapper, row, column, 1, span)

    def _add_vertical_field(self, layout: QVBoxLayout, label_text: str, widget: QWidget) -> None:
        label = QLabel(label_text)
        label.setObjectName("OrderFieldLabel")
        layout.addWidget(label)
        layout.addWidget(widget)

    def _build_detail_value(self, *, min_height: int = 36) -> QTextEdit:
        value = QTextEdit()
        value.setReadOnly(True)
        value.setMinimumHeight(min_height)
        return value

    def _set_scope(self, scope_type: str) -> None:
        self._current_scope = scope_type
        for scope, button in self.scope_buttons.items():
            button.setObjectName("" if scope == scope_type else "SecondaryActionButton")
            button.style().unpolish(button)
            button.style().polish(button)
            button.update()

        is_order = scope_type == "订单级"
        is_store = scope_type == "店铺级"
        is_project = scope_type == "项目级"

        self.order_combo.setEnabled(is_order)
        self.shop_combo.setEnabled(is_order or is_store)
        self.platform_combo.setEnabled(is_order or is_store)

        if is_project:
            self.shop_combo.setCurrentIndex(-1)
            self.platform_combo.setCurrentIndex(0)
            self.order_combo.setCurrentIndex(-1)
        elif is_store:
            self.order_combo.setCurrentIndex(-1)
        elif is_order:
            self._handle_order_selection_changed()

    def _refresh_filter_options(self) -> None:
        current_month = self.month_filter_combo.currentText().strip()
        months = sorted(
            {
                str(row.get("expense_date", "")).strip()[:7]
                for row in self._rows
                if str(row.get("expense_date", "")).strip()
            },
            reverse=True,
        )
        self.month_filter_combo.blockSignals(True)
        self.month_filter_combo.clear()
        self.month_filter_combo.addItem("全部月份")
        self.month_filter_combo.addItems(months)
        index = self.month_filter_combo.findText(current_month)
        self.month_filter_combo.setCurrentIndex(index if index >= 0 else 0)
        self.month_filter_combo.blockSignals(False)

        current_shop = self.shop_filter_combo.currentText().strip()
        self.shop_filter_combo.blockSignals(True)
        self.shop_filter_combo.clear()
        self.shop_filter_combo.addItem("全部店铺")
        self.shop_filter_combo.addItems(self._shop_names)
        index = self.shop_filter_combo.findText(current_shop)
        self.shop_filter_combo.setCurrentIndex(index if index >= 0 else 0)
        self.shop_filter_combo.blockSignals(False)

    def _apply_filters(self) -> None:
        keyword = self.search_edit.text().strip()
        month_key = self.month_filter_combo.currentText().strip()
        scope_filter = self.scope_filter_combo.currentText().strip()
        shop_filter = self.shop_filter_combo.currentText().strip()

        def _matches(row: dict[str, Any]) -> bool:
            haystack = " ".join(
                [
                    row["expense_date"],
                    row["scope_type"],
                    row["shop_name"],
                    row["order_id"],
                    row["platform"],
                    row["category"],
                    row["remark"],
                    row["amount"],
                ]
            )
            if keyword and keyword not in haystack:
                return False
            if month_key and month_key != "全部月份" and not row["expense_date"].startswith(month_key):
                return False
            if scope_filter and scope_filter != "全部层级" and row["scope_type"] != scope_filter:
                return False
            if shop_filter and shop_filter != "全部店铺" and row["shop_name"] != shop_filter:
                return False
            return True

        self._filtered_rows = [row for row in self._rows if _matches(row)]
        self._render_summary_cards()
        self._render_list()

    def _clear_filters(self) -> None:
        self.search_edit.clear()
        self.month_filter_combo.setCurrentIndex(0)
        self.scope_filter_combo.setCurrentIndex(0)
        self.shop_filter_combo.setCurrentIndex(0)
        self._apply_filters()

    def _render_summary_cards(self) -> None:
        totals = defaultdict(lambda: {"amount": parse_decimal("0"), "count": 0})
        for row in self._filtered_rows:
            amount = parse_decimal(row.get("amount"))
            totals["all"]["amount"] += amount
            totals["all"]["count"] += 1
            key = row["scope_type"]
            totals[key]["amount"] += amount
            totals[key]["count"] += 1

        self._set_stat_card(self.total_card, totals["all"]["amount"], totals["all"]["count"])
        self._set_stat_card(self.project_card, totals["项目级"]["amount"], totals["项目级"]["count"])
        self._set_stat_card(self.store_card, totals["店铺级"]["amount"], totals["店铺级"]["count"])
        self._set_stat_card(self.order_card, totals["订单级"]["amount"], totals["订单级"]["count"])

    def _set_stat_card(self, card: _ExpenseStatCard, amount, count: int) -> None:
        card.value_label.setText(f"¥{format_money(amount)}")
        card.meta_label.setText(f"{count} 笔")

    def _render_list(self) -> None:
        selected_id = self._selected_record_id
        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        for row in self._filtered_rows:
            amount_text = format_money(parse_decimal(row.get("amount")))
            subtitle_parts = [row["expense_date"], row["scope_type"]]
            if row["shop_name"]:
                subtitle_parts.append(row["shop_name"])
            if row["order_id"]:
                subtitle_parts.append(row["order_id"])
            subtitle = " · ".join(subtitle_parts)
            text = f"{row['category'] or '未分类'}  ¥{amount_text}\n{subtitle}"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, row["record_id"])
            self.list_widget.addItem(item)

        self.list_summary_label.setText(f"共 {len(self._filtered_rows)} 条开支记录")
        self.list_widget.blockSignals(False)

        if self.list_widget.count() == 0:
            self._selected_record_id = ""
            self._clear_detail()
            return

        target_row = 0
        if selected_id:
            for index in range(self.list_widget.count()):
                if self.list_widget.item(index).data(Qt.ItemDataRole.UserRole) == selected_id:
                    target_row = index
                    break
        self.list_widget.setCurrentRow(target_row)

    def _handle_current_item_changed(self, current: QListWidgetItem | None, _previous: QListWidgetItem | None) -> None:
        if current is None:
            self._selected_record_id = ""
            self._clear_detail()
            return
        record_id = str(current.data(Qt.ItemDataRole.UserRole) or "").strip()
        self._selected_record_id = record_id
        row = next((item for item in self._filtered_rows if item["record_id"] == record_id), None)
        if row is None:
            self._clear_detail()
            return
        self._load_row_into_editor(row)
        self._render_detail(row)

    def _render_detail(self, row: dict[str, Any]) -> None:
        self.detail_title_label.setText(row["category"] or "经营开支")
        self.detail_scope_chip.value_label.setText(row["scope_type"] or "—")
        self.detail_shop_chip.value_label.setText(row["shop_name"] or "—")
        self.detail_order_chip.value_label.setText(row["order_id"] or "—")
        self.detail_amount_chip.value_label.setText(f"¥{format_money(parse_decimal(row['amount']))}")
        self.detail_category_value.setPlainText(row["category"] or "—")
        self.detail_platform_value.setPlainText(row["platform"] or "—")
        self.detail_date_value.setPlainText(row["expense_date"] or "—")
        self.detail_remark_value.setPlainText(row["remark"] or "—")
        self.detail_effect_label.setText(self._profit_scope_text(row["scope_type"]))
        self.delete_button.setEnabled(True)

    def _clear_detail(self) -> None:
        self.detail_title_label.setText("请选择一条开支记录")
        for chip in (
            self.detail_scope_chip,
            self.detail_shop_chip,
            self.detail_order_chip,
            self.detail_amount_chip,
        ):
            chip.value_label.setText("—")
        self.detail_category_value.setPlainText("")
        self.detail_platform_value.setPlainText("")
        self.detail_date_value.setPlainText("")
        self.detail_remark_value.setPlainText("")
        self.detail_effect_label.setText("—")
        self.delete_button.setEnabled(False)

    def _refresh_order_options(self, current_order_id: str = "") -> None:
        current_order_id = current_order_id or self._current_order_id()
        self.order_combo.blockSignals(True)
        self.order_combo.clear()
        seen: set[str] = set()
        for row in self._history_rows:
            snapshot = row.get("order_snapshot") if isinstance(row.get("order_snapshot"), dict) else {}
            order_id = str(snapshot.get("order_id", "")).strip()
            if not order_id or order_id in seen:
                continue
            seen.add(order_id)
            shop_name = str(row.get("shop_name", "")).strip()
            recipient = str(snapshot.get("recipient_name", "")).strip()
            status = str(snapshot.get("order_status", "")).strip()
            label = " · ".join(part for part in (order_id, recipient, shop_name, status) if part)
            self.order_combo.addItem(
                label,
                {
                    "order_id": order_id,
                    "shop_name": shop_name,
                    "platform": str(snapshot.get("platform", "抖店")).strip() or "抖店",
                },
            )
        if current_order_id:
            matched = False
            for index in range(self.order_combo.count()):
                data = self.order_combo.itemData(index)
                if isinstance(data, dict) and data.get("order_id") == current_order_id:
                    matched = True
                    break
            if not matched:
                self.order_combo.insertItem(
                    0,
                    f"{current_order_id} · 历史中未找到",
                    {"order_id": current_order_id, "shop_name": "", "platform": ""},
                )
        if current_order_id:
            for index in range(self.order_combo.count()):
                data = self.order_combo.itemData(index)
                if isinstance(data, dict) and data.get("order_id") == current_order_id:
                    self.order_combo.setCurrentIndex(index)
                    break
        self.order_combo.blockSignals(False)

    def _handle_order_selection_changed(self, _index: int = -1) -> None:
        if self._current_scope != "订单级":
            return
        data = self.order_combo.currentData()
        if not isinstance(data, dict):
            return
        shop_name = str(data.get("shop_name", "")).strip()
        platform = str(data.get("platform", "")).strip()
        if shop_name:
            index = self.shop_combo.findText(shop_name)
            if index < 0:
                self.shop_combo.addItem(shop_name)
                index = self.shop_combo.findText(shop_name)
            self.shop_combo.setCurrentIndex(index)
        if platform:
            index = self.platform_combo.findText(platform)
            if index < 0:
                self.platform_combo.addItem(platform)
                index = self.platform_combo.findText(platform)
            self.platform_combo.setCurrentIndex(index)

    def _load_row_into_editor(self, row: dict[str, Any]) -> None:
        self._selected_record_id = row["record_id"]
        self._set_scope(row["scope_type"] or "订单级")
        parsed_date = QDate.fromString(row["expense_date"], "yyyy-MM-dd")
        self.expense_date_edit.setDate(parsed_date if parsed_date.isValid() else QDate.currentDate())
        category = row["category"] or ""
        index = self.category_combo.findText(category)
        if index >= 0:
            self.category_combo.setCurrentIndex(index)
        else:
            self.category_combo.setEditText(category)
        shop_name = row["shop_name"] or ""
        shop_index = self.shop_combo.findText(shop_name)
        if shop_index >= 0:
            self.shop_combo.setCurrentIndex(shop_index)
        elif self.shop_combo.count():
            self.shop_combo.setCurrentIndex(0)
        platform = row["platform"] or ""
        platform_index = self.platform_combo.findText(platform)
        self.platform_combo.setCurrentIndex(platform_index if platform_index >= 0 else 0)
        self._refresh_order_options(row["order_id"])
        self.amount_edit.setText(row["amount"])
        self.remark_edit.setPlainText(row["remark"])

    def _handle_save_clicked(self) -> None:
        payload = self._build_payload()
        if payload is None:
            return
        self.save_requested.emit(self._selected_record_id, payload)

    def _handle_delete_clicked(self) -> None:
        if not self._selected_record_id:
            return
        self.delete_requested.emit(self._selected_record_id)

    def _build_payload(self) -> dict[str, str] | None:
        category = self.category_combo.currentText().strip()
        if not category:
            QMessageBox.warning(self, "缺少分类", "请先填写开支分类。")
            return None
        amount_raw = self.amount_edit.text().strip()
        if not amount_raw or parse_decimal(amount_raw) == parse_decimal("0"):
            QMessageBox.warning(self, "缺少金额", "请先填写正确的开支金额。")
            return None

        payload = {
            "expense_date": self.expense_date_edit.date().toString("yyyy-MM-dd"),
            "scope_type": self._current_scope,
            "shop_name": "",
            "order_id": "",
            "platform": "",
            "category": category,
            "amount": amount_raw,
            "remark": self.remark_edit.toPlainText().strip(),
        }

        if self._current_scope == "店铺级":
            shop_name = self.shop_combo.currentText().strip()
            if not shop_name:
                QMessageBox.warning(self, "缺少店铺", "店铺级开支需要选择店铺。")
                return None
            payload["shop_name"] = shop_name
            payload["platform"] = self.platform_combo.currentText().strip()
        elif self._current_scope == "订单级":
            data = self.order_combo.currentData()
            order_id = ""
            if isinstance(data, dict):
                order_id = str(data.get("order_id", "")).strip()
                payload["shop_name"] = self.shop_combo.currentText().strip() or str(data.get("shop_name", "")).strip()
                payload["platform"] = self.platform_combo.currentText().strip() or str(data.get("platform", "")).strip()
            if not order_id:
                QMessageBox.warning(self, "缺少关联订单", "订单级开支需要先选择关联订单。")
                return None
            payload["order_id"] = order_id
        return payload

    def _current_order_id(self) -> str:
        data = self.order_combo.currentData()
        if isinstance(data, dict):
            return str(data.get("order_id", "")).strip()
        return ""

    def _normalize_row(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "record_id": str(row.get("record_id", "")).strip(),
            "expense_date": str(row.get("expense_date", "")).strip(),
            "scope_type": str(row.get("scope_type", "")).strip(),
            "shop_name": str(row.get("shop_name", "")).strip(),
            "order_id": str(row.get("order_id", "")).strip(),
            "platform": str(row.get("platform", "")).strip(),
            "category": str(row.get("category", "")).strip(),
            "amount": str(row.get("amount", "")).strip(),
            "remark": str(row.get("remark", "")).strip(),
            "created_at": str(row.get("created_at", "")).strip(),
            "updated_at": str(row.get("updated_at", "")).strip(),
        }

    def clear_editor(self) -> None:
        self._selected_record_id = ""
        self._set_scope("订单级")
        self.expense_date_edit.setDate(QDate.currentDate())
        self.category_combo.setCurrentIndex(-1)
        self.category_combo.setEditText("")
        self.shop_combo.setCurrentIndex(0 if self.shop_combo.count() else -1)
        self.platform_combo.setCurrentIndex(0)
        self.order_combo.setCurrentIndex(0 if self.order_combo.count() else -1)
        self.amount_edit.clear()
        self.remark_edit.clear()
        self._clear_detail()

    def _profit_scope_text(self, scope_type: str) -> str:
        if scope_type == "订单级":
            return "会直接冲减对应订单毛利润，同时进入店铺与总盘支出。"
        if scope_type == "店铺级":
            return "会进入对应店铺经营开支，并影响店铺经营利润与总盘利润。"
        if scope_type == "项目级":
            return "只进入总盘经营开支，不分摊到具体店铺或订单。"
        return "—"
