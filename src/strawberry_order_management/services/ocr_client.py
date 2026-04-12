from __future__ import annotations

import base64

import requests


class OCRClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def extract_text(self, image_bytes: bytes) -> str:
        if "minimax" in self.base_url.lower():
            return self._extract_via_minimax(image_bytes)

        response = requests.post(
            f"{self.base_url}/ocr",
            headers={"Authorization": f"Bearer {self.api_key}"},
            files={"file": ("order.png", image_bytes, "image/png")},
            timeout=30,
        )
        response.raise_for_status()
        try:
            payload = response.json()
        except ValueError as exc:
            raise ValueError("OCR API response is not valid JSON") from exc
        if not isinstance(payload, dict) or "text" not in payload:
            raise ValueError("OCR API response missing 'text'")
        return payload["text"]

    def _extract_via_minimax(self, image_bytes: bytes) -> str:
        encoded_image = base64.b64encode(image_bytes).decode("utf-8")
        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": "MiniMax-Text-01",
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "你是电商订单截图 OCR 助手。"
                            "请只输出图片中能识别到的订单相关文字，尽量保持字段顺序和原文信息，"
                            "不要总结、改写、翻译、解释，不要补充不存在的内容。"
                            "如果能辨认出字段，请优先按“订单编号 / 下单时间 / 订单状态 / 商品信息 / 单价/数量 / 商家收入金额 / 收货信息”这些标签输出。"
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            "请识别这张订单截图，输出尽量完整、可解析的中文文本。"
                            "收货信息请尽量保留“姓名 [编号] 手机号 地址 [编号]”这种顺序。"
                            f"[Image base64:{encoded_image}]"
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
            raise ValueError("OCR API response is not valid JSON") from exc

        choices = payload.get("choices") if isinstance(payload, dict) else None
        if not isinstance(choices, list) or not choices:
            raise ValueError("MiniMax OCR response missing choices")

        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            raise ValueError("MiniMax OCR response missing choices")

        message = first_choice.get("message")
        if not isinstance(message, dict) or "content" not in message:
            raise ValueError("MiniMax OCR response missing message content")

        return message["content"]
