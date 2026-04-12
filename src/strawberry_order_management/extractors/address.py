from __future__ import annotations

import re

from strawberry_order_management.models import AddressExtraction

PATTERN = re.compile(
    r"^(?P<prefix>.+?)\[(?P<code1>\d+)\](?P<body>.+)\[(?P<code2>\d+)\]$"
)


def extract_address_payload(raw_text: str) -> AddressExtraction:
    text = raw_text.strip()
    match = PATTERN.match(text)
    if match is None:
        raise ValueError("地址格式不符合规则")

    code1 = match.group("code1")
    code2 = match.group("code2")
    if code1 != code2:
        raise ValueError("编号不一致")

    cleaned_text = f"{match.group('prefix')}{match.group('body')}"
    return AddressExtraction(
        cleaned_text=cleaned_text,
        delivery_note=f"请电话送货上门谢谢【{code1}】",
        code=code1,
    )
