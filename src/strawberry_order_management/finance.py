from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def parse_decimal(value) -> Decimal:
    cleaned = str(value or "").strip().replace("%", "").replace(",", "")
    if not cleaned:
        return Decimal("0")
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return Decimal("0")


def parse_fee_rate_multiplier(value) -> Decimal:
    rate = parse_decimal(value)
    if rate == Decimal("0"):
        return Decimal("0")
    if abs(rate) <= Decimal("1"):
        return rate
    return (rate / Decimal("100")).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def format_money(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def calculate_platform_fee_amount(income_value, fee_rate_value) -> str:
    income = parse_decimal(income_value)
    multiplier = parse_fee_rate_multiplier(fee_rate_value)
    return format_money(income * multiplier)
