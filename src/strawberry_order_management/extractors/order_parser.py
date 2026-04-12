from __future__ import annotations

import re

from strawberry_order_management.models import ParsedOrder

_ORDER_ID_PATTERN = re.compile(r"订单编号\s*(\d+)", re.S)
_PLACED_AT_PATTERN = re.compile(r"下单时间\s*([0-9:\-\s]+)", re.S)
_ORDER_STATUS_PATTERN = re.compile(r"订单状态\s*(.+?)\s*商品信息", re.S)
_PRODUCT_NAME_PATTERN = re.compile(r"商品信息\s*(.+?)\s*单价/数量", re.S)
_QUANTITY_PATTERN = re.compile(r"单价/数量\s*¥\s*([0-9.]+)\s*[x×]\s*(\d+)", re.S)
_ORDER_AMOUNT_PATTERN = re.compile(r"单价/数量\s*¥\s*([0-9.]+)", re.S)
_INCOME_AMOUNT_PATTERN = re.compile(r"商家收入金额\s*¥\s*([0-9.]+)", re.S)
_RECIPIENT_PATTERN = re.compile(
    r"收货信息\s*(.+?)\s*\[\s*(\d+)\s*\]\s*(\d{11})\s*(.+?)\s*\[\s*\2\s*\]",
    re.S,
)


def _search(pattern: re.Pattern[str], raw_text: str) -> re.Match[str]:
    match = pattern.search(raw_text)
    if match is None:
        raise ValueError(f"missing field: {pattern.pattern}")
    return match


def parse_order_text(raw_text: str) -> ParsedOrder:
    order_id = _search(_ORDER_ID_PATTERN, raw_text).group(1)
    placed_at = _search(_PLACED_AT_PATTERN, raw_text).group(1).strip()
    order_status = " ".join(_search(_ORDER_STATUS_PATTERN, raw_text).group(1).split()).strip()
    product_name = " ".join(_search(_PRODUCT_NAME_PATTERN, raw_text).group(1).split()).strip()
    quantity = _search(_QUANTITY_PATTERN, raw_text).group(2)
    order_amount = _search(_ORDER_AMOUNT_PATTERN, raw_text).group(1)
    income_amount = _search(_INCOME_AMOUNT_PATTERN, raw_text).group(1)

    recipient_match = _search(_RECIPIENT_PATTERN, raw_text)
    recipient_name = " ".join(recipient_match.group(1).split()).strip()
    code = recipient_match.group(2)
    phone_number = recipient_match.group(3)
    address = " ".join(recipient_match.group(4).split()).strip()
    delivery_note = f"请电话送货上门谢谢【{code}】"

    return ParsedOrder(
        order_id=order_id,
        placed_at=placed_at,
        order_status=order_status,
        product_name=product_name,
        quantity=quantity,
        order_amount=order_amount,
        income_amount=income_amount,
        recipient_name=recipient_name,
        phone_number=phone_number,
        code=code,
        address=address,
        delivery_note=delivery_note,
    )
