from __future__ import annotations

import requests


class HelperClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def enrich_text(self, raw_text: str) -> str:
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
