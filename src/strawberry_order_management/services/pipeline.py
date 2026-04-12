from __future__ import annotations

from datetime import datetime

from strawberry_order_management.extractors.order_parser import parse_order_text
from strawberry_order_management.models import ParsedOrder


DEFAULT_FEISHU_FIELD_MAPPING = {
    "备注": "备注",
    "订单日期": "订单日期",
    "下单时间": "下单时间",
    "订单状态": "订单状态",
    "收入": "收入",
    "发货地址": "发货地址",
    "价格": "",
    "采购商品1": "",
    "采购数量1": "",
    "采购成本1": "",
    "采购商品2": "",
    "采购数量2": "",
    "采购成本2": "",
    "采购商品3": "",
    "采购数量3": "",
    "采购成本3": "",
}


def build_feishu_payload(
    order: ParsedOrder,
    field_mapping: dict[str, str] | None = None,
) -> dict[str, str]:
    try:
        placed_at = datetime.strptime(order.placed_at, "%Y-%m-%d %H:%M:%S")
    except ValueError as exc:
        raise ValueError("placed_at must be in 'YYYY-MM-DD HH:MM:SS' format") from exc
    mapping = dict(DEFAULT_FEISHU_FIELD_MAPPING)
    if field_mapping:
        mapping.update(field_mapping)

    source_fields = {
        "备注": order.delivery_note,
        "订单日期": placed_at.strftime("%Y/%m/%d"),
        "下单时间": placed_at.strftime("%H:%M:%S"),
        "订单状态": order.order_status,
        "收入": order.income_amount,
        "发货地址": f"{order.recipient_name} {order.phone_number}-{order.code} {order.address}",
        "价格": order.order_amount,
    }
    for index, item in enumerate(order.procurement_items, start=1):
        source_fields[f"采购商品{index}"] = item.product_name
        source_fields[f"采购数量{index}"] = item.quantity
        source_fields[f"采购成本{index}"] = item.cost

    payload: dict[str, str] = {}
    for source_name, value in source_fields.items():
        target_name = str(mapping.get(source_name, "")).strip()
        text_value = str(value).strip()
        if not target_name or not text_value:
            continue
        payload[target_name] = text_value
    return payload


class OrderPipeline:
    def __init__(self, ocr_client, helper_client, feishu_client):
        self.ocr_client = ocr_client
        self.helper_client = helper_client
        self.feishu_client = feishu_client

    def extract_order(self, image_bytes: bytes) -> ParsedOrder:
        ocr_text = self.ocr_client.extract_text(image_bytes)
        helper_text = self.helper_client.enrich_text(ocr_text)
        return parse_order_text(helper_text)

    def build_feishu_payload(
        self, order: ParsedOrder, field_mapping: dict[str, str] | None = None
    ) -> dict[str, str]:
        return build_feishu_payload(order, field_mapping)

    def submit_order(
        self,
        access_token: str,
        order: ParsedOrder,
        field_mapping: dict[str, str] | None = None,
    ) -> dict:
        if self.feishu_client is None:
            raise ValueError("missing feishu client")
        return self.feishu_client.create_record(
            access_token,
            build_feishu_payload(order, field_mapping),
        )
