from __future__ import annotations

import re

from strawberry_order_management.models import AddressExtraction

PATTERN = re.compile(
    r"^(?P<prefix>.+?)\[(?P<code1>\d+)\](?P<body>.+)\[(?P<code2>\d+)\]$"
)
INLINE_PATTERN = re.compile(
    r"^(?P<name>[^,，\s]+)\s*[,，]\s*(?P<phone>\d{11})\s*-\s*(?P<code>\d+)\s*[,，]\s*(?P<address>.+)$"
)


def extract_address_payload(raw_text: str) -> AddressExtraction:
    text = raw_text.strip()
    match = PATTERN.match(text)
    if match is not None:
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

    inline_match = INLINE_PATTERN.match(text)
    if inline_match is None:
        raise ValueError("地址格式不符合规则")

    code = inline_match.group("code")
    cleaned_address = "".join(inline_match.group("address").split())
    return AddressExtraction(
        cleaned_text=f"{inline_match.group('name')}{inline_match.group('phone')}{cleaned_address}",
        delivery_note=f"请电话送货上门谢谢【{code}】",
        code=code,
    )
