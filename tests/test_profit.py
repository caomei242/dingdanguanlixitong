from __future__ import annotations

from datetime import datetime as real_datetime

import strawberry_order_management.profit as profit_module
from strawberry_order_management.profit import (
    build_daily_profit_sections,
    build_profit_overview,
    list_available_months,
)


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
    order_id: str | None = None,
):
    return {
        "record_id": record_id,
        "shop_name": shop_name,
        "status": "已写入飞书",
        "sync_source": "确认写入飞书",
        "order_snapshot": {
            "order_id": order_id or record_id,
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
            record_id="apr12-lebao",
            shop_name="乐宝零食店",
            placed_at="2026-04-12 09:00:00",
            income_amount="50.00",
            platform_fee_amount="3.00",
            procurement_total_cost="30.00",
            other_cost="2.00",
            gross_profit="15.00",
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
        _row(
            record_id="mar05-lebao",
            shop_name="乐宝零食店",
            placed_at="2026-03-05 12:00:00",
            income_amount="90.00",
            platform_fee_amount="5.40",
            procurement_total_cost="35.00",
            other_cost="4.50",
            gross_profit="45.10",
        ),
        _row(
            record_id="apr2025-lebao",
            shop_name="乐宝零食店",
            placed_at="2025-04-05 12:00:00",
            income_amount="70.00",
            platform_fee_amount="4.20",
            procurement_total_cost="20.00",
            other_cost="0.70",
            gross_profit="45.10",
        ),
    ]


def _expense_rows():
    return [
        {
            "record_id": "expense-order-1",
            "expense_date": "2026-04-13",
            "scope_type": "订单级",
            "shop_name": "乐宝零食店",
            "order_id": "apr13-lebao",
            "platform": "抖店",
            "category": "售后补偿",
            "amount": "10.00",
            "remark": "售后返现 10 元",
        },
        {
            "record_id": "expense-shop-1",
            "expense_date": "2026-04-13",
            "scope_type": "店铺级",
            "shop_name": "乐宝零食店",
            "order_id": "",
            "platform": "",
            "category": "软件服务",
            "amount": "99.00",
            "remark": "自动发货软件月费",
        },
        {
            "record_id": "expense-project-1",
            "expense_date": "2026-04-13",
            "scope_type": "项目级",
            "shop_name": "",
            "order_id": "",
            "platform": "",
            "category": "设备采购",
            "amount": "200.00",
            "remark": "运营办公电脑",
        },
    ]


def test_list_available_months_descending():
    assert list_available_months(_rows()) == ["2026-04", "2026-03", "2025-04"]


def test_build_profit_overview_aggregates_totals_rankings_and_comparisons():
    overview = build_profit_overview(
        _rows(),
        ["乐宝零食店", "欢宝零食店", "灵宝零食店"],
        month_key="2026-04",
    )

    assert overview["month_key"] == "2026-04"
    assert overview["totals"] == {
        "income": "230.00",
        "expense": "139.80",
        "gross_profit": "90.20",
        "profit_rate": "39.22%",
        "order_count": "3",
        "active_shops": "2",
    }
    assert overview["comparisons"] == {
        "mom_gross_profit": "100.00%",
        "yoy_gross_profit": "100.00%",
    }
    assert overview["shop_rankings"][0] == {
        "shop_name": "乐宝零食店",
        "income": "150.00",
        "expense": "95.00",
        "gross_profit": "55.00",
        "profit_rate": "36.67%",
    }
    assert overview["shop_rankings"][1] == {
        "shop_name": "欢宝零食店",
        "income": "80.00",
        "expense": "44.80",
        "gross_profit": "35.20",
        "profit_rate": "44.00%",
    }
    assert overview["expense_breakdown"] == [
        {"label": "平台扣点金额", "value": "13.80"},
        {"label": "采购总成本", "value": "120.00"},
        {"label": "其他成本", "value": "6.00"},
    ]
    assert overview["status_counts"] == {
        "已发货": 3,
        "待发货": 0,
        "已拍单未发货": 0,
    }
    assert len(overview["trend_series"]["income"]) == 30
    assert overview["trend_series"]["income"][11] == {
        "date": "2026-04-12",
        "label": "04/12",
        "amount": "50.00",
        "value": 50.0,
    }
    assert overview["trend_series"]["income"][12] == {
        "date": "2026-04-13",
        "label": "04/13",
        "amount": "180.00",
        "value": 180.0,
    }
    assert overview["trend_series"]["expense"][12]["amount"] == "104.80"
    assert overview["trend_series"]["gross_profit"][12]["amount"] == "75.20"


def test_build_profit_overview_includes_order_store_and_project_expenses_in_correct_scope():
    overview = build_profit_overview(
        _rows(),
        ["乐宝零食店", "欢宝零食店", "灵宝零食店"],
        month_key="2026-04",
        expense_rows=_expense_rows(),
    )

    assert overview["totals"] == {
        "income": "230.00",
        "expense": "448.80",
        "gross_profit": "-218.80",
        "profit_rate": "-95.13%",
        "order_count": "3",
        "active_shops": "2",
    }
    assert overview["shop_rankings"][0] == {
        "shop_name": "欢宝零食店",
        "income": "80.00",
        "expense": "44.80",
        "gross_profit": "35.20",
        "profit_rate": "44.00%",
    }
    assert overview["shop_rankings"][1] == {
        "shop_name": "乐宝零食店",
        "income": "150.00",
        "expense": "204.00",
        "gross_profit": "-54.00",
        "profit_rate": "-36.00%",
    }
    assert overview["expense_breakdown"] == [
        {"label": "平台扣点金额", "value": "13.80"},
        {"label": "采购总成本", "value": "120.00"},
        {"label": "其他成本", "value": "6.00"},
        {"label": "订单额外开支", "value": "10.00"},
        {"label": "店铺经营开支", "value": "99.00"},
        {"label": "项目经营开支", "value": "200.00"},
    ]
    assert overview["trend_series"]["expense"][12]["amount"] == "413.80"
    assert overview["trend_series"]["gross_profit"][12]["amount"] == "-233.80"


def test_build_profit_overview_reduces_income_when_after_sale_refund_exists():
    rows = _rows()
    rows[0]["order_snapshot"]["after_sale_type"] = "退货退款"
    rows[0]["order_snapshot"]["after_sale_status"] = "已退款"
    rows[0]["order_snapshot"]["after_sale_amount"] = "10.00"

    overview = build_profit_overview(
        rows,
        ["乐宝零食店", "欢宝零食店", "灵宝零食店"],
        month_key="2026-04",
    )

    assert overview["totals"] == {
        "income": "220.00",
        "expense": "139.80",
        "gross_profit": "80.20",
        "profit_rate": "36.45%",
        "order_count": "3",
        "active_shops": "2",
    }
    assert overview["shop_rankings"][0] == {
        "shop_name": "乐宝零食店",
        "income": "140.00",
        "expense": "95.00",
        "gross_profit": "45.00",
        "profit_rate": "32.14%",
    }
    assert overview["trend_series"]["income"][12]["amount"] == "170.00"
    assert overview["trend_series"]["gross_profit"][12]["amount"] == "65.20"


def test_build_profit_overview_uses_today_with_zero_when_current_month_has_no_today_data(monkeypatch):
    class _FakeDateTime(real_datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 4, 16, 18, 0, 0)

    monkeypatch.setattr(profit_module, "datetime", _FakeDateTime)

    overview = build_profit_overview(
        _rows(),
        ["乐宝零食店", "欢宝零食店", "灵宝零食店"],
        month_key="2026-04",
    )

    assert overview["daily_totals"] == {
        "date_key": "2026-04-16",
        "income": "0.00",
        "expense": "0.00",
        "gross_profit": "0.00",
        "profit_rate": "--",
        "order_count": "0",
        "active_shops": "0",
    }


def test_build_daily_profit_sections_shows_each_day_and_each_shop():
    sections = build_daily_profit_sections(
        _rows(),
        ["乐宝零食店", "欢宝零食店", "灵宝零食店"],
        month_key="2026-04",
    )

    assert [section["date"] for section in sections] == ["2026-04-16", "2026-04-13", "2026-04-12"]
    assert sections[0]["order_count"] == 0
    assert sections[1]["order_count"] == 2
    assert sections[1]["shops"][0] == {
        "shop_name": "乐宝零食店",
        "order_count": 1,
        "income": "100.00",
        "expense": "60.00",
        "gross_profit": "40.00",
        "profit_rate": "40.00%",
        "income_breakdown": [
            {"label": "订单收入", "value": "100.00", "order_id": "apr13-lebao"}
        ],
        "expense_breakdown": [
            {"label": "平台扣点金额", "value": "6.00"},
            {"label": "采购总成本", "value": "50.00"},
            {"label": "其他成本", "value": "4.00"},
        ],
    }
    assert sections[1]["shops"][1]["shop_name"] == "欢宝零食店"
    assert sections[1]["shops"][1]["profit_rate"] == "44.00%"
    assert sections[2]["shops"][1] == {
        "shop_name": "欢宝零食店",
        "order_count": 0,
        "income": "0.00",
        "expense": "0.00",
        "gross_profit": "0.00",
        "profit_rate": "--",
        "income_breakdown": [],
        "expense_breakdown": [],
    }


def test_build_daily_profit_sections_includes_order_and_store_expenses_but_not_project_expense_in_shop_rows():
    sections = build_daily_profit_sections(
        _rows(),
        ["乐宝零食店", "欢宝零食店", "灵宝零食店"],
        month_key="2026-04",
        expense_rows=_expense_rows(),
    )

    assert sections[0]["project_expense_total"] == "0.00"
    assert sections[1]["project_expense_total"] == "200.00"
    assert sections[1]["shops"][0] == {
        "shop_name": "乐宝零食店",
        "order_count": 1,
        "income": "100.00",
        "expense": "169.00",
        "gross_profit": "-69.00",
        "profit_rate": "-69.00%",
        "income_breakdown": [
            {"label": "订单收入", "value": "100.00", "order_id": "apr13-lebao"}
        ],
        "expense_breakdown": [
            {"label": "平台扣点金额", "value": "6.00"},
            {"label": "采购总成本", "value": "50.00"},
            {"label": "其他成本", "value": "4.00"},
            {"label": "订单额外开支", "value": "10.00"},
            {"label": "店铺经营开支", "value": "99.00"},
        ],
    }


def test_build_daily_profit_sections_supports_filters():
    sections = build_daily_profit_sections(
        _rows(),
        ["乐宝零食店", "欢宝零食店"],
        month_key="2026-04",
        shop_filter="乐宝零食店",
        platform_filter="抖店",
        status_filter="已发货",
    )

    assert [section["date"] for section in sections] == ["2026-04-16", "2026-04-13", "2026-04-12"]
    assert [shop["shop_name"] for shop in sections[0]["shops"]] == ["乐宝零食店"]


def test_build_profit_overview_includes_shops_from_history_even_if_not_in_settings():
    overview = build_profit_overview(
        _rows(),
        ["乐宝零食店"],
        month_key="2026-04",
    )

    assert [item["shop_name"] for item in overview["shop_rankings"][:2]] == ["乐宝零食店", "欢宝零食店"]


def test_build_daily_profit_sections_includes_historical_shops_even_if_not_in_settings():
    sections = build_daily_profit_sections(
        _rows(),
        ["乐宝零食店"],
        month_key="2026-04",
    )

    assert [shop["shop_name"] for shop in sections[0]["shops"]] == ["乐宝零食店", "欢宝零食店"]


def test_build_daily_profit_sections_uses_today_with_zero_when_current_month_has_no_today_data(monkeypatch):
    class _FakeDateTime(real_datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 4, 16, 9, 0, 0)

    monkeypatch.setattr(profit_module, "datetime", _FakeDateTime)

    sections = build_daily_profit_sections(
        _rows(),
        ["乐宝零食店", "欢宝零食店"],
        month_key="2026-04",
    )

    assert [section["date"] for section in sections] == ["2026-04-16", "2026-04-13", "2026-04-12"]
    assert sections[0]["order_count"] == 0
    assert sections[0]["project_expense_total"] == "0.00"
    assert sections[0]["shops"][0] == {
        "shop_name": "乐宝零食店",
        "order_count": 0,
        "income": "0.00",
        "expense": "0.00",
        "gross_profit": "0.00",
        "profit_rate": "--",
        "income_breakdown": [],
        "expense_breakdown": [],
    }
    assert sections[0]["shops"][1] == {
        "shop_name": "欢宝零食店",
        "order_count": 0,
        "income": "0.00",
        "expense": "0.00",
        "gross_profit": "0.00",
        "profit_rate": "--",
        "income_breakdown": [],
        "expense_breakdown": [],
    }


def test_build_profit_overview_uses_placeholder_when_no_comparison_baseline():
    overview = build_profit_overview(
        [
            _row(
                record_id="feb-lebao",
                shop_name="乐宝零食店",
                placed_at="2026-02-05 12:00:00",
                income_amount="100.00",
                platform_fee_amount="10.00",
                procurement_total_cost="30.00",
                other_cost="5.00",
                gross_profit="55.00",
            )
        ],
        ["乐宝零食店"],
        month_key="2026-02",
    )

    assert overview["comparisons"] == {
        "mom_gross_profit": "--",
        "yoy_gross_profit": "--",
    }
