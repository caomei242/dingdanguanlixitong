from __future__ import annotations

from datetime import datetime

from strawberry_order_management.extractors.order_parser import parse_order_text
from strawberry_order_management.models import ParsedOrder


def build_feishu_payload(order: ParsedOrder) -> dict[str, str]:
    try:
        placed_at = datetime.strptime(order.placed_at, "%Y-%m-%d %H:%M:%S")
    except ValueError as exc:
        raise ValueError("placed_at must be in 'YYYY-MM-DD HH:MM:SS' format") from exc
    return {
        "备注": order.delivery_note,
        "订单日期": placed_at.strftime("%Y/%m/%d"),
        "下单时间": placed_at.strftime("%H:%M:%S"),
        "订单状态": order.order_status,
        "收入": order.income_amount,
        "发货地址": f"{order.recipient_name} {order.phone_number}-{order.code} {order.address}",
        "价格": order.order_amount,
    }


class OrderPipeline:
    def __init__(self, ocr_client, helper_client, feishu_client):
        self.ocr_client = ocr_client
        self.helper_client = helper_client
        self.feishu_client = feishu_client

    def extract_order(self, image_bytes: bytes) -> ParsedOrder:
        ocr_text = self.ocr_client.extract_text(image_bytes)
        helper_text = self.helper_client.enrich_text(ocr_text)
        return parse_order_text(helper_text)

    def build_feishu_payload(self, order: ParsedOrder) -> dict[str, str]:
        return build_feishu_payload(order)

    def submit_order(self, access_token: str, order: ParsedOrder) -> dict:
        if self.feishu_client is None:
            raise ValueError("missing feishu client")
        return self.feishu_client.create_record(access_token, build_feishu_payload(order))
