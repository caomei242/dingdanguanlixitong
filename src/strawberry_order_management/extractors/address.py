from __future__ import annotations

import re

from strawberry_order_management.models import AddressExtraction

PATTERN = re.compile(
    r"^(?P<prefix>.+?)\[(?P<code1>\d+)\](?P<body>.+)\[(?P<code2>\d+)\]$",
    re.S,
)
INLINE_PATTERN = re.compile(
    r"^(?P<name>[^,，\s]+)\s*[,，]\s*(?P<phone>\d{11})\s*-\s*(?P<code>\d+)\s*[,，]\s*(?P<address>.+)$"
)
WECHAT_VIRTUAL_PATTERN = re.compile(
    r"^(?P<name>.+?)[（(]\s*(?P<name_code>\d+)\s*[）)]\s*[,，]\s*"
    r"(?P<phone>\d{11})\s*-\s*(?P<phone_code>\d+)\s*[,，]\s*(?P<address>.+)$"
)
WECHAT_TAIL_CODE_PATTERN = re.compile(r"[（(]\s*拨打请输入分机号\s*(?P<code>\d+)\s*[）)]\s*[。.]?$")
WECHAT_LABEL_PATTERN = re.compile(
    r"收件人\s*(?P<name>\S+)\s*收货地址\s*(?P<address>.+?)\s*"
    r"(?:真实手机号\s*\S+\s*)?"
    r"虚拟号\s*(?P<phone>\d{11})\s*分机号\s*(?P<code>\d+)",
    re.S,
)
GENERIC_ADDRESS_BLOCK_PATTERN = re.compile(
    r"(?:收货信息|详细收货信息)\s*(?P<block>.+?)\s*$",
    re.S,
)
PLAIN_PHONE_ADDRESS_PATTERN = re.compile(
    r"^(?P<name>[\u4e00-\u9fffA-Za-z·]{1,12})\s*"
    r"(?P<phone>1\d{10})\s*(?P<address>.+)$",
    re.S,
)
TAIL_BRACKET_CODE_PATTERN = re.compile(r"\s*[\[【]\s*(?P<code>\d+)\s*[\]】]\s*$")
VIRTUAL_NUMBER_LABEL_PATTERN = re.compile(r"(?<=\d{11})\s*虚拟号\s*")
VIRTUAL_NUMBER_PREFIX_PATTERN = re.compile(r"^\s*虚拟号\s*[:：]?\s*")
REAL_PHONE_HINT_PATTERN = re.compile(r"\s*真实手机号\s*(?:申请查看|\S+)?\s*")
WECHAT_CALL_HINT_PATTERN = re.compile(r"[（(]\s*拨打请输入分机号\s*\d+\s*[）)]\s*[。.]?$")


def extract_address_payload(raw_text: str) -> AddressExtraction:
    text = raw_text.strip()
    match = PATTERN.match(text)
    if match is not None:
        code1 = match.group("code1")
        code2 = match.group("code2")
        if code1 != code2:
            raise ValueError("编号不一致")

        cleaned_text = _clean_extracted_text(f"{match.group('prefix')}{match.group('body')}")
        return AddressExtraction(
            cleaned_text=cleaned_text,
            delivery_note=f"请电话送货上门谢谢【{code1}】",
            code=code1,
        )

    wechat_match = WECHAT_VIRTUAL_PATTERN.match(text)
    if wechat_match is not None:
        name_code = wechat_match.group("name_code")
        phone_code = wechat_match.group("phone_code")
        address = wechat_match.group("address").strip()
        tail_match = WECHAT_TAIL_CODE_PATTERN.search(address)
        tail_code = tail_match.group("code") if tail_match is not None else name_code
        if len({name_code, phone_code, tail_code}) != 1:
            raise ValueError("编号不一致")
        if tail_match is not None:
            address = WECHAT_TAIL_CODE_PATTERN.sub("", address).strip()
        cleaned_address = "".join(address.split()).rstrip("。.")
        return AddressExtraction(
            cleaned_text=_clean_extracted_text(
                f"{wechat_match.group('name').strip()}{wechat_match.group('phone')}{cleaned_address}"
            ),
            delivery_note=f"请电话送货上门谢谢【{name_code}】",
            code=name_code,
        )

    wechat_label_match = WECHAT_LABEL_PATTERN.search(text)
    if wechat_label_match is not None:
        cleaned_address = "".join(wechat_label_match.group("address").split()).rstrip("。.")
        code = wechat_label_match.group("code")
        return AddressExtraction(
            cleaned_text=_clean_extracted_text(
                f"{wechat_label_match.group('name').strip()}{wechat_label_match.group('phone')}{cleaned_address}"
            ),
            delivery_note=f"请电话送货上门谢谢【{code}】",
            code=code,
        )

    generic_block_match = GENERIC_ADDRESS_BLOCK_PATTERN.search(text)
    if generic_block_match is not None and generic_block_match.group("block").strip() != text:
        return extract_address_payload(generic_block_match.group("block").strip())

    inline_match = INLINE_PATTERN.match(text)
    if inline_match is None:
        plain_match = PLAIN_PHONE_ADDRESS_PATTERN.match(text)
        if plain_match is None:
            raise ValueError("地址格式不符合规则")
        raw_address = plain_match.group("address").strip()
        tail_code_match = TAIL_BRACKET_CODE_PATTERN.search(raw_address)
        code = tail_code_match.group("code") if tail_code_match is not None else ""
        if tail_code_match is not None:
            raw_address = TAIL_BRACKET_CODE_PATTERN.sub("", raw_address).strip()
        cleaned_address = "".join(raw_address.split()).rstrip("。.")
        return AddressExtraction(
            cleaned_text=_clean_extracted_text(
                f"{plain_match.group('name')}{plain_match.group('phone')}{cleaned_address}"
            ),
            delivery_note=f"请电话送货上门谢谢【{code}】" if code else "",
            code=code,
        )

    code = inline_match.group("code")
    cleaned_address = "".join(inline_match.group("address").split())
    return AddressExtraction(
        cleaned_text=_clean_extracted_text(
            f"{inline_match.group('name')}{inline_match.group('phone')}{cleaned_address}"
        ),
        delivery_note=f"请电话送货上门谢谢【{code}】",
        code=code,
    )


def _clean_extracted_text(value: str) -> str:
    return VIRTUAL_NUMBER_LABEL_PATTERN.sub("", "".join(str(value or "").split())).strip()


def clean_virtual_number_artifacts(value: str) -> str:
    text = " ".join(str(value or "").split()).strip()
    if not text:
        return ""
    text = REAL_PHONE_HINT_PATTERN.sub(" ", text)
    text = VIRTUAL_NUMBER_LABEL_PATTERN.sub("", text)
    text = VIRTUAL_NUMBER_PREFIX_PATTERN.sub("", text)
    text = WECHAT_CALL_HINT_PATTERN.sub("", text).strip()
    return text.strip("，, ")
