from __future__ import annotations

import re

from strawberry_order_management.extractors.address import extract_address_payload
from strawberry_order_management.models import AddressExtraction
from strawberry_order_management.extractors.order_parser import (
    _parse_product_block,
    _normalize_placed_at,
)

_ORDER_ID_PATTERNS = (
    re.compile(r"订单编号\s*[:：]?\s*(\d+)", re.S),
    re.compile(r"订单号\s*[:：]?\s*(\d+)", re.S),
    re.compile(r"商品单\s*ID\s*[:：]?\s*(\d+)", re.I | re.S),
)
_PLACED_AT_PATTERN = re.compile(r"下单时间\s*[:：]?\s*([0-9:\-\s]+)", re.S)
_ORDER_STATUS_PATTERN = re.compile(r"订单状态\s*[:：]?\s*(.+?)\s*(?:商品|收货信息|$)", re.S)
_PRODUCT_BLOCK_PATTERNS = (
    re.compile(r"商品信息\s*(.+?)\s*单价/数量", re.S),
    re.compile(r"(?:^|\n)\s*商品\s*\n\s*(.+?)\s*单价/数量", re.S),
)
_QUANTITY_PATTERN = re.compile(r"单价/数量\s*¥\s*([0-9.]+)\s*[x×]\s*(\d+)", re.S)
_ORDER_AMOUNT_PATTERN = re.compile(r"单价/数量\s*¥\s*([0-9.]+)", re.S)
_INCOME_AMOUNT_PATTERNS = (
    re.compile(r"商家收入金额\s*¥\s*([0-9.]+)", re.S),
    re.compile(r"实收款/优惠信息\s*¥\s*([0-9.]+)", re.S),
    re.compile(r"收入\s*[:：]?\s*¥?\s*([0-9.]+)", re.S),
)
_ADDRESS_BLOCK_PATTERNS = (
    re.compile(r"收货信息\s*(.+?)\s*$", re.S),
    re.compile(r"详细收货信息\s*(.+?)\s*$", re.S),
)
_PLAIN_RECIPIENT_SEARCH_PATTERN = re.compile(
    r"(?P<name>[\u4e00-\u9fffA-Za-z·]{1,16})\s*"
    r"(?P<phone>1\d{10})\s*(?P<address>.+)$",
    re.S,
)
_CLEANED_RECIPIENT_PATTERN = re.compile(r"^(?P<name>.+?)(?P<phone>1\d{10})(?P<address>.+)$", re.S)
_ORDER_STATUS_ALIASES = {
    "完成": "已发货",
    "已完成": "已发货",
    "未发货": "待发货",
    "已下单未发货": "已拍单未发货",
}


def parse_supplemental_order_text(raw_text: str) -> dict[str, str]:
    text = str(raw_text or "").strip()
    patch: dict[str, str] = {}
    _put_first_match(patch, "order_id", _ORDER_ID_PATTERNS, text)
    placed_at_match = _PLACED_AT_PATTERN.search(text)
    if placed_at_match is not None:
        patch["placed_at"] = _normalize_placed_at(placed_at_match.group(1).strip())
    status_match = _ORDER_STATUS_PATTERN.search(text)
    if status_match is not None:
        patch["order_status"] = _normalize_order_status(status_match.group(1))
    product_block = _find_product_block(text)
    if product_block:
        product_name, specification, sku = _parse_product_block(product_block)
        if product_name:
            patch["product_name"] = product_name
        if specification:
            patch["specification"] = specification
        if sku:
            patch["sku"] = sku
    quantity_match = _QUANTITY_PATTERN.search(text)
    if quantity_match is not None:
        patch["order_amount"] = quantity_match.group(1)
        patch["quantity"] = quantity_match.group(2)
    else:
        order_amount_match = _ORDER_AMOUNT_PATTERN.search(text)
        if order_amount_match is not None:
            patch["order_amount"] = order_amount_match.group(1)
    income_match = _search_any(_INCOME_AMOUNT_PATTERNS, text)
    if income_match is not None:
        patch["income_amount"] = income_match.group(1)
    patch.update(_parse_recipient_patch(text))
    return patch


def _put_first_match(
    patch: dict[str, str],
    key: str,
    patterns: tuple[re.Pattern[str], ...],
    text: str,
) -> None:
    match = _search_any(patterns, text)
    if match is not None:
        patch[key] = match.group(1).strip()


def _search_any(patterns: tuple[re.Pattern[str], ...], text: str) -> re.Match[str] | None:
    for pattern in patterns:
        match = pattern.search(text)
        if match is not None:
            return match
    return None


def _find_product_block(text: str) -> str:
    for pattern in _PRODUCT_BLOCK_PATTERNS:
        match = pattern.search(text)
        if match is not None:
            return match.group(1).strip()
    return ""


def _normalize_order_status(value: str) -> str:
    cleaned = " ".join(str(value or "").split()).strip()
    return _ORDER_STATUS_ALIASES.get(cleaned, cleaned)


def _parse_recipient_patch(text: str) -> dict[str, str]:
    for pattern in _ADDRESS_BLOCK_PATTERNS:
        block_match = pattern.search(text)
        if block_match is None:
            continue
        try:
            return _patch_from_address_payload(extract_address_payload(block_match.group(1).strip()))
        except ValueError:
            continue
    try:
        return _patch_from_address_payload(extract_address_payload(text))
    except ValueError:
        pass
    recipient_match = _PLAIN_RECIPIENT_SEARCH_PATTERN.search(text)
    if recipient_match is None:
        return {}
    name = _strip_recipient_label(recipient_match.group("name").strip())
    address = "".join(recipient_match.group("address").split()).rstrip("。.")
    return {
        "recipient_name": name,
        "phone_number": recipient_match.group("phone"),
        "code": "",
        "address": address,
        "delivery_note": "",
    }


def _patch_from_address_payload(payload: AddressExtraction) -> dict[str, str]:
    cleaned_match = _CLEANED_RECIPIENT_PATTERN.match(payload.cleaned_text)
    if cleaned_match is None:
        return {}
    return {
        "recipient_name": _strip_recipient_label(cleaned_match.group("name").strip()),
        "phone_number": cleaned_match.group("phone"),
        "code": payload.code,
        "address": " ".join(cleaned_match.group("address").split()).strip(),
        "delivery_note": payload.delivery_note,
    }


def _strip_recipient_label(value: str) -> str:
    return re.sub(r"^(?:收货信息|详细收货信息|收件人|买家收货信息)+", "", value).strip()
