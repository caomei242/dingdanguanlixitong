from __future__ import annotations

from calendar import monthrange
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from typing import Any

from strawberry_order_management.finance import format_money, parse_decimal

_FIXED_ORDER_STATUS_OPTIONS = ("已发货", "待发货", "已拍单未发货")
_ORDER_STATUS_ALIASES = {"未发货": "待发货", "已下单未发货": "已拍单未发货"}
_REFUND_AFTER_SALE_TYPES = {"仅退款", "退货退款", "部分退款"}
_REFUND_AFTER_SALE_STATUSES = {"已退款", "已退货"}


def list_available_months(rows: list[dict[str, Any]]) -> list[str]:
    month_keys = {
        parsed["month_key"]
        for parsed in (_parse_history_row(row) for row in rows)
        if parsed["month_key"]
    }
    return sorted(month_keys, reverse=True)


def build_profit_overview(
    rows: list[dict[str, Any]],
    shop_names: list[str],
    month_key: str | None = None,
    expense_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    normalized_rows = [_parse_history_row(row) for row in rows]
    normalized_expenses = [_parse_expense_row(row) for row in (expense_rows or [])]
    available_months = list_available_months(rows)
    selected_month = month_key or (available_months[0] if available_months else "")
    month_rows = [row for row in normalized_rows if row["month_key"] == selected_month]
    month_expenses = [row for row in normalized_expenses if row["month_key"] == selected_month]
    visible_shop_names = _resolve_visible_shop_names(shop_names, month_rows)

    income_total = sum((row["income"] for row in month_rows), Decimal("0"))
    expense_totals = _sum_expense_components(month_rows)
    extra_expense_totals = _sum_external_expense_components(month_expenses)
    expense_total = _expense_total_from_components(expense_totals) + _expense_total_from_components(extra_expense_totals)
    gross_profit_total = _sum_gross_profit(month_rows, income_total, expense_total)
    order_count = len(month_rows)
    active_shops = len({row["shop_name"] for row in month_rows if row["shop_name"]})
    daily_reference_key = _resolve_daily_reference_key(month_rows, selected_month)
    daily_rows = [row for row in month_rows if row["date_key"] == daily_reference_key]
    daily_expenses = [row for row in month_expenses if row["date_key"] == daily_reference_key]
    daily_income_total = sum((row["income"] for row in daily_rows), Decimal("0"))
    daily_expense_totals = _sum_expense_components(daily_rows)
    daily_extra_expense_totals = _sum_external_expense_components(daily_expenses)
    daily_expense_total = _expense_total_from_components(daily_expense_totals) + _expense_total_from_components(
        daily_extra_expense_totals
    )
    daily_gross_profit_total = _sum_gross_profit(daily_rows, daily_income_total, daily_expense_total)
    daily_order_count = len(daily_rows)
    daily_active_shops = len({row["shop_name"] for row in daily_rows if row["shop_name"]})

    previous_month_key = _shift_month_key(selected_month, -1)
    previous_year_key = _shift_year_key(selected_month, -1)
    previous_month_rows = [row for row in normalized_rows if row["month_key"] == previous_month_key]
    previous_year_rows = [row for row in normalized_rows if row["month_key"] == previous_year_key]
    previous_month_expenses = [row for row in normalized_expenses if row["month_key"] == previous_month_key]
    previous_year_expenses = [row for row in normalized_expenses if row["month_key"] == previous_year_key]

    previous_month_profit = _sum_gross_profit(
        previous_month_rows,
        sum((row["income"] for row in previous_month_rows), Decimal("0")),
        _expense_total_from_components(_sum_expense_components(previous_month_rows))
        + _expense_total_from_components(_sum_external_expense_components(previous_month_expenses)),
    )
    previous_year_profit = _sum_gross_profit(
        previous_year_rows,
        sum((row["income"] for row in previous_year_rows), Decimal("0")),
        _expense_total_from_components(_sum_expense_components(previous_year_rows))
        + _expense_total_from_components(_sum_external_expense_components(previous_year_expenses)),
    )

    rankings = []
    for shop_name in visible_shop_names:
        shop_rows = [row for row in month_rows if row["shop_name"] == shop_name]
        shop_expenses = _filter_shop_expenses(month_expenses, shop_name)
        if not shop_rows and not shop_expenses:
            continue
        shop_income = sum((row["income"] for row in shop_rows), Decimal("0"))
        shop_components = _sum_expense_components(shop_rows)
        shop_extra_expenses = _sum_external_expense_components(shop_expenses, include_project=False)
        shop_expense = _expense_total_from_components(shop_components) + _expense_total_from_components(shop_extra_expenses)
        shop_profit = _sum_gross_profit(shop_rows, shop_income, shop_expense)
        rankings.append(
            {
                "shop_name": shop_name,
                "income": format_money(shop_income),
                "expense": format_money(shop_expense),
                "gross_profit": format_money(shop_profit),
                "profit_rate": _format_profit_rate(shop_profit, shop_income),
            }
        )
    rankings.sort(key=lambda item: (parse_decimal(item["gross_profit"]), parse_decimal(item["income"])), reverse=True)

    expense_breakdown = [
        {"label": "平台扣点金额", "value": format_money(expense_totals["platform_fee_amount"])},
        {"label": "采购总成本", "value": format_money(expense_totals["procurement_total_cost"])},
        {"label": "其他成本", "value": format_money(expense_totals["other_cost"] + expense_totals["custom_cost"])},
    ]
    if extra_expense_totals["order_extra_expense"] != Decimal("0"):
        expense_breakdown.append({"label": "订单额外开支", "value": format_money(extra_expense_totals["order_extra_expense"])})
    if extra_expense_totals["store_operating_expense"] != Decimal("0"):
        expense_breakdown.append(
            {"label": "店铺经营开支", "value": format_money(extra_expense_totals["store_operating_expense"])}
        )
    if extra_expense_totals["project_operating_expense"] != Decimal("0"):
        expense_breakdown.append(
            {"label": "项目经营开支", "value": format_money(extra_expense_totals["project_operating_expense"])}
        )

    status_counts = {status: 0 for status in _FIXED_ORDER_STATUS_OPTIONS}
    for row in month_rows:
        status_counts[row["order_status"]] = status_counts.get(row["order_status"], 0) + 1

    return {
        "month_key": selected_month,
        "available_months": available_months,
        "totals": {
            "income": format_money(income_total),
            "expense": format_money(expense_total),
            "gross_profit": format_money(gross_profit_total),
            "profit_rate": _format_profit_rate(gross_profit_total, income_total),
            "order_count": str(order_count),
            "active_shops": str(active_shops),
        },
        "daily_totals": {
            "date_key": daily_reference_key,
            "income": format_money(daily_income_total),
            "expense": format_money(daily_expense_total),
            "gross_profit": format_money(daily_gross_profit_total),
            "profit_rate": _format_profit_rate(daily_gross_profit_total, daily_income_total),
            "order_count": str(daily_order_count),
            "active_shops": str(daily_active_shops),
        },
        "comparisons": {
            "mom_gross_profit": _format_change_percent(gross_profit_total, previous_month_profit),
            "yoy_gross_profit": _format_change_percent(gross_profit_total, previous_year_profit),
        },
        "trend_series": {
            "income": _build_daily_series(month_rows, month_expenses, selected_month, "income"),
            "expense": _build_daily_series(month_rows, month_expenses, selected_month, "expense"),
            "gross_profit": _build_daily_series(month_rows, month_expenses, selected_month, "gross_profit"),
        },
        "shop_rankings": rankings,
        "expense_breakdown": expense_breakdown,
        "status_counts": status_counts,
    }


def build_daily_profit_sections(
    rows: list[dict[str, Any]],
    shop_names: list[str],
    month_key: str | None = None,
    shop_filter: str = "",
    platform_filter: str = "",
    status_filter: str = "",
    expense_rows: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    normalized_rows = [_parse_history_row(row) for row in rows]
    normalized_expenses = [_parse_expense_row(row) for row in (expense_rows or [])]
    available_months = list_available_months(rows)
    selected_month = month_key or (available_months[0] if available_months else "")

    filtered_rows = [
        row
        for row in normalized_rows
        if row["month_key"] == selected_month
        and (not shop_filter or row["shop_name"] == shop_filter)
        and (not platform_filter or platform_filter == "全部平台" or row["platform"] == platform_filter)
        and (
            not status_filter
            or status_filter == "全部状态"
            or row["order_status"] == _normalize_status(status_filter)
        )
    ]
    filtered_expenses = [
        row
        for row in normalized_expenses
        if row["month_key"] == selected_month
        and (not shop_filter or row["shop_name"] in {"", shop_filter})
        and (not platform_filter or platform_filter == "全部平台" or not row["platform"] or row["platform"] == platform_filter)
    ]

    if shop_filter:
        shops_to_render = [shop_filter]
    else:
        shops_to_render = _resolve_visible_shop_names(shop_names, filtered_rows)

    daily_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in filtered_rows:
        daily_groups[row["date_key"]].append(row)

    sections = []
    section_dates = _resolve_daily_section_dates(filtered_rows, selected_month)
    for date_key in section_dates:
        day_rows = daily_groups[date_key]
        day_expenses = [row for row in filtered_expenses if row["date_key"] == date_key]
        shop_sections = []
        for shop_name in shops_to_render:
            shop_rows = [row for row in day_rows if row["shop_name"] == shop_name]
            shop_expenses = _filter_shop_expenses(day_expenses, shop_name)
            shop_income = sum((row["income"] for row in shop_rows), Decimal("0"))
            shop_components = _sum_expense_components(shop_rows)
            shop_extra_expenses = _sum_external_expense_components(shop_expenses, include_project=False)
            shop_expense = _expense_total_from_components(shop_components) + _expense_total_from_components(shop_extra_expenses)
            shop_profit = _sum_gross_profit(shop_rows, shop_income, shop_expense)
            income_breakdown = [
                {
                    "label": "订单收入",
                    "value": format_money(row["income"]),
                    "order_id": row["order_id"],
                }
                for row in shop_rows
            ]
            expense_breakdown = []
            if shop_components["platform_fee_amount"] != Decimal("0"):
                expense_breakdown.append(
                    {"label": "平台扣点金额", "value": format_money(shop_components["platform_fee_amount"])}
                )
            if shop_components["procurement_total_cost"] != Decimal("0"):
                expense_breakdown.append(
                    {"label": "采购总成本", "value": format_money(shop_components["procurement_total_cost"])}
                )
            if (shop_components["other_cost"] + shop_components["custom_cost"]) != Decimal("0"):
                expense_breakdown.append(
                    {
                        "label": "其他成本",
                        "value": format_money(shop_components["other_cost"] + shop_components["custom_cost"]),
                    }
                )
            if shop_extra_expenses["order_extra_expense"] != Decimal("0"):
                expense_breakdown.append(
                    {"label": "订单额外开支", "value": format_money(shop_extra_expenses["order_extra_expense"])}
                )
            if shop_extra_expenses["store_operating_expense"] != Decimal("0"):
                expense_breakdown.append(
                    {"label": "店铺经营开支", "value": format_money(shop_extra_expenses["store_operating_expense"])}
                )
            shop_sections.append(
                {
                    "shop_name": shop_name,
                    "order_count": len(shop_rows),
                    "income": format_money(shop_income),
                    "expense": format_money(shop_expense),
                    "gross_profit": format_money(shop_profit),
                    "profit_rate": _format_profit_rate(shop_profit, shop_income),
                    "income_breakdown": income_breakdown,
                    "expense_breakdown": expense_breakdown,
                }
            )

        sections.append(
            {
                "date": date_key,
                "order_count": len(day_rows),
                "project_expense_total": format_money(
                    _sum_external_expense_components(day_expenses)["project_operating_expense"]
                ),
                "shops": shop_sections,
            }
        )
    return sections


def _resolve_daily_section_dates(rows: list[dict[str, Any]], selected_month: str) -> list[str]:
    date_keys = {row["date_key"] for row in rows if row["date_key"]}
    if not selected_month:
        return sorted(date_keys, reverse=True)

    today_key = datetime.now().strftime("%Y-%m-%d")
    today_month = today_key[:7]
    if selected_month == today_month:
        date_keys.add(today_key)

    return sorted(date_keys, reverse=True)


def _parse_history_row(row: dict[str, Any]) -> dict[str, Any]:
    snapshot = row.get("order_snapshot") if isinstance(row.get("order_snapshot"), dict) else {}
    placed_at = str(snapshot.get("placed_at", "")).strip()
    dt = _parse_datetime(placed_at)
    custom_cost_values = snapshot.get("custom_cost_values") or []
    if not isinstance(custom_cost_values, (list, tuple)):
        custom_cost_values = []
    custom_cost_labels = snapshot.get("custom_cost_labels") or []
    if not isinstance(custom_cost_labels, (list, tuple)):
        custom_cost_labels = []
    income_amount = _resolve_effective_income(snapshot)
    return {
        "record_id": str(row.get("record_id", "")).strip(),
        "shop_name": str(row.get("shop_name", "")).strip(),
        "order_id": str(snapshot.get("order_id", "")).strip(),
        "platform": str(snapshot.get("platform", "")).strip() or "抖店",
        "order_status": _normalize_status(str(snapshot.get("order_status", "")).strip()),
        "income": income_amount,
        "platform_fee_amount": parse_decimal(snapshot.get("platform_fee_amount")),
        "procurement_total_cost": parse_decimal(snapshot.get("procurement_total_cost")),
        "other_cost": parse_decimal(snapshot.get("other_cost")),
        "gross_profit": parse_decimal(snapshot.get("gross_profit")),
        "custom_cost_labels": [str(value).strip() for value in custom_cost_labels],
        "custom_cost_values": [parse_decimal(value) for value in custom_cost_values],
        "month_key": dt.strftime("%Y-%m") if dt is not None else "",
        "date_key": dt.strftime("%Y-%m-%d") if dt is not None else "",
    }


def _resolve_effective_income(snapshot: dict[str, Any]) -> Decimal:
    base_income_value = str(snapshot.get("after_sale_base_income", "") or "").strip()
    if base_income_value:
        return parse_decimal(snapshot.get("income_amount"))
    income_amount = parse_decimal(snapshot.get("income_amount"))
    after_sale_type = str(snapshot.get("after_sale_type", "") or "").strip()
    after_sale_status = str(snapshot.get("after_sale_status", "") or "").strip()
    if (
        after_sale_type in _REFUND_AFTER_SALE_TYPES
        and after_sale_status in _REFUND_AFTER_SALE_STATUSES
    ):
        return max(income_amount - parse_decimal(snapshot.get("after_sale_amount")), Decimal("0"))
    return income_amount


def _parse_datetime(value: str) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("/", "-").strip()
    candidates = (normalized, normalized.replace("T", " "))
    for candidate in candidates:
        try:
            return datetime.fromisoformat(candidate)
        except ValueError:
            continue
    for pattern in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(normalized, pattern)
        except ValueError:
            continue
    return None


def _normalize_status(value: str) -> str:
    cleaned = str(value or "").strip()
    if not cleaned:
        return "待发货"
    return _ORDER_STATUS_ALIASES.get(cleaned, cleaned)


def _sum_expense_components(rows: list[dict[str, Any]]) -> dict[str, Decimal]:
    totals = {
        "platform_fee_amount": Decimal("0"),
        "procurement_total_cost": Decimal("0"),
        "other_cost": Decimal("0"),
        "custom_cost": Decimal("0"),
    }
    for row in rows:
        totals["platform_fee_amount"] += row["platform_fee_amount"]
        totals["procurement_total_cost"] += row["procurement_total_cost"]
        totals["other_cost"] += row["other_cost"]
        totals["custom_cost"] += sum(row["custom_cost_values"], Decimal("0"))
    return totals


def _sum_external_expense_components(
    rows: list[dict[str, Any]],
    *,
    include_project: bool = True,
) -> dict[str, Decimal]:
    totals = {
        "order_extra_expense": Decimal("0"),
        "store_operating_expense": Decimal("0"),
        "project_operating_expense": Decimal("0"),
    }
    for row in rows:
        amount = row["amount"]
        if row["scope_type"] == "订单级":
            totals["order_extra_expense"] += amount
        elif row["scope_type"] == "店铺级":
            totals["store_operating_expense"] += amount
        elif include_project and row["scope_type"] == "项目级":
            totals["project_operating_expense"] += amount
    return totals


def _expense_total_from_components(components: dict[str, Decimal]) -> Decimal:
    return sum(components.values(), Decimal("0"))


def _sum_gross_profit(rows: list[dict[str, Any]], income_total: Decimal, expense_total: Decimal) -> Decimal:
    if not rows:
        return Decimal("0")
    return income_total - expense_total


def _format_profit_rate(gross_profit: Decimal, income: Decimal) -> str:
    if income == Decimal("0"):
        return "--"
    percent = (gross_profit / income) * Decimal("100")
    return f"{format_money(percent)}%"


def _format_change_percent(current: Decimal, previous: Decimal) -> str:
    if previous == Decimal("0"):
        return "--"
    percent = ((current - previous) / previous) * Decimal("100")
    return f"{format_money(percent)}%"


def _resolve_visible_shop_names(shop_names: list[str], rows: list[dict[str, Any]]) -> list[str]:
    configured = [str(name).strip() for name in shop_names if str(name).strip()]
    historical = []
    for row in rows:
        shop_name = str(row.get("shop_name", "")).strip()
        if shop_name and shop_name not in historical and shop_name not in configured:
            historical.append(shop_name)
    return configured + historical


def _resolve_daily_reference_key(rows: list[dict[str, Any]], selected_month: str) -> str:
    if not selected_month:
        return ""
    today_key = datetime.now().strftime("%Y-%m-%d")
    if today_key.startswith(f"{selected_month}-"):
        return today_key
    if not rows:
        return ""
    available_dates = sorted({row["date_key"] for row in rows if row["date_key"]})
    if not available_dates:
        return ""
    return available_dates[-1]


def _shift_month_key(month_key: str, delta_months: int) -> str:
    if not month_key:
        return ""
    year_part, month_part = month_key.split("-")
    year = int(year_part)
    month = int(month_part)
    absolute = year * 12 + (month - 1) + delta_months
    new_year, new_month_index = divmod(absolute, 12)
    return f"{new_year:04d}-{new_month_index + 1:02d}"


def _shift_year_key(month_key: str, delta_years: int) -> str:
    if not month_key:
        return ""
    year_part, month_part = month_key.split("-")
    return f"{int(year_part) + delta_years:04d}-{int(month_part):02d}"


def _build_daily_series(
    rows: list[dict[str, Any]],
    expense_rows: list[dict[str, Any]],
    month_key: str,
    metric: str,
) -> list[dict[str, Any]]:
    if not month_key:
        return []
    try:
        year_part, month_part = month_key.split("-")
        year = int(year_part)
        month = int(month_part)
    except ValueError:
        return []
    last_day = monthrange(year, month)[1]
    value_by_date: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for row in rows:
        if not row["date_key"]:
            continue
        if metric == "income":
            value_by_date[row["date_key"]] += row["income"]
        elif metric == "expense":
            value_by_date[row["date_key"]] += _expense_total_from_components(
                {
                    "platform_fee_amount": row["platform_fee_amount"],
                    "procurement_total_cost": row["procurement_total_cost"],
                    "other_cost": row["other_cost"],
                    "custom_cost": sum(row["custom_cost_values"], Decimal("0")),
                }
            )
        elif metric == "gross_profit":
            value_by_date[row["date_key"]] += _sum_gross_profit(
                [row],
                row["income"],
                _expense_total_from_components(
                    {
                        "platform_fee_amount": row["platform_fee_amount"],
                        "procurement_total_cost": row["procurement_total_cost"],
                        "other_cost": row["other_cost"],
                        "custom_cost": sum(row["custom_cost_values"], Decimal("0")),
                    }
                ),
            )
        else:
            raise ValueError(f"unsupported metric: {metric}")
    if metric in {"expense", "gross_profit"}:
        external_by_date = _group_external_expenses_by_date(expense_rows)
        for date_key, components in external_by_date.items():
            extra_total = _expense_total_from_components(components)
            if metric == "expense":
                value_by_date[date_key] += extra_total
            else:
                value_by_date[date_key] -= extra_total
    points: list[dict[str, Any]] = []
    for day in range(1, last_day + 1):
        date_key = f"{month_key}-{day:02d}"
        amount = value_by_date[date_key]
        points.append(
            {
                "date": date_key,
                "label": f"{month:02d}/{day:02d}",
                "amount": format_money(amount),
                "value": float(amount),
            }
        )
    return points


def _group_external_expenses_by_date(rows: list[dict[str, Any]]) -> dict[str, dict[str, Decimal]]:
    grouped: dict[str, dict[str, Decimal]] = defaultdict(
        lambda: {
            "order_extra_expense": Decimal("0"),
            "store_operating_expense": Decimal("0"),
            "project_operating_expense": Decimal("0"),
        }
    )
    for row in rows:
        if not row["date_key"]:
            continue
        bucket = grouped[row["date_key"]]
        if row["scope_type"] == "订单级":
            bucket["order_extra_expense"] += row["amount"]
        elif row["scope_type"] == "店铺级":
            bucket["store_operating_expense"] += row["amount"]
        elif row["scope_type"] == "项目级":
            bucket["project_operating_expense"] += row["amount"]
    return grouped


def _filter_shop_expenses(rows: list[dict[str, Any]], shop_name: str) -> list[dict[str, Any]]:
    return [
        row
        for row in rows
        if row["scope_type"] != "项目级" and row["shop_name"] == shop_name
    ]


def _parse_expense_row(row: dict[str, Any]) -> dict[str, Any]:
    expense_date = str(row.get("expense_date", "")).strip()
    dt = _parse_datetime(expense_date)
    return {
        "record_id": str(row.get("record_id", "")).strip(),
        "expense_date": expense_date,
        "date_key": dt.strftime("%Y-%m-%d") if dt is not None else "",
        "month_key": dt.strftime("%Y-%m") if dt is not None else "",
        "scope_type": str(row.get("scope_type", "")).strip(),
        "shop_name": str(row.get("shop_name", "")).strip(),
        "order_id": str(row.get("order_id", "")).strip(),
        "platform": str(row.get("platform", "")).strip(),
        "category": str(row.get("category", "")).strip(),
        "amount": parse_decimal(row.get("amount")),
        "remark": str(row.get("remark", "")).strip(),
    }
