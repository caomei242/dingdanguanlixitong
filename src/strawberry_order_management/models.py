from __future__ import annotations

from dataclasses import dataclass, field


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
    specification: str = ""
    sku: str = ""
    sku_image_path: str = ""
    platform: str = "抖店"
    platform_fee_rate: str = ""
    platform_fee_amount: str = ""
    other_cost: str = ""
    procurement_total_cost: str = ""
    gross_profit: str = ""
    custom_cost_labels: tuple[str, str, str] = ("", "", "")
    custom_cost_values: tuple[str, str, str] = ("", "", "")
    procurement_items: tuple["ProcurementItem", "ProcurementItem", "ProcurementItem"] = field(
        default_factory=lambda: (
            ProcurementItem("", "1", ""),
            ProcurementItem("", "1", ""),
            ProcurementItem("", "1", ""),
        )
    )


@dataclass(frozen=True)
class ProcurementItem:
    product_name: str
    quantity: str
    cost: str


@dataclass(frozen=True)
class ProductPreset:
    name: str
    default_cost: str


@dataclass(frozen=True)
class ShopConfig:
    name: str
    app_token: str
    table_id: str
    table_name: str
    wiki_url: str = ""
    field_mapping: dict[str, str] = field(default_factory=dict)
