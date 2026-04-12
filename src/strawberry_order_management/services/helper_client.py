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
                        "content": "你是订单信息整理助手，请输出可解析的订单文本。",
                    },
                    {"role": "user", "content": raw_text},
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
