from __future__ import annotations

import re

from strawberry_order_management.extractors.address import clean_virtual_number_artifacts, extract_address_payload
from strawberry_order_management.models import ParsedOrder

_ORDER_ID_PATTERNS = (
    re.compile(r"订单编号\s*[:：]?\s*(\d+)", re.S),
    re.compile(r"订单号\s*[:：]?\s*(\d+)", re.S),
)
_PLACED_AT_PATTERNS = (
    re.compile(r"下单时间\s*[:：]?\s*([0-9:\-\s]+)", re.S),
)
_ORDER_STATUS_PATTERNS = (
    re.compile(r"订单状态\s*[:：]?\s*(.+?)\s*商品信息", re.S),
    re.compile(r"订单状态\s*[:：]?\s*(.+?)\s*(?:详细收货信息|收货信息|收件人|买家收货信息|商品信息|商品|$)", re.S),
)
_PRODUCT_BLOCK_PATTERNS = (
    re.compile(r"商品信息\s*(.+?)\s*单价/数量", re.S),
    re.compile(r"(?:^|\n)\s*商品\s*\n\s*(.+?)\s*单价/数量", re.S),
)
_QUANTITY_PATTERN = re.compile(r"单价/数量\s*¥\s*([0-9.]+)\s*[x×]\s*(\d+)", re.S)
_ORDER_AMOUNT_PATTERN = re.compile(r"单价/数量\s*¥\s*([0-9.]+)", re.S)
_INCOME_AMOUNT_PATTERNS = (
    re.compile(r"商家收入金额\s*¥\s*([0-9.]+)", re.S),
    re.compile(r"实收款/优惠信息\s*¥\s*([0-9.]+)", re.S),
    re.compile(r"实收款\s*¥\s*([0-9.]+)", re.S),
)
_RECIPIENT_PATTERN = re.compile(
    r"收货信息\s*(.+?)\s*\[\s*(\d+)\s*\]\s*(\d{11})\s*(.+?)\s*\[\s*\2\s*\]",
    re.S,
)
_RECIPIENT_LABEL_PATTERN = re.compile(
    r"(?:收货信息|详细收货信息)\s*"
    r"收件人\s*(?P<name>.+?)(?:\s*\[\s*(?P<bracket_code>\d+)\s*\])?\s*"
    r"收货地址\s*(?P<address>.+?)\s*"
    r"(?:真实手机号\s*\S+\s*)?"
    r"虚拟号\s*(?P<phone>\d{11})\s*分机号\s*(?P<code>\d+)",
    re.S,
)
_RECIPIENT_FALLBACK_BLOCK_PATTERNS = (
    re.compile(r"收货信息\s*(.+?)\s*$", re.S),
    re.compile(r"详细收货信息\s*(.+?)\s*$", re.S),
)
_CLEANED_RECIPIENT_PATTERN = re.compile(r"^(?P<name>.+?)(?P<phone>\d{11})(?P<address>.+)$", re.S)
_SKU_PATTERN = re.compile(r"(?:SKU|sku|货号|商家编码)\s*[:：]\s*(.+)", re.I)
_IGNORED_PRODUCT_LINE_PATTERN = re.compile(r"^(?:商品(?:单)?ID|商品id|item id)\s*[:：]", re.I)
_INLINE_SPECIFICATION_PATTERN = re.compile(
    r"^(?P<name>.+?)\s+(?P<spec>\d+(?:\.\d+)?\s*(?:ML|ml|mL|L|l|升|g|kg|KG|斤)[^\n]*)$"
)
_ORDER_STATUS_ALIASES = {
    "未发货": "待发货",
    "已下单未发货": "已拍单未发货",
}


def _search(pattern: re.Pattern[str], raw_text: str) -> re.Match[str]:
    match = pattern.search(raw_text)
    if match is None:
        raise ValueError(f"missing field: {pattern.pattern}")
    return match


def _search_any(
    patterns: tuple[re.Pattern[str], ...], raw_text: str, field_name: str
) -> re.Match[str]:
    for pattern in patterns:
        match = pattern.search(raw_text)
        if match is not None:
            return match
    raise ValueError(f"missing field: {field_name}")


def parse_order_text(raw_text: str) -> ParsedOrder:
    order_id = _search_any(_ORDER_ID_PATTERNS, raw_text, "订单编号/订单号").group(1)
    placed_at = _normalize_placed_at(
        _search_any(_PLACED_AT_PATTERNS, raw_text, "下单时间").group(1).strip()
    )
    order_status = _normalize_order_status(
        " ".join(_search_any(_ORDER_STATUS_PATTERNS, raw_text, "订单状态").group(1).split()).strip()
    )
    product_name, specification, sku = _parse_product_block(
        _search_any(_PRODUCT_BLOCK_PATTERNS, raw_text, "商品信息/商品").group(1)
    )
    quantity = _search(_QUANTITY_PATTERN, raw_text).group(2)
    order_amount = _search(_ORDER_AMOUNT_PATTERN, raw_text).group(1)
    income_amount = _search_any(_INCOME_AMOUNT_PATTERNS, raw_text, "商家收入金额/实收款").group(1)

    recipient_name, phone_number, code, address = _parse_recipient(raw_text)
    delivery_note = f"请电话送货上门谢谢【{code}】"

    return ParsedOrder(
        order_id=order_id,
        placed_at=placed_at,
        order_status=order_status,
        product_name=product_name,
        specification=specification,
        sku=sku,
        quantity=quantity,
        order_amount=order_amount,
        income_amount=income_amount,
        recipient_name=recipient_name,
        phone_number=phone_number,
        code=code,
        address=address,
        delivery_note=delivery_note,
        platform=_detect_platform(raw_text),
    )


def _parse_recipient(raw_text: str) -> tuple[str, str, str, str]:
    recipient_match = _RECIPIENT_PATTERN.search(raw_text)
    if recipient_match is not None:
        recipient_name = " ".join(recipient_match.group(1).split()).strip()
        code = recipient_match.group(2)
        phone_number = recipient_match.group(3)
        address = clean_virtual_number_artifacts(" ".join(recipient_match.group(4).split()).strip())
        return recipient_name, phone_number, code, address

    recipient_label_match = _RECIPIENT_LABEL_PATTERN.search(raw_text)
    if recipient_label_match is not None:
        bracket_code = recipient_label_match.group("bracket_code")
        code = recipient_label_match.group("code")
        if bracket_code and bracket_code != code:
            raise ValueError("recipient code mismatch")
        recipient_name = " ".join(recipient_label_match.group("name").split()).strip()
        phone_number = recipient_label_match.group("phone")
        address = clean_virtual_number_artifacts(" ".join(recipient_label_match.group("address").split()).strip())
        return recipient_name, phone_number, code, address

    block_match = None
    for pattern in _RECIPIENT_FALLBACK_BLOCK_PATTERNS:
        block_match = pattern.search(raw_text)
        if block_match is not None:
            break
    if block_match is None:
        _search(_RECIPIENT_PATTERN, raw_text)
    payload = extract_address_payload(block_match.group(1).strip())
    cleaned_match = _CLEANED_RECIPIENT_PATTERN.match(payload.cleaned_text)
    if cleaned_match is None:
        raise ValueError(f"missing field: {_RECIPIENT_PATTERN.pattern}")
    recipient_name = " ".join(cleaned_match.group("name").split()).strip()
    phone_number = cleaned_match.group("phone")
    address = clean_virtual_number_artifacts(" ".join(cleaned_match.group("address").split()).strip())
    return recipient_name, phone_number, payload.code, address


def _normalize_order_status(value: str) -> str:
    cleaned = str(value).strip()
    return _ORDER_STATUS_ALIASES.get(cleaned, cleaned)


def _normalize_placed_at(value: str) -> str:
    cleaned = " ".join(str(value).strip().split())
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}", cleaned):
        return f"{cleaned}:00"
    return cleaned


def _detect_platform(raw_text: str) -> str:
    text = str(raw_text or "")
    if any(marker in text for marker in ("微信小店", "虚拟号", "分机号", "详细收货信息")):
        return "微信小店"
    return "抖店"


def _parse_product_block(raw_block: str) -> tuple[str, str, str]:
    lines = [
        " ".join(line.split()).strip()
        for line in str(raw_block).splitlines()
        if " ".join(line.split()).strip()
    ]
    if not lines:
        return "", "", ""
    product_name = lines[0]
    product_name, inline_specification = _split_inline_specification(product_name)
    specification_lines: list[str] = []
    if inline_specification:
        specification_lines.append(inline_specification)
    sku = ""
    for line in lines[1:]:
        sku_match = _SKU_PATTERN.search(line)
        if sku_match and not sku:
            sku = " ".join(sku_match.group(1).split()).strip()
            continue
        if _IGNORED_PRODUCT_LINE_PATTERN.match(line):
            continue
        specification_lines.append(line)
    specification = " ".join(specification_lines).strip()
    return product_name, specification, sku


def _split_inline_specification(product_name: str) -> tuple[str, str]:
    cleaned = " ".join(str(product_name).split()).strip()
    match = _INLINE_SPECIFICATION_PATTERN.match(cleaned)
    if not match:
        return cleaned, ""
    return match.group("name").strip(), match.group("spec").strip()
