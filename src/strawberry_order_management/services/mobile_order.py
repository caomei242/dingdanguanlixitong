from __future__ import annotations

import base64
import binascii
import html
import json
import threading
from dataclasses import asdict
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
import urllib.request
from urllib.parse import parse_qs, urlparse

from strawberry_order_management.extractors.address import extract_address_payload
from strawberry_order_management.extractors.multi_order import parse_order_text_batch
from strawberry_order_management.extractors.supplemental_order import parse_supplemental_order_text
from strawberry_order_management.history import HistoryStore
from strawberry_order_management.models import ParsedOrder, ProcurementItem
from strawberry_order_management.services.auto_order import normalize_procurement_items
from strawberry_order_management.services.wechat_callback import WechatCallbackService


_ORDER_FIELDS = (
    "order_id",
    "placed_at",
    "order_status",
    "product_name",
    "specification",
    "sku",
    "quantity",
    "order_amount",
    "income_amount",
    "recipient_name",
    "phone_number",
    "code",
    "address",
    "delivery_note",
)
_REQUIRED_PREVIEW_FIELDS = (
    "order_id",
    "placed_at",
    "order_status",
    "product_name",
    "quantity",
    "order_amount",
    "income_amount",
    "recipient_name",
    "phone_number",
    "address",
)


class MobileOrderService:
    def __init__(
        self,
        history_store: HistoryStore,
        *,
        default_shop_name: str = "",
        default_platform: str = "",
        procurement_templates: list[dict[str, Any]] | None = None,
        order_pipeline: Any = None,
    ):
        self.history_store = history_store
        self._draft_lock = threading.Lock()
        self.default_shop_name = _text(default_shop_name)
        self.default_platform = _text(default_platform)
        self.procurement_templates = list(procurement_templates or [])
        self.order_pipeline = order_pipeline

    def preview(
        self,
        text: str,
        *,
        shop_name: str = "",
        platform: str = "",
        image_base64: str = "",
        image_data_url: str = "",
        image_url: str = "",
        image_path: str = "",
    ) -> dict[str, Any]:
        warnings: list[str] = []
        raw_text = str(text or "").strip()
        image_bytes = _load_image_bytes(
            image_base64=image_base64,
            image_data_url=image_data_url,
            image_url=image_url,
            image_path=image_path,
        )
        patch: dict[str, str] = {}
        ocr_text = ""
        if image_bytes is not None:
            if self.order_pipeline is None:
                warnings.append("图片识别需要先在电脑端配置并启动草莓系统 OCR")
            else:
                try:
                    image_order = self.order_pipeline.extract_order(image_bytes)
                except Exception as exc:  # noqa: BLE001 - service must return a readable mobile error
                    warnings.append(f"图片识别失败：{exc}")
                else:
                    patch.update(_patch_from_order(image_order))
                    ocr_text = _order_to_mobile_ocr_text(image_order)
        if raw_text:
            patch.update(parse_supplemental_order_text(raw_text))
        output_one = ""
        output_two = ""

        address_payload = None
        if _has_recipient_patch(patch):
            try:
                address_payload = extract_address_payload(_address_text_from_patch(patch))
            except ValueError as exc:
                warnings.append(f"地址快照生成失败：{exc}")
        if address_payload is None and raw_text:
            try:
                address_payload = extract_address_payload(raw_text)
            except ValueError as exc:
                if not patch:
                    warnings.append(f"地址提取失败：{exc}")

        if address_payload is not None:
            output_one = address_payload.cleaned_text
            output_two = address_payload.delivery_note
            patch.setdefault("delivery_note", address_payload.delivery_note)
            patch.setdefault("code", address_payload.code)

        resolved_platform = _text(platform) or self.default_platform
        order = _parsed_order_from_patch(
            patch,
            platform=resolved_platform,
            procurement_templates=self.procurement_templates,
        )
        order_preview = _order_to_preview(order)
        missing_fields = [field for field in _REQUIRED_PREVIEW_FIELDS if not order_preview.get(field)]
        recognized = bool(output_one or output_two or any(str(value).strip() for value in patch.values()))
        if not recognized:
            warnings.append("未识别到订单、商品或收货信息")
        elif missing_fields:
            warnings.append("草稿信息不完整，请在电脑端确认补齐")

        return {
            "ok": recognized,
            "shop_name": _text(shop_name) or self.default_shop_name,
            "platform": order.platform,
            "output_one": output_one,
            "output_two": output_two,
            "recognized_text": ocr_text or raw_text,
            "order_preview": order_preview,
            "missing_fields": missing_fields,
            "warnings": warnings,
        }

    def create_draft(
        self,
        text: str,
        *,
        shop_name: str = "",
        platform: str = "",
        image_base64: str = "",
        image_data_url: str = "",
        image_url: str = "",
        image_path: str = "",
    ) -> dict[str, Any]:
        preview = self.preview(
            text,
            shop_name=shop_name,
            platform=platform,
            image_base64=image_base64,
            image_data_url=image_data_url,
            image_url=image_url,
            image_path=image_path,
        )
        if not preview["ok"]:
            return {**preview, "draft": None}

        with self._draft_lock:
            row = self.history_store.append(
                {
                    "shop_name": _text(shop_name) or self.default_shop_name,
                    "sync_source": "手机助手草稿",
                    "status": "待确认",
                    "message": "手机助手录入草稿，待电脑确认写入飞书",
                    "auto_order_status": "",
                    "auto_order_message": "",
                    "auto_order_last_run_at": "",
                    "auto_order_task_id": "",
                    "auto_order_task_status": "",
                    "auto_order_task_submitted_at": "",
                    "auto_order_task_last_polled_at": "",
                    "auto_order_debug": {},
                    "created_at": datetime.now().isoformat(timespec="seconds"),
                    "order_snapshot": preview["order_preview"],
                    "address_snapshot": {
                        "output_one": preview["output_one"],
                        "output_two": preview["output_two"],
                    },
                }
            )
        return {**preview, "draft": row, "draft_record_id": row.get("record_id", "")}

    def preview_batch(
        self,
        text: str,
        *,
        shop_name: str = "",
        platform: str = "",
        image_base64: str = "",
        image_data_url: str = "",
        image_url: str = "",
        image_path: str = "",
    ) -> dict[str, Any]:
        warnings: list[str] = []
        raw_text = str(text or "").strip()
        image_bytes = _load_image_bytes(
            image_base64=image_base64,
            image_data_url=image_data_url,
            image_url=image_url,
            image_path=image_path,
        )
        order_results: list[dict[str, Any]] = []
        if image_bytes is not None:
            if self.order_pipeline is None:
                warnings.append("图片识别需要先在电脑端配置并启动草莓系统 OCR")
            else:
                try:
                    extractor = getattr(self.order_pipeline, "extract_order_batch", None)
                    if callable(extractor):
                        order_results = list(extractor(image_bytes))
                    else:
                        order_results = [
                            {
                                "index": 1,
                                "ok": True,
                                "raw_text": "",
                                "order": self.order_pipeline.extract_order(image_bytes),
                                "error": "",
                            }
                        ]
                except Exception as exc:  # noqa: BLE001 - mobile endpoint should return readable errors
                    warnings.append(f"图片识别失败：{exc}")

        if raw_text:
            order_results.extend(parse_order_text_batch(raw_text))

        if not order_results and raw_text:
            order_results = [{"index": 1, "ok": False, "raw_text": raw_text, "order": None, "error": ""}]

        orders = [
            self._preview_batch_item(
                result,
                shop_name=shop_name,
                platform=platform,
            )
            for result in order_results
        ]
        recognized_count = sum(1 for item in orders if item.get("ok"))
        if not orders and not warnings:
            warnings.append("未识别到订单、商品或收货信息")

        return {
            "ok": recognized_count > 0,
            "shop_name": _text(shop_name) or self.default_shop_name,
            "platform": _text(platform) or self.default_platform,
            "total": len(orders),
            "recognized_count": recognized_count,
            "orders": orders,
            "warnings": warnings,
        }

    def create_drafts_batch(
        self,
        text: str,
        *,
        shop_name: str = "",
        platform: str = "",
        image_base64: str = "",
        image_data_url: str = "",
        image_url: str = "",
        image_path: str = "",
        selected_indexes: list[int] | None = None,
    ) -> dict[str, Any]:
        preview = self.preview_batch(
            text,
            shop_name=shop_name,
            platform=platform,
            image_base64=image_base64,
            image_data_url=image_data_url,
            image_url=image_url,
            image_path=image_path,
        )
        selected = set(selected_indexes or [])
        if not selected:
            selected = {
                int(item["index"])
                for item in preview["orders"]
                if item.get("ok")
            }

        created = 0
        skipped = 0
        failed = 0
        orders: list[dict[str, Any]] = []
        with self._draft_lock:
            existing_order_ids = _existing_order_ids(self.history_store.list_items())
            for item in preview["orders"]:
                index = int(item["index"])
                item_result = dict(item)
                if index not in selected:
                    item_result["draft_status"] = "skipped"
                    item_result["draft_message"] = "未选择创建草稿"
                    skipped += 1
                    orders.append(item_result)
                    continue
                if not item.get("ok"):
                    item_result["draft_status"] = "failed"
                    item_result["draft_message"] = "订单信息未识别完整，未创建草稿"
                    failed += 1
                    orders.append(item_result)
                    continue
                order_preview = dict(item.get("order_preview") or {})
                order_id = _text(order_preview.get("order_id"))
                if order_id and order_id in existing_order_ids:
                    item_result["draft_status"] = "skipped"
                    item_result["draft_message"] = "历史里已有同订单号，已跳过"
                    skipped += 1
                    orders.append(item_result)
                    continue

                row = self.history_store.append(
                    {
                        "shop_name": _text(shop_name) or self.default_shop_name,
                        "sync_source": "手机助手批量草稿",
                        "status": "待确认",
                        "message": "手机助手批量录入草稿，待电脑确认写入飞书",
                        "auto_order_status": "",
                        "auto_order_message": "",
                        "auto_order_last_run_at": "",
                        "auto_order_task_id": "",
                        "auto_order_task_status": "",
                        "auto_order_task_submitted_at": "",
                        "auto_order_task_last_polled_at": "",
                        "auto_order_debug": {},
                        "created_at": datetime.now().isoformat(timespec="seconds"),
                        "order_snapshot": order_preview,
                        "address_snapshot": {
                            "output_one": item.get("output_one", ""),
                            "output_two": item.get("output_two", ""),
                        },
                    }
                )
                if order_id:
                    existing_order_ids.add(order_id)
                item_result["draft_status"] = "created"
                item_result["draft_message"] = "已创建待确认草稿"
                item_result["draft_record_id"] = row.get("record_id", "")
                created += 1
                orders.append(item_result)

        return {
            **preview,
            "ok": created > 0,
            "created_count": created,
            "skipped_count": skipped,
            "failed_count": failed,
            "orders": orders,
        }

    def _preview_batch_item(
        self,
        result: dict[str, Any],
        *,
        shop_name: str = "",
        platform: str = "",
    ) -> dict[str, Any]:
        warnings: list[str] = []
        raw_text = _text(result.get("raw_text"))
        order = result.get("order")
        patch = _patch_from_order(order) if isinstance(order, ParsedOrder) else {}
        if raw_text:
            patch.update(parse_supplemental_order_text(raw_text))

        output_one = ""
        output_two = ""
        address_payload = None
        if _has_recipient_patch(patch):
            try:
                address_payload = extract_address_payload(_address_text_from_patch(patch))
            except ValueError as exc:
                warnings.append(f"地址快照生成失败：{exc}")
        if address_payload is None and raw_text:
            try:
                address_payload = extract_address_payload(raw_text)
            except ValueError as exc:
                if not patch:
                    warnings.append(f"地址提取失败：{exc}")
        if address_payload is not None:
            output_one = address_payload.cleaned_text
            output_two = address_payload.delivery_note
            patch.setdefault("delivery_note", address_payload.delivery_note)
            patch.setdefault("code", address_payload.code)

        resolved_platform = _text(platform) or self.default_platform
        parsed_order = _parsed_order_from_patch(
            patch,
            platform=resolved_platform,
            procurement_templates=self.procurement_templates,
        )
        order_preview = _order_to_preview(parsed_order)
        missing_fields = [field for field in _REQUIRED_PREVIEW_FIELDS if not order_preview.get(field)]
        if missing_fields:
            warnings.append("草稿信息不完整，请在电脑端确认补齐")
        error = _text(result.get("error"))
        if error:
            warnings.append(error)
        ok = bool(output_one or output_two or any(str(value).strip() for value in patch.values()))
        return {
            "index": int(result.get("index") or 1),
            "ok": ok,
            "shop_name": _text(shop_name) or self.default_shop_name,
            "platform": parsed_order.platform,
            "output_one": output_one,
            "output_two": output_two,
            "recognized_text": _order_to_mobile_ocr_text(order) if isinstance(order, ParsedOrder) else raw_text,
            "order_preview": order_preview,
            "missing_fields": missing_fields,
            "warnings": warnings,
        }


class MobileOrderHttpServer:
    def __init__(
        self,
        service: MobileOrderService,
        *,
        api_key: str,
        host: str = "127.0.0.1",
        port: int = 0,
        wechat_callback_service: WechatCallbackService | None = None,
    ):
        self.service = service
        self.api_key = str(api_key or "")
        self.host = host
        self.port = port
        self.wechat_callback_service = wechat_callback_service
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def base_url(self) -> str:
        if self._server is None:
            return f"http://{self.host}:{self.port}"
        host, port = self._server.server_address[:2]
        return f"http://{host}:{port}"

    def start(self) -> None:
        if self._server is not None:
            return
        handler = _make_handler(
            self.service,
            self.api_key,
            wechat_callback_service=self.wechat_callback_service,
        )
        self._server = ThreadingHTTPServer((self.host, self.port), handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._server is None:
            return
        self._server.shutdown()
        self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=2)
        self._server = None
        self._thread = None


def _make_handler(
    service: MobileOrderService,
    api_key: str,
    *,
    wechat_callback_service: WechatCallbackService | None = None,
) -> type[BaseHTTPRequestHandler]:
    class MobileOrderRequestHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - stdlib callback name
            parsed = urlparse(self.path)
            if parsed.path.rstrip("/") in {"", "/mobile"}:
                self._send_html(200, _build_mobile_entry_html(service))
                return
            if (
                wechat_callback_service is not None
                and parsed.path == wechat_callback_service.callback_path
            ):
                query = _query_mapping(parsed.query)
                try:
                    body = wechat_callback_service.verify_server(
                        signature=query.get("signature", ""),
                        timestamp=query.get("timestamp", ""),
                        nonce=query.get("nonce", ""),
                        echostr=query.get("echostr", ""),
                    )
                except ValueError as exc:
                    self._send_text(401, str(exc))
                    return
                self._send_text(200, body)
                return
            self._send_json(404, {"ok": False, "error": "not_found"})

        def do_POST(self) -> None:  # noqa: N802 - stdlib callback name
            parsed = urlparse(self.path)
            if (
                wechat_callback_service is not None
                and parsed.path == wechat_callback_service.callback_path
            ):
                content_length = int(self.headers.get("Content-Length", "0") or "0")
                xml_text = self.rfile.read(content_length).decode("utf-8")
                query = _query_mapping(parsed.query)
                try:
                    result = wechat_callback_service.handle_message(
                        signature=query.get("signature", ""),
                        timestamp=query.get("timestamp", ""),
                        nonce=query.get("nonce", ""),
                        xml_text=xml_text,
                    )
                except ValueError as exc:
                    status = 401 if str(exc) == "invalid signature" else 400
                    self._send_text(status, str(exc))
                    return
                self._send_xml(200, result.response_xml)
                return
            if not _is_authorized(self.headers.get("Authorization", ""), api_key):
                self._send_json(401, {"ok": False, "error": "unauthorized"})
                return
            if parsed.path not in {
                "/mobile/orders/preview",
                "/mobile/orders/drafts",
                "/mobile/orders/preview-batch",
                "/mobile/orders/drafts-batch",
            }:
                self._send_json(404, {"ok": False, "error": "not_found"})
                return
            try:
                payload = self._read_json()
                response = _dispatch_request(service, parsed.path, payload)
            except ValueError as exc:
                self._send_json(400, {"ok": False, "error": str(exc)})
                return
            self._send_json(200, response)

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            return

        def _read_json(self) -> dict[str, Any]:
            content_length = int(self.headers.get("Content-Length", "0") or "0")
            raw_body = self.rfile.read(content_length)
            try:
                payload = json.loads(raw_body.decode("utf-8") or "{}")
            except json.JSONDecodeError as exc:
                raise ValueError("invalid_json") from exc
            if not isinstance(payload, dict):
                raise ValueError("json_body_must_be_object")
            return payload

        def _send_json(self, status: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_html(self, status: int, body: str) -> None:
            data = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _send_text(self, status: int, body: str) -> None:
            data = str(body).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _send_xml(self, status: int, body: str) -> None:
            data = str(body).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/xml; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    return MobileOrderRequestHandler


def _build_mobile_entry_html(service: MobileOrderService) -> str:
    default_shop = html.escape(service.default_shop_name or "")
    default_platform = html.escape(service.default_platform or "")
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <title>草莓手机助手录单</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f5f8ff;
      --card: rgba(255,255,255,0.92);
      --line: #d7e3ff;
      --text: #1f2f55;
      --muted: #7084b0;
      --primary: #5b7cff;
      --primary-strong: #3f67f5;
      --danger: #ff6d7a;
      --success: #14b86a;
      --shadow: 0 18px 40px rgba(91,124,255,0.12);
      font-family: "SF Pro Text","PingFang SC","Helvetica Neue",sans-serif;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background:
        radial-gradient(circle at top left, rgba(91,124,255,0.18), transparent 30%),
        linear-gradient(180deg, #f8fbff 0%, #eef4ff 100%);
      color: var(--text);
    }}
    .shell {{
      max-width: 760px;
      margin: 0 auto;
      padding: 16px 14px 40px;
    }}
    .hero, .card {{
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 22px;
      box-shadow: var(--shadow);
      backdrop-filter: blur(14px);
    }}
    .hero {{
      padding: 18px 18px 14px;
      margin-bottom: 14px;
    }}
    h1 {{
      margin: 0;
      font-size: 24px;
      line-height: 1.15;
    }}
    .sub {{
      margin-top: 6px;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.5;
    }}
    .card {{
      padding: 16px;
      margin-bottom: 14px;
    }}
    .grid {{
      display: grid;
      gap: 12px;
    }}
    .grid.two {{
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }}
    @media (max-width: 560px) {{
      .grid.two {{
        grid-template-columns: 1fr;
      }}
    }}
    label {{
      display: block;
      font-size: 13px;
      font-weight: 600;
      margin-bottom: 6px;
    }}
    input, textarea, button {{
      font: inherit;
    }}
    input[type="text"], textarea {{
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 12px 14px;
      color: var(--text);
      background: #fff;
      outline: none;
    }}
    input[type="text"]:focus, textarea:focus {{
      border-color: rgba(91,124,255,0.9);
      box-shadow: 0 0 0 4px rgba(91,124,255,0.12);
    }}
    textarea {{
      min-height: 144px;
      resize: vertical;
      line-height: 1.55;
    }}
    .file-input {{
      width: 100%;
      border: 1px dashed var(--line);
      border-radius: 14px;
      padding: 12px;
      background: rgba(91,124,255,0.04);
    }}
    .actions {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
      margin-top: 12px;
    }}
    button {{
      border: 0;
      border-radius: 14px;
      padding: 12px 14px;
      font-weight: 700;
      color: white;
      background: linear-gradient(135deg, var(--primary) 0%, var(--primary-strong) 100%);
      box-shadow: 0 10px 22px rgba(91,124,255,0.22);
    }}
    button.secondary {{
      color: var(--text);
      background: #fff;
      border: 1px solid var(--line);
      box-shadow: none;
    }}
    button:disabled {{
      opacity: 0.6;
    }}
    .hint {{
      margin-top: 8px;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.5;
    }}
    .status {{
      min-height: 20px;
      margin-top: 10px;
      font-size: 13px;
      color: var(--muted);
    }}
    .status.error {{ color: var(--danger); }}
    .status.success {{ color: var(--success); }}
    .result-box {{
      border: 1px solid var(--line);
      border-radius: 16px;
      background: #fff;
      padding: 12px 14px;
      min-height: 74px;
      white-space: pre-wrap;
      word-break: break-word;
      line-height: 1.6;
    }}
    .result-head {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 8px;
    }}
    .mini {{
      border: 1px solid var(--line);
      background: rgba(91,124,255,0.08);
      color: var(--primary-strong);
      padding: 6px 10px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 700;
      box-shadow: none;
    }}
    .list {{
      margin: 0;
      padding-left: 18px;
      color: var(--muted);
      line-height: 1.6;
      font-size: 13px;
    }}
    .preview {{
      display: grid;
      gap: 10px;
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }}
    .preview-item {{
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 10px 12px;
      background: rgba(255,255,255,0.86);
    }}
    .preview-item.wide {{
      grid-column: 1 / -1;
    }}
    .preview-item .k {{
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 4px;
    }}
    .preview-item .v {{
      font-size: 14px;
      line-height: 1.5;
      word-break: break-word;
    }}
    .batch-list {{
      display: grid;
      gap: 12px;
    }}
    .batch-order {{
      border: 1px solid var(--line);
      border-radius: 18px;
      background: rgba(255,255,255,0.88);
      padding: 12px;
    }}
    .batch-order-head {{
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 10px;
      margin-bottom: 10px;
    }}
    .batch-title {{
      font-size: 15px;
      font-weight: 800;
    }}
    .batch-meta {{
      color: var(--muted);
      font-size: 12px;
      line-height: 1.5;
      margin-top: 2px;
    }}
    .batch-toggle {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      color: var(--muted);
      font-size: 12px;
      white-space: nowrap;
    }}
    .batch-toggle input {{
      width: 18px;
      height: 18px;
    }}
    .batch-output {{
      border: 1px solid var(--line);
      border-radius: 14px;
      background: rgba(91,124,255,0.04);
      padding: 10px 12px;
      margin-top: 8px;
      line-height: 1.55;
      word-break: break-word;
      font-size: 13px;
    }}
    .batch-warning {{
      color: var(--danger);
      font-size: 12px;
      margin-top: 8px;
      line-height: 1.5;
    }}
    .hidden {{ display: none; }}
  </style>
</head>
<body>
  <div class="shell">
    <section class="hero">
      <h1>草莓手机助手录单</h1>
      <div class="sub">手机微信、爱马仕或浏览器都可以发文字/订单截图，先看结果一 / 结果二，再决定是否创建待确认草稿。</div>
    </section>

    <section class="card">
      <div class="grid two">
        <div>
          <label for="apiKey">API Key</label>
          <input id="apiKey" type="text" placeholder="第一次填一次，后面会自动记住">
        </div>
        <div>
          <label for="shopName">店铺</label>
          <input id="shopName" type="text" value="{default_shop}" placeholder="不填就走系统默认店铺">
        </div>
        <div>
          <label for="platform">平台</label>
          <input id="platform" type="text" value="{default_platform}" placeholder="不填就走系统默认平台">
        </div>
        <div>
          <label for="imageFile">订单截图</label>
          <input id="imageFile" class="file-input" type="file" accept="image/*">
        </div>
      </div>
      <div style="margin-top:12px;">
        <label for="orderText">订单文字</label>
        <textarea id="orderText" placeholder="可以直接粘贴收货信息、订单文字，也可以只传图片。"></textarea>
      </div>
      <div class="actions">
        <button id="previewButton" type="button">先识别看看</button>
        <button id="draftButton" type="button" class="secondary">创建待确认草稿</button>
      </div>
      <div id="status" class="status"></div>
      <div class="hint">建议流程：先点“先识别看看”，确认结果一 / 结果二没问题后，再点“创建待确认草稿”。</div>
    </section>

    <section id="resultCard" class="card hidden">
      <div class="grid">
        <div>
          <div class="result-head">
            <label style="margin:0;">结果一</label>
            <button class="mini" type="button" data-copy-target="outputOne">复制</button>
          </div>
          <div id="outputOne" class="result-box"></div>
        </div>
        <div>
          <div class="result-head">
            <label style="margin:0;">结果二</label>
            <button class="mini" type="button" data-copy-target="outputTwo">复制</button>
          </div>
          <div id="outputTwo" class="result-box"></div>
        </div>
      </div>
    </section>

    <section id="previewCard" class="card hidden">
      <div class="result-head">
        <label style="margin:0;">草稿预览</label>
        <span id="draftMeta" class="hint"></span>
      </div>
      <div id="previewGrid" class="preview"></div>
    </section>

    <section id="batchCard" class="card hidden">
      <div class="result-head">
        <label style="margin:0;">批量识别结果</label>
        <span id="batchMeta" class="hint"></span>
      </div>
      <div id="batchList" class="batch-list"></div>
    </section>

    <section id="warningsCard" class="card hidden">
      <label style="margin:0 0 8px 0;">提醒</label>
      <ul id="warningsList" class="list"></ul>
    </section>
  </div>

  <script>
    const apiKeyInput = document.getElementById('apiKey');
    const shopNameInput = document.getElementById('shopName');
    const platformInput = document.getElementById('platform');
    const imageFileInput = document.getElementById('imageFile');
    const orderTextInput = document.getElementById('orderText');
    const previewButton = document.getElementById('previewButton');
    const draftButton = document.getElementById('draftButton');
    const statusNode = document.getElementById('status');
    const resultCard = document.getElementById('resultCard');
    const previewCard = document.getElementById('previewCard');
    const warningsCard = document.getElementById('warningsCard');
    const batchCard = document.getElementById('batchCard');
    const outputOne = document.getElementById('outputOne');
    const outputTwo = document.getElementById('outputTwo');
    const previewGrid = document.getElementById('previewGrid');
    const batchList = document.getElementById('batchList');
    const batchMeta = document.getElementById('batchMeta');
    const warningsList = document.getElementById('warningsList');
    const draftMeta = document.getElementById('draftMeta');

    const storageKey = 'strawberry-mobile-order-api-key';
    apiKeyInput.value = localStorage.getItem(storageKey) || '';
    apiKeyInput.addEventListener('change', () => localStorage.setItem(storageKey, apiKeyInput.value.trim()));
    apiKeyInput.addEventListener('blur', () => localStorage.setItem(storageKey, apiKeyInput.value.trim()));

    document.querySelectorAll('[data-copy-target]').forEach((button) => {{
      button.addEventListener('click', async () => {{
        const target = document.getElementById(button.dataset.copyTarget);
        const text = target ? target.textContent || '' : '';
        if (!text.trim()) return;
        try {{
          await navigator.clipboard.writeText(text);
          setStatus('已复制', 'success');
        }} catch (_error) {{
          setStatus('复制失败，请手动长按复制', 'error');
        }}
      }});
    }});

    previewButton.addEventListener('click', () => submitForm('/mobile/orders/preview-batch'));
    draftButton.addEventListener('click', () => submitForm('/mobile/orders/drafts-batch'));

    function setStatus(text, tone = '') {{
      statusNode.textContent = text || '';
      statusNode.className = tone ? `status ${{tone}}` : 'status';
    }}

    async function readFileAsDataUrl(file) {{
      return await new Promise((resolve, reject) => {{
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result || ''));
        reader.onerror = () => reject(new Error('图片读取失败'));
        reader.readAsDataURL(file);
      }});
    }}

    function renderPreview(payload) {{
      if (Array.isArray(payload.orders)) {{
        renderBatchPreview(payload);
        return;
      }}
      outputOne.textContent = payload.output_one || '';
      outputTwo.textContent = payload.output_two || '';
      resultCard.classList.remove('hidden');

      previewGrid.innerHTML = '';
      const preview = payload.order_preview || {{}};
      const rows = [
        ['订单编号', preview.order_id],
        ['下单时间', preview.placed_at],
        ['订单状态', preview.order_status],
        ['平台', preview.platform],
        ['商品名称', preview.product_name, true],
        ['规格', preview.specification, true],
        ['数量', preview.quantity],
        ['订单金额', preview.order_amount],
        ['商家收入', preview.income_amount],
        ['收件人', preview.recipient_name],
        ['手机号', preview.phone_number],
        ['备注尾号', preview.code],
        ['收货地址', preview.address, true],
      ];
      rows.forEach(([label, value, wide]) => {{
        if (!String(value || '').trim()) return;
        const item = document.createElement('div');
        item.className = wide ? 'preview-item wide' : 'preview-item';
        item.innerHTML = `<div class="k">${{escapeHtml(label)}}</div><div class="v">${{escapeHtml(String(value))}}</div>`;
        previewGrid.appendChild(item);
      }});
      previewCard.classList.remove('hidden');

      warningsList.innerHTML = '';
      const warnings = [...(payload.warnings || [])];
      if ((payload.missing_fields || []).length) {{
        warnings.push('缺少字段：' + payload.missing_fields.join('、'));
      }}
      if (warnings.length) {{
        warnings.forEach((warning) => {{
          const li = document.createElement('li');
          li.textContent = warning;
          warningsList.appendChild(li);
        }});
        warningsCard.classList.remove('hidden');
      }} else {{
        warningsCard.classList.add('hidden');
      }}

      if (payload.draft_record_id) {{
        draftMeta.textContent = `已创建草稿：${{payload.draft_record_id}}`;
      }} else {{
        draftMeta.textContent = payload.ok ? '当前仅预览，尚未写入草稿' : '';
      }}
    }}

    function renderBatchPreview(payload) {{
      const orders = Array.isArray(payload.orders) ? payload.orders : [];
      batchList.innerHTML = '';
      resultCard.classList.add('hidden');
      previewCard.classList.add('hidden');
      batchMeta.textContent = `识别到 ${{payload.recognized_count || 0}} / ${{payload.total || orders.length}} 单`;

      orders.forEach((order) => {{
        const preview = order.order_preview || {{}};
        const card = document.createElement('div');
        card.className = 'batch-order';
        const warnings = [...(order.warnings || [])];
        if ((order.missing_fields || []).length) {{
          warnings.push('缺少字段：' + order.missing_fields.join('、'));
        }}
        const disabled = order.ok ? '' : 'disabled';
        const checked = order.ok && order.draft_status !== 'skipped' ? 'checked' : '';
        const draftMessage = order.draft_message ? `<div class="batch-warning">${{escapeHtml(order.draft_message)}}</div>` : '';
        const warningHtml = warnings.length
          ? `<div class="batch-warning">${{warnings.map((item) => escapeHtml(String(item))).join('；')}}</div>`
          : '';
        card.innerHTML = `
          <div class="batch-order-head">
            <div>
              <div class="batch-title">第${{order.index}}单 · ${{escapeHtml(preview.recipient_name || '未识别收件人')}}</div>
              <div class="batch-meta">订单 ${{escapeHtml(preview.order_id || '未识别')}} · 收入 ${{escapeHtml(preview.income_amount || '-')}}</div>
            </div>
            <label class="batch-toggle">
              <input type="checkbox" data-order-index="${{order.index}}" ${{checked}} ${{disabled}}>
              创建草稿
            </label>
          </div>
          <div class="batch-output"><b>结果一：</b>${{escapeHtml(order.output_one || '未生成')}}</div>
          <div class="batch-output"><b>结果二：</b>${{escapeHtml(order.output_two || '未生成')}}</div>
          ${{warningHtml}}
          ${{draftMessage}}
        `;
        batchList.appendChild(card);
      }});
      batchCard.classList.remove('hidden');

      warningsList.innerHTML = '';
      const warnings = [...(payload.warnings || [])];
      if (warnings.length) {{
        warnings.forEach((warning) => {{
          const li = document.createElement('li');
          li.textContent = warning;
          warningsList.appendChild(li);
        }});
        warningsCard.classList.remove('hidden');
      }} else {{
        warningsCard.classList.add('hidden');
      }}

      if (payload.created_count !== undefined) {{
        batchMeta.textContent = `已创建 ${{payload.created_count || 0}} 单，跳过 ${{payload.skipped_count || 0}} 单`;
      }} else {{
        draftMeta.textContent = payload.ok ? '当前仅预览，尚未写入草稿' : '';
      }}
    }}

    function escapeHtml(value) {{
      return value
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;');
    }}

    async function submitForm(path) {{
      const apiKey = apiKeyInput.value.trim();
      if (!apiKey) {{
        setStatus('请先填写 API Key', 'error');
        apiKeyInput.focus();
        return;
      }}
      const text = orderTextInput.value.trim();
      const file = imageFileInput.files && imageFileInput.files[0];
      if (!text && !file) {{
        setStatus('请至少提供订单文字或一张截图', 'error');
        return;
      }}
      previewButton.disabled = true;
      draftButton.disabled = true;
      setStatus(path.endsWith('/drafts-batch') ? '正在创建草稿…' : '正在识别…');
      try {{
        const payload = {{
          text,
          shop_name: shopNameInput.value.trim(),
          platform: platformInput.value.trim(),
        }};
        if (path.endsWith('/drafts-batch')) {{
          payload.selected_indexes = Array.from(document.querySelectorAll('[data-order-index]:checked'))
            .map((node) => Number(node.dataset.orderIndex))
            .filter((value) => Number.isFinite(value));
          if (document.querySelector('[data-order-index]') && payload.selected_indexes.length === 0) {{
            setStatus('请至少勾选一单再创建草稿', 'error');
            previewButton.disabled = false;
            draftButton.disabled = false;
            return;
          }}
        }}
        if (file) {{
          payload.image_data_url = await readFileAsDataUrl(file);
        }}
        const response = await fetch(path, {{
          method: 'POST',
          headers: {{
            'Authorization': `Bearer ${{apiKey}}`,
            'Content-Type': 'application/json',
          }},
          body: JSON.stringify(payload),
        }});
        const result = await response.json();
        if (!response.ok || !result.ok) {{
          const warnings = Array.isArray(result.warnings) ? result.warnings.join('；') : '';
          throw new Error(warnings || result.error || '识别失败');
        }}
        renderPreview(result);
        setStatus(path.endsWith('/drafts-batch') ? '草稿已写入历史，回电脑确认即可' : '识别完成', 'success');
      }} catch (error) {{
        setStatus(error instanceof Error ? error.message : '请求失败', 'error');
      }} finally {{
        previewButton.disabled = false;
        draftButton.disabled = false;
      }}
    }}
  </script>
</body>
</html>"""


def _dispatch_request(
    service: MobileOrderService,
    path: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    text = str(payload.get("text", ""))
    kwargs = {
        "shop_name": str(payload.get("shop_name", "")).strip(),
        "platform": str(payload.get("platform", "")).strip(),
        "image_base64": str(payload.get("image_base64", "")).strip(),
        "image_data_url": str(payload.get("image_data_url", "")).strip(),
        "image_url": str(payload.get("image_url", "")).strip(),
        "image_path": str(payload.get("image_path", "")).strip(),
    }
    if path == "/mobile/orders/preview":
        return service.preview(text, **kwargs)
    if path == "/mobile/orders/drafts":
        return service.create_draft(text, **kwargs)
    if path == "/mobile/orders/preview-batch":
        return service.preview_batch(text, **kwargs)
    selected_indexes = payload.get("selected_indexes")
    if selected_indexes is not None and not isinstance(selected_indexes, list):
        raise ValueError("selected_indexes_must_be_list")
    return service.create_drafts_batch(
        text,
        selected_indexes=[
            int(item)
            for item in (selected_indexes or [])
            if str(item).strip().isdigit()
        ],
        **kwargs,
    )


def _is_authorized(header_value: str, api_key: str) -> bool:
    expected = f"Bearer {api_key}"
    return bool(api_key) and str(header_value or "").strip() == expected


def _query_mapping(raw_query: str) -> dict[str, str]:
    return {
        key: values[0]
        for key, values in parse_qs(str(raw_query or ""), keep_blank_values=True).items()
        if key and values
    }


def _existing_order_ids(rows: list[dict[str, Any]]) -> set[str]:
    order_ids: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        order_snapshot = row.get("order_snapshot")
        if isinstance(order_snapshot, dict):
            order_id = _text(order_snapshot.get("order_id"))
            if order_id:
                order_ids.add(order_id)
                continue
        order_id = _text(row.get("order_id"))
        if order_id:
            order_ids.add(order_id)
    return order_ids


def _parsed_order_from_patch(
    patch: dict[str, str],
    *,
    platform: str = "",
    procurement_templates: list[dict[str, Any]] | None = None,
) -> ParsedOrder:
    specification = _text(patch.get("specification"))
    procurement_items = _procurement_items_from_template(specification, procurement_templates or [])
    return ParsedOrder(
        order_id=_text(patch.get("order_id")),
        placed_at=_text(patch.get("placed_at")),
        order_status=_text(patch.get("order_status")),
        product_name=_text(patch.get("product_name")),
        specification=specification,
        sku=_text(patch.get("sku")),
        quantity=_text(patch.get("quantity")),
        order_amount=_text(patch.get("order_amount")),
        income_amount=_text(patch.get("income_amount")),
        recipient_name=_text(patch.get("recipient_name")),
        phone_number=_text(patch.get("phone_number")),
        code=_text(patch.get("code")),
        address=_text(patch.get("address")),
        delivery_note=_text(patch.get("delivery_note")),
        platform=str(platform or "").strip() or "手机助手",
        procurement_items=tuple(procurement_items),
    )


def _patch_from_order(order: ParsedOrder) -> dict[str, str]:
    return {
        "order_id": _text(order.order_id),
        "placed_at": _text(order.placed_at),
        "order_status": _text(order.order_status),
        "product_name": _text(order.product_name),
        "specification": _text(order.specification),
        "sku": _text(order.sku),
        "quantity": _text(order.quantity),
        "order_amount": _text(order.order_amount),
        "income_amount": _text(order.income_amount),
        "recipient_name": _text(order.recipient_name),
        "phone_number": _text(order.phone_number),
        "code": _text(order.code),
        "address": _text(order.address),
        "delivery_note": _text(order.delivery_note),
    }


def _order_to_mobile_ocr_text(order: ParsedOrder) -> str:
    lines = []
    for label, value in (
        ("订单编号", order.order_id),
        ("下单时间", order.placed_at),
        ("订单状态", order.order_status),
        ("商品信息", order.product_name),
        ("规格", order.specification),
        ("数量", order.quantity),
        ("订单金额", order.order_amount),
        ("商家收入金额", order.income_amount),
        ("收货信息", _address_text_from_patch(_patch_from_order(order))),
    ):
        text = _text(value)
        if text:
            lines.append(f"{label} {text}")
    return "\n".join(lines)


def _load_image_bytes(
    *,
    image_base64: str = "",
    image_data_url: str = "",
    image_url: str = "",
    image_path: str = "",
) -> bytes | None:
    encoded = _text(image_base64) or _text(image_data_url)
    if encoded:
        if "," in encoded and encoded.lower().startswith("data:"):
            encoded = encoded.split(",", 1)[1]
        try:
            return base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ValueError("invalid_image_base64") from exc
    url = _text(image_url)
    if url:
        with urllib.request.urlopen(url, timeout=20) as response:
            return response.read()
    path = _text(image_path)
    if path:
        with open(path, "rb") as file:
            return file.read()
    return None


def _order_to_preview(order: ParsedOrder) -> dict[str, Any]:
    preview = asdict(order)
    preview["custom_cost_labels"] = list(order.custom_cost_labels)
    preview["custom_cost_values"] = list(order.custom_cost_values)
    preview["procurement_items"] = normalize_procurement_items(preview.get("procurement_items"))
    return preview


def _has_recipient_patch(patch: dict[str, str]) -> bool:
    return bool(
        _text(patch.get("recipient_name"))
        and _text(patch.get("phone_number"))
        and _text(patch.get("address"))
    )


def _address_text_from_patch(patch: dict[str, str]) -> str:
    name = _text(patch.get("recipient_name"))
    phone_number = _text(patch.get("phone_number"))
    address = "".join(_text(patch.get("address")).split())
    code = _text(patch.get("code"))
    if code:
        return f"{name}[{code}]{phone_number}{address}[{code}]"
    return f"{name}{phone_number}{address}"


def _procurement_items_from_template(
    specification: str,
    procurement_templates: list[dict[str, Any]],
) -> list[ProcurementItem]:
    template = _find_template_for_specification(specification, procurement_templates)
    items: list[ProcurementItem] = []
    for item in list((template or {}).get("procurement_items") or [])[:3]:
        if not isinstance(item, dict):
            continue
        items.append(
            ProcurementItem(
                _text(item.get("product_name")),
                _text(item.get("quantity")),
                _text(item.get("cost")),
                _text(item.get("tracking_number")),
                _text(item.get("jd_link")),
            )
        )
    while len(items) < 3:
        items.append(ProcurementItem("", "", "", "", ""))
    return items


def _find_template_for_specification(
    specification: str,
    procurement_templates: list[dict[str, Any]],
) -> dict[str, Any] | None:
    target = _normalize_specification_key(specification)
    if not target:
        return None
    for template in procurement_templates:
        if not isinstance(template, dict):
            continue
        if _normalize_specification_key(template.get("specification")) == target:
            return template
    return None


def _normalize_specification_key(value: Any) -> str:
    return "".join(_text(value).lower().split())


def _text(value: Any) -> str:
    return str(value or "").strip()
