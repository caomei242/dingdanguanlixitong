from __future__ import annotations

from datetime import datetime

from strawberry_order_management.extractors.multi_order import parse_order_text_batch
from strawberry_order_management.extractors.order_parser import _detect_platform, parse_order_text
from strawberry_order_management.extractors.supplemental_order import parse_supplemental_order_text
from strawberry_order_management.models import ParsedOrder
from strawberry_order_management.services.order_image_splitter import OrderImageSplitter


DEFAULT_FEISHU_FIELD_MAPPING = {
    "店铺": "",
    "平台": "平台",
    "订单编号": "",
    "备注": "备注",
    "订单日期": "订单日期",
    "下单时间": "下单时间",
    "订单状态": "订单状态",
    "商品名称": "",
    "规格": "",
    "SKU": "",
    "SKU 图片": "",
    "数量": "",
    "收件人": "",
    "手机号": "",
    "编号": "",
    "收入": "收入",
    "发货地址": "发货地址",
    "采购快递单号": "",
    "采购快递单号1": "",
    "采购快递单号2": "",
    "采购快递单号3": "",
    "价格": "",
    "平台扣点比例": "",
    "平台扣点金额": "",
    "其他成本": "",
    "采购总成本": "",
    "毛利润": "",
    "自定义字段1": "",
    "自定义字段2": "",
    "自定义字段3": "",
    "同步方式": "",
    "同步状态": "",
    "同步说明": "",
    "录入时间": "",
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
    *,
    shop_name: str = "",
    sync_source: str = "",
    sync_status: str = "",
    sync_message: str = "",
    blank_source_fields: set[str] | None = None,
) -> dict[str, object]:
    placed_at = _parse_placed_at(order.placed_at)
    mapping = dict(DEFAULT_FEISHU_FIELD_MAPPING)
    if field_mapping:
        mapping.update(field_mapping)
    blank_source_fields = {str(item).strip() for item in (blank_source_fields or set()) if str(item).strip()}

    procurement_tracking_number = order.procurement_tracking_number
    if not str(procurement_tracking_number).strip():
        procurement_tracking_number = " / ".join(
            str(item.tracking_number).strip()
            for item in order.procurement_items
            if str(item.tracking_number).strip()
        )

    source_fields = {
        "店铺": shop_name,
        "平台": order.platform,
        "订单编号": order.order_id,
        "备注": order.delivery_note,
        "订单日期": placed_at.strftime("%Y/%m/%d"),
        "下单时间": placed_at.strftime("%H:%M:%S"),
        "订单状态": order.order_status,
        "商品名称": order.product_name,
        "规格": order.specification,
        "SKU": order.sku,
        "SKU 图片": order.sku_image_path,
        "数量": order.quantity,
        "收件人": order.recipient_name,
        "手机号": order.phone_number,
        "编号": order.code,
        "收入": order.income_amount,
        "发货地址": f"{order.recipient_name} {order.phone_number}-{order.code} {order.address}",
        "采购快递单号": procurement_tracking_number,
        "采购快递单号1": "",
        "采购快递单号2": "",
        "采购快递单号3": "",
        "价格": order.order_amount,
        "平台扣点比例": order.platform_fee_rate,
        "平台扣点金额": order.platform_fee_amount,
        "其他成本": order.other_cost,
        "采购总成本": order.procurement_total_cost,
        "毛利润": order.gross_profit,
        "自定义字段1": order.custom_cost_values[0],
        "自定义字段2": order.custom_cost_values[1],
        "自定义字段3": order.custom_cost_values[2],
        "同步方式": sync_source,
        "同步状态": sync_status,
        "同步说明": sync_message,
        "录入时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    for index, item in enumerate(order.procurement_items, start=1):
        source_fields[f"采购商品{index}"] = item.product_name
        source_fields[f"采购数量{index}"] = item.quantity
        source_fields[f"采购成本{index}"] = item.cost
        source_fields[f"采购快递单号{index}"] = item.tracking_number

    payload: dict[str, object] = {}
    for source_name, value in source_fields.items():
        target_name = str(mapping.get(source_name, "")).strip()
        if not target_name:
            continue
        if source_name == "SKU 图片":
            image_path = str(value).strip()
            if not image_path:
                continue
            payload[target_name] = [{"local_path": image_path}]
            continue
        text_value = str(value).strip()
        if not text_value and source_name not in blank_source_fields:
            continue
        payload[target_name] = text_value
    return payload


def _parse_placed_at(value: str) -> datetime:
    text = str(value or "").strip()
    for pattern in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(text, pattern)
        except ValueError:
            continue
    raise ValueError("placed_at must be in 'YYYY-MM-DD HH:MM:SS' format")


class OrderPipeline:
    def __init__(self, ocr_client, helper_client, feishu_client, *, image_splitter=None):
        self.ocr_client = ocr_client
        self.helper_client = helper_client
        self.feishu_client = feishu_client
        self.image_splitter = image_splitter if image_splitter is not None else OrderImageSplitter()

    def extract_order(
        self,
        image_bytes: bytes,
        on_progress: callable | None = None,
    ) -> ParsedOrder:
        _emit_progress(on_progress, "OCR识别中...")
        ocr_text = self.ocr_client.extract_text(image_bytes)
        _emit_progress(on_progress, "辅助整理中...")
        helper_text = self.helper_client.enrich_text(ocr_text)
        try:
            _emit_progress(on_progress, "解析订单中...")
            return parse_order_text(helper_text)
        except ValueError as exc:
            _emit_progress(on_progress, "截图字段不完整，正在尽量补齐...")
            partial_order = _build_partial_order_from_text(helper_text)
            if partial_order is None:
                raise exc
            return partial_order

    def extract_order_batch(
        self,
        image_bytes: bytes,
        on_progress: callable | None = None,
    ) -> list[dict]:
        chunks = self._split_multi_order_image(image_bytes)
        if len(chunks) >= 2:
            _emit_progress(on_progress, f"检测到多单截图，正在切成 {len(chunks)} 单...")
            return self._extract_order_chunks(chunks, on_progress)

        _emit_progress(on_progress, "OCR识别中...")
        ocr_text = self.ocr_client.extract_text(image_bytes)
        _emit_progress(on_progress, "辅助整理中...")
        helper_text = self.helper_client.enrich_text(ocr_text)
        _emit_progress(on_progress, "解析订单中...")
        return _parse_helper_text_to_batch_results(helper_text)

    def _split_multi_order_image(self, image_bytes: bytes) -> list:
        if self.image_splitter is None:
            return []
        try:
            return list(self.image_splitter.split(image_bytes))
        except Exception:
            return []

    def _extract_order_chunks(
        self,
        chunks: list,
        on_progress: callable | None = None,
    ) -> list[dict]:
        results: list[dict] = []
        total = len(chunks)
        next_index = 1
        for position, chunk in enumerate(chunks, start=1):
            _emit_progress(on_progress, f"正在识别第 {position}/{total} 单...")
            try:
                ocr_text = self.ocr_client.extract_text(chunk.image_bytes)
                _emit_progress(on_progress, "辅助整理中...")
                helper_text = self.helper_client.enrich_text(ocr_text)
                _emit_progress(on_progress, "解析订单中...")
                parsed_items = _parse_helper_text_to_batch_results(helper_text)
            except Exception as exc:  # noqa: BLE001 - one bad chunk must not stop the batch.
                _emit_progress(on_progress, f"第 {position} 单识别失败，可重试或手动补录")
                results.append(
                    {
                        "index": next_index,
                        "ok": False,
                        "raw_text": "",
                        "order": None,
                        "source_image_bytes": chunk.image_bytes,
                        "error": f"第 {position} 单识别失败：{exc}；可重试或手动补录",
                    }
                )
                next_index += 1
                continue

            for item in parsed_items:
                result = dict(item)
                result["index"] = next_index
                result["source_image_bytes"] = chunk.image_bytes
                results.append(result)
                next_index += 1
        return results

    def build_feishu_payload(
        self,
        order: ParsedOrder,
        field_mapping: dict[str, str] | None = None,
        **kwargs,
    ) -> dict[str, str]:
        return build_feishu_payload(order, field_mapping, **kwargs)

    def submit_order(
        self,
        access_token: str,
        order: ParsedOrder,
        field_mapping: dict[str, str] | None = None,
        **kwargs,
    ) -> dict:
        if self.feishu_client is None:
            raise ValueError("missing feishu client")
        return self.feishu_client.create_record(
            access_token,
            build_feishu_payload(order, field_mapping, **kwargs),
        )


def _build_partial_order_from_text(raw_text: str) -> ParsedOrder | None:
    patch = {
        key: value
        for key, value in parse_supplemental_order_text(raw_text).items()
        if str(value).strip()
    }
    meaningful_keys = {
        "order_id",
        "placed_at",
        "order_status",
        "product_name",
        "specification",
        "quantity",
        "order_amount",
        "income_amount",
        "recipient_name",
        "phone_number",
        "code",
        "address",
        "delivery_note",
    }
    if not meaningful_keys & set(patch):
        return None
    return ParsedOrder(
        order_id=patch.get("order_id", ""),
        placed_at=patch.get("placed_at", ""),
        order_status=patch.get("order_status", ""),
        product_name=patch.get("product_name", ""),
        specification=patch.get("specification", ""),
        sku=patch.get("sku", ""),
        quantity=patch.get("quantity", ""),
        order_amount=patch.get("order_amount", ""),
        income_amount=patch.get("income_amount", ""),
        recipient_name=patch.get("recipient_name", ""),
        phone_number=patch.get("phone_number", ""),
        code=patch.get("code", ""),
        address=patch.get("address", ""),
        delivery_note=patch.get("delivery_note", ""),
        platform=patch.get("platform", "") or _detect_platform(raw_text),
    )


def _parse_helper_text_to_batch_results(helper_text: str) -> list[dict]:
    results = parse_order_text_batch(helper_text)
    if results:
        return [_with_partial_order_fallback(item) for item in results]
    try:
        order = parse_order_text(helper_text)
    except ValueError as exc:
        partial_order = _build_partial_order_from_text(helper_text)
        if partial_order is None:
            return [
                {
                    "index": 1,
                    "ok": False,
                    "raw_text": helper_text,
                    "order": None,
                    "error": f"解析失败：{exc}",
                }
            ]
        order = partial_order
    return [
        {
            "index": 1,
            "ok": True,
            "raw_text": helper_text,
            "order": order,
            "error": "",
        }
    ]


def _with_partial_order_fallback(item: dict) -> dict:
    if not isinstance(item, dict) or item.get("ok") is not False:
        return item
    partial_order = _build_partial_order_from_text(str(item.get("raw_text", "")))
    if partial_order is None:
        return item
    updated = dict(item)
    updated["ok"] = True
    updated["order"] = partial_order
    updated["error"] = ""
    return updated


def _emit_progress(on_progress, message: str) -> None:
    if on_progress is None:
        return
    on_progress(str(message))
