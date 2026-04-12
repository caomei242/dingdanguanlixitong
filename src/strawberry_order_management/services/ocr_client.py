from __future__ import annotations

import requests


class OCRClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def extract_text(self, image_bytes: bytes) -> str:
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
