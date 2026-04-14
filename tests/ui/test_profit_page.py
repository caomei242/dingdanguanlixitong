from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QScrollArea

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


def test_profit_page_renders_two_tabs_and_overview_metrics(qtbot):
    page = ProfitPage()
    qtbot.addWidget(page)
    page.set_shop_names(["乐宝零食店", "欢宝零食店", "灵宝零食店"])
    page.load_rows(_rows())

    assert page.tabs.count() == 2
    assert [page.tabs.tabText(index) for index in range(page.tabs.count())] == [
        "大盘",
        "每日账目明细",
    ]
    assert page.metric_value_labels["gross_profit"].text() == "75.20"
    assert page.metric_value_labels["profit_rate"].text() == "41.78%"
    assert page.metric_value_labels["income"].text() == "180.00"
    assert page.metric_value_labels["expense"].text() == "104.80"
    assert page.month_summary_heading.text() == "月级别"
    assert page.daily_summary_heading.text() == "当日级别"
    assert page.daily_scope_label.text() == "2026-04-13"
    assert page.daily_metric_value_labels["gross_profit"].text() == "75.20"
    assert page.daily_metric_value_labels["income"].text() == "180.00"
    assert page.overview_trend_metric_combo.currentText() == "收入"
    assert len(page.income_trend_chart.series_points) == 30
    assert page.income_trend_chart.series_points[12]["amount"] == "180.00"

    page.overview_trend_metric_combo.setCurrentText("支出")

    assert page.trend_title_label.text() == "支出趋势"
    assert page.income_trend_chart.series_points[12]["amount"] == "104.80"


def test_profit_page_daily_tab_renders_day_cards_and_expandable_details(qtbot):
    page = ProfitPage()
    qtbot.addWidget(page)
    page.set_shop_names(["乐宝零食店", "欢宝零食店"])
    page.load_rows(_rows())

    assert len(page.day_cards) == 1
    day_card = page.day_cards[0]
    assert day_card.date_label.text() == "2026-04-13"
    assert day_card.shop_cards[0].summary_labels["income"].text() == "100.00"
    assert day_card.shop_cards[0].summary_labels["profit_rate"].text() == "40.00%"
    assert day_card.shop_cards[0].details_container.isHidden() is True

    qtbot.mouseClick(day_card.shop_cards[0].toggle_button, Qt.MouseButton.LeftButton)

    assert day_card.shop_cards[0].details_container.isHidden() is False
    assert "订单收入" in day_card.shop_cards[0].income_breakdown_label.text()


def test_profit_page_uses_dashboard_and_daily_workspace_shell(qtbot):
    page = ProfitPage()
    qtbot.addWidget(page)
    page.set_shop_names(["乐宝零食店", "欢宝零食店"])
    page.load_rows(_rows())

    assert page.tabs.objectName() == "ProfitSegmentTabs"
    assert page.findChild(QScrollArea, "ProfitDashboardScroll") is not None
    assert page.findChild(QScrollArea, "ProfitDailyScroll") is not None
    assert page.findChild(QFrame, "ProfitOverviewHeader") is not None
    assert page.findChild(QFrame, "ProfitTrendCard") is not None
    assert page.findChild(QFrame, "ProfitDailyFilterCard") is not None
    assert page.findChild(QFrame, "ProfitDailyRowsPanel") is not None
    assert page.day_cards[0].objectName() == "ProfitDailyDayCard"
    assert page.day_cards[0].shop_cards[0].objectName() == "ProfitDailyShopRow"
