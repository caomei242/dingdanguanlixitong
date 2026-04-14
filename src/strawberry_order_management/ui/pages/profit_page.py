from __future__ import annotations

from typing import Any

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from strawberry_order_management.profit import (
    build_daily_profit_sections,
    build_profit_overview,
    list_available_months,
)

_ORDER_STATUS_OPTIONS = ("全部状态", "已发货", "待发货", "已拍单未发货")
_PLATFORM_OPTIONS = ("全部平台", "抖店", "微信小店")


class _IncomeTrendChart(QFrame):
    def __init__(self) -> None:
        super().__init__()
        self.series_points: list[dict[str, Any]] = []
        self._plot_points: list[tuple[QPointF, dict[str, Any]]] = []
        self._hovered_index: int | None = None
        self._chart_rect = QRectF()
        self.setMinimumHeight(230)
        self.setMouseTracking(True)

    def set_points(self, points: list[dict[str, Any]]) -> None:
        self.series_points = list(points)
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QColor("#ffffff"))
        self._plot_points = []

        chart_rect = self.rect().adjusted(54, 18, -18, -34)
        self._chart_rect = QRectF(chart_rect)
        if chart_rect.width() <= 0 or chart_rect.height() <= 0:
            return

        guide_pen = QPen(QColor("#e4ebfb"))
        guide_pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(guide_pen)
        for step in range(5):
            ratio = step / 4 if step else 0
            y = chart_rect.bottom() - (chart_rect.height() * ratio)
            painter.drawLine(chart_rect.left(), int(y), chart_rect.right(), int(y))

        points = self.series_points
        if not points:
            painter.setPen(QColor("#94a3c4"))
            painter.drawText(chart_rect, Qt.AlignmentFlag.AlignCenter, "暂无趋势数据")
            return

        max_value = max(float(item.get("value", 0.0)) for item in points)
        if max_value <= 0:
            max_value = 1.0

        axis_pen = QPen(QColor("#cbd6f0"))
        painter.setPen(axis_pen)
        painter.drawLine(chart_rect.left(), chart_rect.bottom(), chart_rect.right(), chart_rect.bottom())

        label_pen = QPen(QColor("#7d8cad"))
        painter.setPen(label_pen)
        for step in range(5):
            value = max_value * (step / 4 if step else 0)
            y = chart_rect.bottom() - (chart_rect.height() * (step / 4 if step else 0))
            painter.drawText(
                QRectF(0, y - 8, 46, 16),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                f"¥{value:.0f}",
            )

        if len(points) == 1:
            positions = [QPointF(chart_rect.center().x(), chart_rect.bottom())]
        else:
            positions = []
            step_width = chart_rect.width() / (len(points) - 1)
            for index, item in enumerate(points):
                value = float(item.get("value", 0.0))
                x = chart_rect.left() + (step_width * index)
                y = chart_rect.bottom() - ((value / max_value) * chart_rect.height())
                positions.append(QPointF(x, y))
        self._plot_points = list(zip(positions, points))

        path = QPainterPath()
        path.moveTo(positions[0])
        for point in positions[1:]:
            path.lineTo(point)

        if self._hovered_index is not None and 0 <= self._hovered_index < len(positions):
            hover_pen = QPen(QColor("#9db4ff"))
            hover_pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(hover_pen)
            hovered_point = positions[self._hovered_index]
            painter.drawLine(
                QPointF(hovered_point.x(), chart_rect.top()),
                QPointF(hovered_point.x(), chart_rect.bottom()),
            )

        line_pen = QPen(QColor("#4f7cff"), 2.2)
        painter.setPen(line_pen)
        painter.drawPath(path)

        point_pen = QPen(QColor("#4f7cff"))
        painter.setPen(point_pen)
        painter.setBrush(QColor("#ffffff"))
        for point in positions:
            painter.drawEllipse(point, 2.5, 2.5)

        painter.setPen(QColor("#7d8cad"))
        if len(points) >= 1:
            for index in sorted({0, len(points) // 2, len(points) - 1}):
                point = positions[index]
                label = str(points[index].get("label", ""))
                painter.drawText(
                    QRectF(point.x() - 24, chart_rect.bottom() + 8, 48, 16),
                    Qt.AlignmentFlag.AlignCenter,
                    label,
                )

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        nearest = self._nearest_point(event.position().toPoint().x(), event.position().toPoint().y())
        if nearest is None:
            if self._hovered_index is not None:
                self._hovered_index = None
                self.update()
            QToolTip.hideText()
            super().mouseMoveEvent(event)
            return
        point, payload, index = nearest
        if self._hovered_index != index:
            self._hovered_index = index
            self.update()
        QToolTip.showText(
            event.globalPosition().toPoint(),
            f"{payload.get('date', '')}\n{payload.get('amount', '--')}",
            self,
        )
        super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        if self._hovered_index is not None:
            self._hovered_index = None
            self.update()
        QToolTip.hideText()
        super().leaveEvent(event)

    def _nearest_point(self, x: int, y: int) -> tuple[QPointF, dict[str, Any], int] | None:
        if self._chart_rect.isNull() or not self._chart_rect.adjusted(-10, -8, 10, 8).contains(x, y):
            return None
        best: tuple[QPointF, dict[str, Any], int] | None = None
        best_distance = max(18.0, self._chart_rect.width() / max(len(self._plot_points) * 2, 2))
        for index, (point, payload) in enumerate(self._plot_points):
            distance = abs(point.x() - x)
            if distance <= best_distance:
                best = (point, payload, index)
                best_distance = distance
        return best


class _MetricCard(QFrame):
    def __init__(self, title: str, value: str = "--") -> None:
        super().__init__()
        self.setObjectName("ProfitMetricCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("HistoryStatTitle")
        self.value_label = QLabel(value)
        self.value_label.setObjectName("HistoryStatValue")
        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)


class _SummaryChip(QFrame):
    def __init__(self, title: str, value: str = "--") -> None:
        super().__init__()
        self.setObjectName("ProfitSummaryChip")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)
        title_label = QLabel(title)
        title_label.setObjectName("HistoryMiniSummaryTitle")
        self.value_label = QLabel(value)
        self.value_label.setObjectName("HistoryMiniSummaryValue")
        layout.addWidget(title_label)
        layout.addWidget(self.value_label)


class _DailyShopCard(QFrame):
    def __init__(self, shop_data: dict[str, Any]) -> None:
        super().__init__()
        self.setObjectName("ProfitDailyShopRow")
        self.summary_labels: dict[str, QLabel] = {}
        self.shop_name_label = QLabel(shop_data["shop_name"])
        self.shop_name_label.setObjectName("SectionTitle")
        self.toggle_button = QPushButton("展开明细")
        self.toggle_button.setObjectName("SecondaryActionButton")
        self.toggle_button.clicked.connect(self._toggle_details)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.addWidget(self.shop_name_label)
        header.addStretch(1)
        header.addWidget(self.toggle_button)

        metrics_grid = QGridLayout()
        metrics_grid.setContentsMargins(0, 0, 0, 0)
        metrics_grid.setHorizontalSpacing(10)
        metrics_grid.setVerticalSpacing(10)

        for index, (key, title) in enumerate(
            (
                ("income", "总收入"),
                ("expense", "总支出"),
                ("gross_profit", "毛利"),
                ("profit_rate", "利润率"),
            )
        ):
            chip = _SummaryChip(title, shop_data[key])
            self.summary_labels[key] = chip.value_label
            metrics_grid.addWidget(chip, 0, index)

        meta_label = QLabel(f"订单数：{shop_data['order_count']}")
        meta_label.setObjectName("MutedText")

        self.income_breakdown_label = QLabel(_format_breakdown_text("收入构成", shop_data["income_breakdown"]))
        self.income_breakdown_label.setWordWrap(True)
        self.expense_breakdown_label = QLabel(_format_breakdown_text("支出构成", shop_data["expense_breakdown"]))
        self.expense_breakdown_label.setWordWrap(True)

        self.details_container = QFrame()
        self.details_container.setObjectName("ProfitDailyDetailPanel")
        details_layout = QVBoxLayout(self.details_container)
        details_layout.setContentsMargins(12, 10, 12, 10)
        details_layout.setSpacing(8)
        details_layout.addWidget(self.income_breakdown_label)
        details_layout.addWidget(self.expense_breakdown_label)
        self.details_container.hide()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        layout.addLayout(header)
        layout.addWidget(meta_label)
        layout.addLayout(metrics_grid)
        layout.addWidget(self.details_container)

    def _toggle_details(self) -> None:
        visible = not self.details_container.isHidden()
        self.details_container.setHidden(visible)
        self.toggle_button.setText("展开明细" if visible else "收起明细")


class _DailyDayCard(QFrame):
    def __init__(self, section: dict[str, Any]) -> None:
        super().__init__()
        self.setObjectName("ProfitDailyDayCard")
        self.shop_cards: list[_DailyShopCard] = []
        self.date_label = QLabel(section["date"])
        self.date_label.setObjectName("HistoryDetailTitle")
        meta_label = QLabel(f"当日订单：{section['order_count']}")
        meta_label.setObjectName("HistoryDetailMeta")

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.addWidget(self.date_label)
        header.addStretch(1)
        header.addWidget(meta_label)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        layout.addLayout(header)
        for shop_data in section["shops"]:
            card = _DailyShopCard(shop_data)
            self.shop_cards.append(card)
            layout.addWidget(card)


class ProfitPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._rows: list[dict[str, Any]] = []
        self._shop_names: list[str] = []
        self.day_cards: list[_DailyDayCard] = []
        self.metric_value_labels: dict[str, QLabel] = {}
        self.daily_metric_value_labels: dict[str, QLabel] = {}

        self.tabs = QTabWidget()
        self.tabs.setObjectName("ProfitSegmentTabs")

        self.overview_month_combo = QComboBox()
        self.overview_trend_metric_combo = QComboBox()
        self.daily_month_combo = QComboBox()
        self.daily_shop_combo = QComboBox()
        self.daily_platform_combo = QComboBox()
        self.daily_status_combo = QComboBox()
        self.daily_platform_combo.addItems(list(_PLATFORM_OPTIONS))
        self.daily_status_combo.addItems(list(_ORDER_STATUS_OPTIONS))
        self.overview_trend_metric_combo.addItems(["收入", "毛利润", "支出"])

        self.comparison_labels = {
            "mom_gross_profit": QLabel("--"),
            "yoy_gross_profit": QLabel("--"),
        }
        for label in self.comparison_labels.values():
            label.setObjectName("HistoryMiniSummaryValue")
        self.expense_breakdown_label = QLabel("暂无数据")
        self.expense_breakdown_label.setWordWrap(True)
        self.expense_breakdown_label.setObjectName("MutedText")
        self.income_trend_chart = _IncomeTrendChart()
        self.trend_title_label = QLabel("收入趋势")
        self.trend_title_label.setObjectName("SectionTitle")
        self.trend_subtitle_label = QLabel("按当月每天收入绘制折线，方便快速判断波动。")
        self.trend_subtitle_label.setObjectName("MutedText")
        self.shop_rankings_label = QLabel("暂无数据")
        self.shop_rankings_label.setWordWrap(True)
        self.shop_rankings_label.setObjectName("MutedText")
        self.month_summary_heading = QLabel("月级别")
        self.month_summary_heading.setObjectName("SectionTitle")
        self.daily_summary_heading = QLabel("当日级别")
        self.daily_summary_heading.setObjectName("SectionTitle")
        self.daily_scope_label = QLabel("—")
        self.daily_scope_label.setObjectName("MutedText")
        self.status_count_labels = {
            "已发货": QLabel("0"),
            "待发货": QLabel("0"),
            "已拍单未发货": QLabel("0"),
        }
        for label in self.status_count_labels.values():
            label.setObjectName("HistoryMiniSummaryValue")

        overview_tab = self._build_overview_tab()
        daily_tab = self._build_daily_tab()
        self.tabs.addTab(overview_tab, "大盘")
        self.tabs.addTab(daily_tab, "每日账目明细")

        layout = QVBoxLayout(self)
        layout.addWidget(self.tabs)

        self.overview_month_combo.currentTextChanged.connect(self._handle_shared_month_changed)
        self.overview_trend_metric_combo.currentTextChanged.connect(self._render_overview)
        self.daily_month_combo.currentTextChanged.connect(self._handle_shared_month_changed)
        self.daily_shop_combo.currentTextChanged.connect(self._render_daily_tab)
        self.daily_platform_combo.currentTextChanged.connect(self._render_daily_tab)
        self.daily_status_combo.currentTextChanged.connect(self._render_daily_tab)

    def set_shop_names(self, shop_names: list[str]) -> None:
        self._shop_names = [name for name in shop_names if str(name).strip()]
        self._refresh()

    def load_rows(self, rows: list[dict[str, Any]]) -> None:
        self._rows = list(rows)
        self._refresh()

    def _build_overview_tab(self) -> QWidget:
        container = QWidget()
        container.setObjectName("ProfitDashboardTab")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        header_card = QFrame()
        header_card.setObjectName("ProfitOverviewHeader")
        header_layout = QHBoxLayout(header_card)
        header_layout.setContentsMargins(16, 14, 16, 14)
        header_layout.setSpacing(12)
        title_box = QVBoxLayout()
        title_box.setContentsMargins(0, 0, 0, 0)
        title_box.setSpacing(4)
        title = QLabel("利润大盘")
        title.setObjectName("SectionTitle")
        subtitle = QLabel("先看整体毛利、利润率、同比和环比，再判断本月经营状态。")
        subtitle.setObjectName("MutedText")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        month_box = QHBoxLayout()
        month_label = QLabel("月份")
        month_label.setObjectName("OrderFieldLabel")
        month_box.addWidget(month_label)
        month_box.addWidget(self.overview_month_combo)
        header_layout.addLayout(title_box, 1)
        header_layout.addLayout(month_box)

        metric_grid = QGridLayout()
        metric_grid.setContentsMargins(0, 0, 0, 0)
        metric_grid.setHorizontalSpacing(12)
        metric_grid.setVerticalSpacing(12)
        for index, (key, title) in enumerate(
            (
                ("gross_profit", "月毛利润"),
                ("profit_rate", "利润率"),
                ("income", "总收入"),
                ("expense", "总支出"),
                ("order_count", "订单数"),
                ("active_shops", "出单店铺"),
            )
        ):
            card = _MetricCard(title)
            self.metric_value_labels[key] = card.value_label
            metric_grid.addWidget(card, index // 3, index % 3)

        daily_metric_grid = QGridLayout()
        daily_metric_grid.setContentsMargins(0, 0, 0, 0)
        daily_metric_grid.setHorizontalSpacing(12)
        daily_metric_grid.setVerticalSpacing(12)
        for index, (key, title) in enumerate(
            (
                ("gross_profit", "当日毛利润"),
                ("profit_rate", "当日利润率"),
                ("income", "当日收入"),
                ("expense", "当日总支出"),
                ("order_count", "当日订单数"),
                ("active_shops", "当日出单店铺"),
            )
        ):
            card = _MetricCard(title)
            self.daily_metric_value_labels[key] = card.value_label
            daily_metric_grid.addWidget(card, index // 3, index % 3)

        comparison_card = QFrame()
        comparison_card.setObjectName("ProfitInsightCard")
        comparison_layout = QVBoxLayout(comparison_card)
        comparison_layout.setContentsMargins(14, 12, 14, 12)
        comparison_layout.setSpacing(10)
        comparison_title = QLabel("同比 / 环比")
        comparison_title.setObjectName("SectionTitle")
        comparison_layout.addWidget(comparison_title)
        for label_text, key in (("环比毛利", "mom_gross_profit"), ("同比毛利", "yoy_gross_profit")):
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            title_label = QLabel(label_text)
            title_label.setObjectName("OrderFieldLabel")
            row.addWidget(title_label)
            row.addStretch(1)
            row.addWidget(self.comparison_labels[key])
            comparison_layout.addLayout(row)

        expense_card = QFrame()
        expense_card.setObjectName("ProfitInsightCard")
        expense_layout = QVBoxLayout(expense_card)
        expense_layout.setContentsMargins(14, 12, 14, 12)
        expense_layout.setSpacing(10)
        expense_title = QLabel("支出构成")
        expense_title.setObjectName("SectionTitle")
        expense_layout.addWidget(expense_title)
        expense_layout.addWidget(self.expense_breakdown_label)

        ranking_card = QFrame()
        ranking_card.setObjectName("ProfitInsightCard")
        ranking_layout = QVBoxLayout(ranking_card)
        ranking_layout.setContentsMargins(14, 12, 14, 12)
        ranking_layout.setSpacing(10)
        ranking_title = QLabel("店铺利润排行")
        ranking_title.setObjectName("SectionTitle")
        ranking_layout.addWidget(ranking_title)
        ranking_layout.addWidget(self.shop_rankings_label)

        status_card = QFrame()
        status_card.setObjectName("ProfitInsightCard")
        status_layout = QVBoxLayout(status_card)
        status_layout.setContentsMargins(14, 12, 14, 12)
        status_layout.setSpacing(10)
        status_title = QLabel("订单状态")
        status_title.setObjectName("SectionTitle")
        status_layout.addWidget(status_title)
        for key, title in (("已发货", "已发货"), ("待发货", "待发货"), ("已拍单未发货", "已拍单未发货")):
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            label = QLabel(title)
            label.setObjectName("OrderFieldLabel")
            row.addWidget(label)
            row.addStretch(1)
            row.addWidget(self.status_count_labels[key])
            status_layout.addLayout(row)

        lower_grid = QGridLayout()
        lower_grid.setContentsMargins(0, 0, 0, 0)
        lower_grid.setHorizontalSpacing(12)
        lower_grid.setVerticalSpacing(12)
        lower_grid.addWidget(comparison_card, 0, 0)
        lower_grid.addWidget(expense_card, 0, 1)
        lower_grid.addWidget(ranking_card, 1, 0)
        lower_grid.addWidget(status_card, 1, 1)

        trend_card = QFrame()
        trend_card.setObjectName("ProfitTrendCard")
        trend_layout = QVBoxLayout(trend_card)
        trend_layout.setContentsMargins(14, 12, 14, 12)
        trend_layout.setSpacing(10)
        trend_header = QHBoxLayout()
        trend_header.setContentsMargins(0, 0, 0, 0)
        trend_header.addWidget(self.trend_title_label)
        trend_header.addStretch(1)
        trend_metric_label = QLabel("指标")
        trend_metric_label.setObjectName("OrderFieldLabel")
        trend_header.addWidget(trend_metric_label)
        trend_header.addWidget(self.overview_trend_metric_combo)
        trend_header.addWidget(self.trend_subtitle_label)
        trend_layout.addLayout(trend_header)
        trend_layout.addWidget(self.income_trend_chart)

        layout.addWidget(header_card)
        layout.addWidget(self.month_summary_heading)
        layout.addLayout(metric_grid)
        daily_header = QHBoxLayout()
        daily_header.setContentsMargins(0, 0, 0, 0)
        daily_header.addWidget(self.daily_summary_heading)
        daily_header.addStretch(1)
        daily_header.addWidget(self.daily_scope_label)
        layout.addLayout(daily_header)
        layout.addLayout(daily_metric_grid)
        layout.addWidget(trend_card)
        layout.addLayout(lower_grid)
        layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setObjectName("ProfitDashboardScroll")
        scroll.setWidgetResizable(True)
        scroll.setWidget(container)
        return scroll

    def _build_daily_tab(self) -> QWidget:
        container = QWidget()
        container.setObjectName("ProfitDailyTab")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        header_card = QFrame()
        header_card.setObjectName("ProfitDailyFilterCard")
        header_layout = QVBoxLayout(header_card)
        header_layout.setContentsMargins(16, 14, 16, 14)
        header_layout.setSpacing(10)
        title = QLabel("每日账目明细")
        title.setObjectName("SectionTitle")
        subtitle = QLabel("按日期查看每家店的收入、支出、毛利和利润率，点开后再看具体构成。")
        subtitle.setObjectName("MutedText")
        filter_row = QHBoxLayout()
        filter_row.setContentsMargins(0, 0, 0, 0)
        filter_row.setSpacing(10)
        for label_text, widget in (
            ("月份", self.daily_month_combo),
            ("店铺", self.daily_shop_combo),
            ("平台", self.daily_platform_combo),
            ("状态", self.daily_status_combo),
        ):
            block = QHBoxLayout()
            block.setContentsMargins(0, 0, 0, 0)
            label = QLabel(label_text)
            label.setObjectName("OrderFieldLabel")
            block.addWidget(label)
            block.addWidget(widget)
            filter_row.addLayout(block)
        filter_row.addStretch(1)
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        header_layout.addLayout(filter_row)

        self.daily_content = QFrame()
        self.daily_content.setObjectName("ProfitDailyRowsPanel")
        self.daily_content_layout = QVBoxLayout(self.daily_content)
        self.daily_content_layout.setContentsMargins(0, 0, 0, 0)
        self.daily_content_layout.setSpacing(14)

        scroll = QScrollArea()
        scroll.setObjectName("ProfitDailyScroll")
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.daily_content)

        layout.addWidget(header_card)
        layout.addWidget(scroll, 1)
        return container

    def _refresh(self) -> None:
        available_months = list_available_months(self._rows)
        current_month = self._current_month_key()
        if current_month not in available_months:
            current_month = available_months[0] if available_months else ""
        self._set_month_options(available_months, current_month)
        self._refresh_shop_options()
        self._render_overview()
        self._render_daily_tab()

    def _set_month_options(self, month_keys: list[str], current_month: str) -> None:
        for combo in (self.overview_month_combo, self.daily_month_combo):
            combo.blockSignals(True)
            combo.clear()
            combo.addItems(month_keys)
            if current_month:
                index = combo.findText(current_month)
                if index >= 0:
                    combo.setCurrentIndex(index)
            combo.blockSignals(False)

    def _current_month_key(self) -> str:
        month_key = self.overview_month_combo.currentText().strip()
        if month_key:
            return month_key
        month_key = self.daily_month_combo.currentText().strip()
        if month_key:
            return month_key
        available = list_available_months(self._rows)
        return available[0] if available else ""

    def _handle_shared_month_changed(self, month_key: str) -> None:
        if not month_key:
            return
        sender = self.sender()
        other = self.daily_month_combo if sender is self.overview_month_combo else self.overview_month_combo
        other.blockSignals(True)
        index = other.findText(month_key)
        if index >= 0:
            other.setCurrentIndex(index)
        other.blockSignals(False)
        self._render_overview()
        self._render_daily_tab()

    def _refresh_shop_options(self) -> None:
        current_shop = self.daily_shop_combo.currentText().strip()
        visible_shop_names = list(dict.fromkeys(
            [
                *self._shop_names,
                *[
                    str((row.get("shop_name") if isinstance(row, dict) else "") or "").strip()
                    for row in self._rows
                    if str((row.get("shop_name") if isinstance(row, dict) else "") or "").strip()
                ],
            ]
        ))
        self.daily_shop_combo.blockSignals(True)
        self.daily_shop_combo.clear()
        self.daily_shop_combo.addItem("全部店铺")
        self.daily_shop_combo.addItems(visible_shop_names)
        index = self.daily_shop_combo.findText(current_shop)
        self.daily_shop_combo.setCurrentIndex(index if index >= 0 else 0)
        self.daily_shop_combo.blockSignals(False)

    def _render_overview(self) -> None:
        overview = build_profit_overview(self._rows, self._shop_names, self._current_month_key())
        totals = overview["totals"]
        for key in ("gross_profit", "profit_rate", "income", "expense", "order_count", "active_shops"):
            self.metric_value_labels[key].setText(totals.get(key, "--"))
        daily_totals = overview.get("daily_totals", {})
        for key in ("gross_profit", "profit_rate", "income", "expense", "order_count", "active_shops"):
            self.daily_metric_value_labels[key].setText(daily_totals.get(key, "--"))
        self.daily_scope_label.setText(daily_totals.get("date_key", "") or "暂无当日数据")
        for key, label in self.comparison_labels.items():
            label.setText(overview["comparisons"].get(key, "--"))
        ranking_lines = []
        for index, item in enumerate(overview["shop_rankings"], start=1):
            if item["income"] == "0.00" and item["gross_profit"] == "0.00":
                continue
            ranking_lines.append(
                f"{index}. {item['shop_name']}  收入 {item['income']}  支出 {item['expense']}  毛利 {item['gross_profit']}  利润率 {item['profit_rate']}"
            )
        self.shop_rankings_label.setText("\n".join(ranking_lines) if ranking_lines else "暂无数据")
        expense_lines = [f"{item['label']}：{item['value']}" for item in overview["expense_breakdown"]]
        self.expense_breakdown_label.setText("\n".join(expense_lines) if expense_lines else "暂无数据")
        metric_key = self._current_trend_metric_key()
        trend_title_text = {
            "income": "收入趋势",
            "gross_profit": "毛利润趋势",
            "expense": "支出趋势",
        }.get(metric_key, "收入趋势")
        trend_subtitle_text = {
            "income": "按当月每天收入绘制折线，方便快速判断波动。",
            "gross_profit": "按当月每天毛利润绘制折线，方便快速观察利润起伏。",
            "expense": "按当月每天支出绘制折线，方便快速识别异常支出。",
        }.get(metric_key, "按当月每天收入绘制折线，方便快速判断波动。")
        self.trend_title_label.setText(trend_title_text)
        self.trend_subtitle_label.setText(trend_subtitle_text)
        self.income_trend_chart.set_points(overview.get("trend_series", {}).get(metric_key, []))
        for status, label in self.status_count_labels.items():
            label.setText(str(overview["status_counts"].get(status, 0)))

    def _current_trend_metric_key(self) -> str:
        text = self.overview_trend_metric_combo.currentText().strip()
        if text == "毛利润":
            return "gross_profit"
        if text == "支出":
            return "expense"
        return "income"

    def _render_daily_tab(self) -> None:
        while self.daily_content_layout.count():
            item = self.daily_content_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.day_cards = []

        shop_filter = self.daily_shop_combo.currentText().strip()
        if shop_filter == "全部店铺":
            shop_filter = ""
        sections = build_daily_profit_sections(
            self._rows,
            self._shop_names,
            month_key=self._current_month_key(),
            shop_filter=shop_filter,
            platform_filter=self.daily_platform_combo.currentText().strip(),
            status_filter=self.daily_status_combo.currentText().strip(),
        )
        if not sections:
            empty_card = QFrame()
            empty_card.setObjectName("ProfitInsightCard")
            empty_layout = QVBoxLayout(empty_card)
            empty_layout.setContentsMargins(16, 16, 16, 16)
            empty_label = QLabel("当前筛选下暂无账目明细")
            empty_label.setObjectName("MutedText")
            empty_layout.addWidget(empty_label)
            self.daily_content_layout.addWidget(empty_card)
            self.daily_content_layout.addStretch(1)
            return
        for section in sections:
            card = _DailyDayCard(section)
            self.day_cards.append(card)
            self.daily_content_layout.addWidget(card)
        self.daily_content_layout.addStretch(1)


def _format_breakdown_text(title: str, items: list[dict[str, Any]]) -> str:
    if not items:
        return f"{title}\n暂无数据"
    lines = [title]
    for item in items:
        order_suffix = f"（{item['order_id']}）" if item.get("order_id") else ""
        lines.append(f"{item['label']}：{item['value']}{order_suffix}")
    return "\n".join(lines)
