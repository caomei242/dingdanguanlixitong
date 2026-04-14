from decimal import Decimal

from strawberry_order_management.finance import (
    calculate_platform_fee_amount,
    parse_fee_rate_multiplier,
)


def test_parse_fee_rate_multiplier_supports_decimal_fraction():
    assert parse_fee_rate_multiplier("0.06") == Decimal("0.06")


def test_parse_fee_rate_multiplier_supports_percentage_number():
    assert parse_fee_rate_multiplier("6") == Decimal("0.06")
    assert parse_fee_rate_multiplier("10") == Decimal("0.10")


def test_calculate_platform_fee_amount_uses_income_times_multiplier():
    assert calculate_platform_fee_amount("162.00", "0.06") == "9.72"
    assert calculate_platform_fee_amount("162.00", "6") == "9.72"
