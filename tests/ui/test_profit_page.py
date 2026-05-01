from datetime import datetime as real_datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QScrollArea

import strawberry_order_management.profit as profit_module
from strawberry_order_management.ui.pages.profit_page import ProfitPage


def _row(
    *,
    record_id: str,
    shop_name: str,
    placed_at: str,
    income_amount: str,
    platform_fee_amount: str,
    procurement_total_cost: str,
    other_cost: str,
    gross_profit: str,
    order_status: str = "已发货",
    platform: str = "抖店",
):
    return {
        "record_id": record_id,
        "shop_name": shop_name,
        "status": "已写入飞书",
        "sync_source": "确认写入飞书",
        "order_snapshot": {
            "order_id": record_id,
            "placed_at": placed_at,
            "platform": platform,
            "order_status": order_status,
            "product_name": "测试商品",
            "income_amount": income_amount,
            "platform_fee_amount": platform_fee_amount,
            "procurement_total_cost": procurement_total_cost,
            "other_cost": other_cost,
            "gross_profit": gross_profit,
            "custom_cost_labels": ["", "", ""],
            "custom_cost_values": ["", "", ""],
            "recipient_name": "测试用户",
        },
    }


def _rows():
    return [
        _row(
            record_id="apr13-lebao",
            shop_name="乐宝零食店",
            placed_at="2026-04-13 09:00:00",
            income_amount="100.00",
            platform_fee_amount="6.00",
            procurement_total_cost="50.00",
            other_cost="4.00",
            gross_profit="40.00",
        ),
        _row(
            record_id="apr13-huanbao",
            shop_name="欢宝零食店",
            placed_at="2026-04-13 10:00:00",
            income_amount="80.00",
            platform_fee_amount="4.80",
            procurement_total_cost="40.00",
            other_cost="0.00",
            gross_profit="35.20",
        ),
    ]


def _expense_rows():
    return [
        {
            "record_id": "expense-feb",
            "expense_date": "2026-02-03",
            "scope_type": "店铺级",
            "shop_name": "乐宝零食店",
            "order_id": "",
            "platform": "",
            "category": "软件服务",
            "amount": "20.00",
            "remark": "二月店铺订阅",
        },
        {
            "record_id": "expense-may",
            "expense_date": "2026-05-01",
            "scope_type": "店铺级",
            "shop_name": "乐宝零食店",
            "order_id": "",
            "platform": "",
            "category": "软件服务",
            "amount": "30.00",
            "remark": "五月店铺订阅",
        },
    ]


def test_profit_page_renders_three_tabs_and_overview_metrics(qtbot, monkeypatch):
    class _FakeDateTime(real_datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 4, 16, 9, 0, 0)

    monkeypatch.setattr(profit_module, "datetime", _FakeDateTime)

    page = ProfitPage()
    qtbot.addWidget(page)
    page.set_shop_names(["乐宝零食店", "欢宝零食店", "灵宝零食店"])
    page.load_rows(_rows())

    assert page.tabs.count() == 3
    assert [page.tabs.tabText(index) for index in range(page.tabs.count())] == [
        "大盘",
        "每周经营",
        "每日账目明细",
    ]
    assert page.metric_value_labels["gross_profit"].text() == "75.20"
    assert page.metric_value_labels["profit_rate"].text() == "41.78%"
    assert page.metric_value_labels["income"].text() == "180.00"
    assert page.metric_value_labels["expense"].text() == "104.80"
    assert page.month_summary_heading.text() == "本月经营"
    assert page.month_scope_label.text() == "2026-04"
    assert page.daily_summary_heading.text() == "今日经营"
    assert page.daily_scope_label.text() == "2026-04-16"
    assert page.daily_metric_value_labels["gross_profit"].text() == "0.00"
    assert page.daily_metric_value_labels["income"].text() == "0.00"
    assert page.overview_trend_metric_combo.currentText() == "收入"
    assert page.trend_subtitle_label.text() == ""
    assert len(page.income_trend_chart.series_points) == 30
    assert page.income_trend_chart.series_points[12]["amount"] == "180.00"

    page.overview_trend_metric_combo.setCurrentText("支出")

    assert page.trend_title_label.text() == "支出趋势"
    assert page.trend_subtitle_label.text() == ""
    assert page.income_trend_chart.series_points[12]["amount"] == "104.80"


def test_profit_page_weekly_tab_renders_weekly_totals(qtbot, monkeypatch):
    class _FakeDateTime(real_datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 4, 16, 9, 0, 0)

    monkeypatch.setattr(profit_module, "datetime", _FakeDateTime)

    page = ProfitPage()
    qtbot.addWidget(page)
    page.set_shop_names(["乐宝零食店", "欢宝零食店", "灵宝零食店"])
    page.load_rows(_rows())

    assert page.weekly_summary_heading.text() == "本周经营"
    assert page.weekly_scope_label.text() == "2026-04-13 至 2026-04-19"
    assert page.weekly_metric_value_labels["gross_profit"].text() == "75.20"
    assert page.weekly_metric_value_labels["profit_rate"].text() == "41.78%"
    assert page.weekly_metric_value_labels["income"].text() == "180.00"
    assert page.weekly_metric_value_labels["expense"].text() == "104.80"
    assert page.weekly_metric_value_labels["order_count"].text() == "2"
    assert page.weekly_metric_value_labels["active_shops"].text() == "2"


def test_profit_page_daily_tab_renders_day_cards_and_expandable_details(qtbot, monkeypatch):
    class _FakeDateTime(real_datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 4, 16, 9, 0, 0)

    monkeypatch.setattr(profit_module, "datetime", _FakeDateTime)

    page = ProfitPage()
    qtbot.addWidget(page)
    page.set_shop_names(["乐宝零食店", "欢宝零食店"])
    page.load_rows(_rows())

    assert len(page.day_cards) == 2
    day_card = page.day_cards[0]
    assert day_card.date_label.text() == "2026-04-16"
    assert day_card.shop_cards[0].summary_labels["income"].text() == "0.00"
    assert day_card.shop_cards[0].summary_labels["profit_rate"].text() == "--"
    assert day_card.shop_cards[0].details_container.isHidden() is True

    qtbot.mouseClick(day_card.shop_cards[0].toggle_button, Qt.MouseButton.LeftButton)

    assert day_card.shop_cards[0].details_container.isHidden() is False
    assert day_card.shop_cards[0].income_breakdown_label.text() == "收入构成\n暂无数据"


def test_profit_page_daily_tab_renders_current_day_rows_when_data_exists(qtbot, monkeypatch):
    class _FakeDateTime(real_datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 4, 16, 9, 0, 0)

    monkeypatch.setattr(profit_module, "datetime", _FakeDateTime)

    page = ProfitPage()
    qtbot.addWidget(page)
    page.set_shop_names(["乐宝零食店"])
    page.load_rows(
        [
            _row(
                record_id="apr16-lebao",
                shop_name="乐宝零食店",
                placed_at="2026-04-16 08:30:00",
                income_amount="120.00",
                platform_fee_amount="7.20",
                procurement_total_cost="60.00",
                other_cost="2.80",
                gross_profit="50.00",
            )
        ]
    )

    page.tabs.setCurrentIndex(2)

    assert page.tabs.currentWidget().objectName() == "ProfitDailyTab"
    assert page.day_cards
    assert page.daily_content_layout.itemAt(0).widget().objectName() == "ProfitDailyDayCard"

    day_card = page.day_cards[0]
    shop_card = day_card.shop_cards[0]
    day_card_texts = [label.text() for label in day_card.findChildren(type(page.daily_scope_label))]

    assert day_card.date_label.text() == "2026-04-16"
    assert "当日订单：1" in day_card_texts
    assert shop_card.shop_name_label.text() == "乐宝零食店"
    assert "订单数：1" in day_card_texts
    assert shop_card.summary_labels["income"].text() == "120.00"
    assert shop_card.summary_labels["expense"].text() == "70.00"
    assert shop_card.summary_labels["gross_profit"].text() == "50.00"
    assert shop_card.summary_labels["profit_rate"].text() == "41.67%"
    assert shop_card.details_container.isHidden() is True

    qtbot.mouseClick(shop_card.toggle_button, Qt.MouseButton.LeftButton)

    assert shop_card.details_container.isHidden() is False
    assert shop_card.income_breakdown_label.text() == "收入构成\n订单收入：120.00（apr16-lebao）"
    assert shop_card.expense_breakdown_label.text() == "支出构成\n平台扣点金额：7.20\n采购总成本：60.00\n其他成本：2.80"


def test_profit_page_uses_dashboard_and_daily_workspace_shell(qtbot):
    page = ProfitPage()
    qtbot.addWidget(page)
    page.set_shop_names(["乐宝零食店", "欢宝零食店"])
    page.load_rows(_rows())

    assert page.tabs.objectName() == "ProfitSegmentTabs"
    assert page.tabs.count() == 3
    assert [page.tabs.tabText(index) for index in range(page.tabs.count())] == [
        "大盘",
        "每周经营",
        "每日账目明细",
    ]
    assert page.findChild(QScrollArea, "ProfitDashboardScroll") is not None
    assert page.findChild(QScrollArea, "ProfitWeeklyScroll") is not None
    assert page.findChild(QScrollArea, "ProfitDailyScroll") is not None
    assert page.findChild(QFrame, "ProfitOverviewHeader") is not None
    assert page.findChild(QFrame, "ProfitWeeklyHeader") is not None
    assert page.findChild(QFrame, "ProfitTrendCard") is not None
    assert page.findChild(QFrame, "ProfitTrendCanvas") is page.income_trend_chart
    assert page.findChild(QFrame, "ProfitDailyFilterCard") is not None
    assert page.findChild(QFrame, "ProfitDailyRowsPanel") is not None
    assert page.day_cards[0].objectName() == "ProfitDailyDayCard"
    assert page.day_cards[0].shop_cards[0].objectName() == "ProfitDailyShopRow"
    assert "已完成售后" in [
        page.daily_status_combo.itemText(index)
        for index in range(page.daily_status_combo.count())
    ]


def test_profit_page_hides_helper_copy(qtbot):
    page = ProfitPage()
    qtbot.addWidget(page)

    texts = [label.text() for label in page.findChildren(type(page.trend_title_label))]

    assert "先看整体毛利、利润率、同比和环比，再判断本月经营状态。" not in texts
    assert "按日期查看每家店的收入、支出、毛利和利润率，点开后再看具体构成。" not in texts


def test_profit_page_defaults_to_current_month_and_merges_expense_only_months(qtbot, monkeypatch):
    class _FakeDateTime(real_datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 5, 1, 9, 0, 0)

    monkeypatch.setattr(profit_module, "datetime", _FakeDateTime)

    page = ProfitPage()
    qtbot.addWidget(page)
    page.set_shop_names(["乐宝零食店", "欢宝零食店"])
    page.load_rows(_rows())
    page.load_expense_rows(_expense_rows())

    overview_months = [
        page.overview_month_combo.itemText(index)
        for index in range(page.overview_month_combo.count())
    ]
    daily_months = [
        page.daily_month_combo.itemText(index)
        for index in range(page.daily_month_combo.count())
    ]

    assert overview_months == ["2026-05", "2026-04", "2026-02"]
    assert daily_months == overview_months
    assert page.overview_month_combo.currentText() == "2026-05"
    assert page.daily_month_combo.currentText() == "2026-05"
    assert page.month_scope_label.text() == "2026-05"
    assert page.metric_value_labels["expense"].text() == "30.00"


def test_profit_page_keeps_manual_month_selection_after_refresh(qtbot, monkeypatch):
    class _FakeDateTime(real_datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 5, 1, 9, 0, 0)

    monkeypatch.setattr(profit_module, "datetime", _FakeDateTime)

    page = ProfitPage()
    qtbot.addWidget(page)
    page.set_shop_names(["乐宝零食店", "欢宝零食店"])
    page.load_rows(_rows())
    page.load_expense_rows(_expense_rows())

    page.overview_month_combo.setCurrentText("2026-04")

    assert page.daily_month_combo.currentText() == "2026-04"
    assert page.month_scope_label.text() == "2026-04"

    page.load_expense_rows(_expense_rows())

    assert page.overview_month_combo.currentText() == "2026-04"
    assert page.daily_month_combo.currentText() == "2026-04"
    assert page.month_scope_label.text() == "2026-04"
