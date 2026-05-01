from __future__ import annotations

import re
from typing import Any

from strawberry_order_management.extractors.order_parser import parse_order_text

_ORDER_START_PATTERN = re.compile(r"(?:订单编号|订单号)\s*[:：]?\s*\d+")


def split_order_text_blocks(text: str) -> list[str]:
    """Split OCR/helper text into per-order text blocks."""
    cleaned_text = str(text or "").strip()
    if not cleaned_text:
        return []

    matches = list(_ORDER_START_PATTERN.finditer(cleaned_text))
    if len(matches) <= 1:
        return [cleaned_text]

    blocks: list[str] = []
    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(cleaned_text)
        block = cleaned_text[start:end].strip()
        if block:
            blocks.append(block)
    return blocks


def parse_order_text_batch(text: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for index, raw_text in enumerate(split_order_text_blocks(text), start=1):
        try:
            order = parse_order_text(raw_text)
        except Exception as exc:  # noqa: BLE001 - one bad block must not stop the batch.
            results.append(
                {
                    "index": index,
                    "ok": False,
                    "raw_text": raw_text,
                    "order": None,
                    "error": f"解析失败：{exc}",
                }
            )
            continue

        results.append(
            {
                "index": index,
                "ok": True,
                "raw_text": raw_text,
                "order": order,
                "error": "",
            }
        )
    return results
