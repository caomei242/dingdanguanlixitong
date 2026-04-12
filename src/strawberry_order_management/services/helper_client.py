from __future__ import annotations

import requests


class HelperClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def enrich_text(self, raw_text: str) -> str:
        if "minimax" in self.base_url.lower():
            return self._enrich_via_minimax(raw_text)

        response = requests.post(
            f"{self.base_url}/extract",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={"text": raw_text},
            timeout=30,
        )
        response.raise_for_status()
        try:
            payload = response.json()
        except ValueError as exc:
            raise ValueError("Helper API response is not valid JSON") from exc
        if not isinstance(payload, dict) or "text" not in payload:
            raise ValueError("Helper API response missing 'text'")
        return payload["text"]

    def _enrich_via_minimax(self, raw_text: str) -> str:
        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": "MiniMax-M2.5",
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "你是订单信息整理助手。"
                            "请把 OCR 原文整理成最容易被程序解析的规范化纯文本，不要解释，不要补充不存在的内容。"
                            "不要加 Markdown，不要加 JSON，不要加代码块。"
                            "优先按这些字段逐行输出："
                            "订单编号 <值>；下单时间 <值>；订单状态 <值>；商品信息 <值>；单价/数量 ¥<单价> x<数量>；"
                            "商家收入金额 ¥<金额>；收货信息 姓名 [编号] 手机号 地址 [编号]。"
                            "字段名请保持原样，字段名后面不要加中文冒号或其他标点，"
                            "尤其是“收货信息 姓名 [编号] 手机号 地址 [编号]”这一结构。"
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            "请整理下面这段订单 OCR 文本，只输出规范化结果：\n"
                            f"{raw_text}"
                        ),
                    },
                ],
            },
            timeout=30,
        )
        response.raise_for_status()
        try:
            payload = response.json()
        except ValueError as exc:
            raise ValueError("Helper API response is not valid JSON") from exc

        choices = payload.get("choices") if isinstance(payload, dict) else None
        if not isinstance(choices, list) or not choices:
            raise ValueError("MiniMax response missing choices")

        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            raise ValueError("MiniMax response missing choices")

        message = first_choice.get("message")
        if not isinstance(message, dict) or "content" not in message:
            raise ValueError("MiniMax response missing message content")

        return message["content"]
