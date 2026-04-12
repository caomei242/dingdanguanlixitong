from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AddressExtraction:
    cleaned_text: str
    delivery_note: str
    code: str
