from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AddressExtraction:
    cleaned_text: str
    delivery_note: str
    code: str


@dataclass(frozen=True)
class ParsedOrder:
    order_id: str
    placed_at: str
    order_status: str
    product_name: str
    quantity: str
    order_amount: str
    income_amount: str
    recipient_name: str
    phone_number: str
    code: str
    address: str
    delivery_note: str
