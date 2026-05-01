from __future__ import annotations

import hashlib
import threading
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse
from xml.etree import ElementTree


@dataclass(frozen=True)
class WechatCallbackRequest:
    account_id: str
    sender_id: str
    message_type: str
    message_id: str
    created_at: str
    recognized_text: str = ""
    image_url: str = ""
    media_id: str = ""
    source: str = "wechat_official_account"
    raw_payload: dict[str, str] = field(default_factory=dict)

    def to_mobile_order_payload(self) -> dict[str, str]:
        return {
            "text": self.recognized_text,
            "image_url": self.image_url,
        }


@dataclass(frozen=True)
class WechatCallbackResult:
    request: WechatCallbackRequest
    response_xml: str


class WechatCallbackService:
    def __init__(
        self,
        *,
        token: str,
        mobile_order_service: Any | None = None,
        callback_path: str = "/wechat/callback",
    ):
        self.token = str(token or "").strip()
        self.mobile_order_service = mobile_order_service
        normalized_callback_path = str(callback_path or "").strip() or "/wechat/callback"
        self.callback_path = (
            normalized_callback_path
            if normalized_callback_path.startswith("/")
            else f"/{normalized_callback_path}"
        )

    def is_valid_signature(self, *, signature: str, timestamp: str, nonce: str) -> bool:
        if not self.token:
            return False
        cleaned_signature = str(signature or "").strip()
        cleaned_timestamp = str(timestamp or "").strip()
        cleaned_nonce = str(nonce or "").strip()
        if not cleaned_signature or not cleaned_timestamp or not cleaned_nonce:
            return False
        expected = _build_signature(self.token, cleaned_timestamp, cleaned_nonce)
        return cleaned_signature == expected

    def verify_server(
        self,
        *,
        signature: str,
        timestamp: str,
        nonce: str,
        echostr: str,
    ) -> str:
        if not self.is_valid_signature(signature=signature, timestamp=timestamp, nonce=nonce):
            raise ValueError("invalid signature")
        return str(echostr or "")

    def parse_callback_xml(self, xml_text: str) -> WechatCallbackRequest:
        try:
            root = ElementTree.fromstring(str(xml_text or "").strip())
        except ElementTree.ParseError as exc:
            raise ValueError("invalid_xml") from exc
        if root.tag != "xml":
            raise ValueError("invalid_xml")

        payload = {child.tag: _xml_text(child.text) for child in list(root)}
        message_type = payload.get("MsgType", "")
        if message_type == "event":
            return WechatCallbackRequest(
                account_id=payload.get("ToUserName", ""),
                sender_id=payload.get("FromUserName", ""),
                message_type=message_type,
                message_id=payload.get("MsgId", ""),
                created_at=payload.get("CreateTime", ""),
                recognized_text=payload.get("Event", ""),
                image_url="",
                media_id="",
                raw_payload=payload,
            )
        if message_type not in {"text", "image"}:
            raise ValueError("unsupported_message_type")

        return WechatCallbackRequest(
            account_id=payload.get("ToUserName", ""),
            sender_id=payload.get("FromUserName", ""),
            message_type=message_type,
            message_id=payload.get("MsgId", ""),
            created_at=payload.get("CreateTime", ""),
            recognized_text=payload.get("Content", "") if message_type == "text" else "",
            image_url=payload.get("PicUrl", "") if message_type == "image" else "",
            media_id=payload.get("MediaId", "") if message_type == "image" else "",
            raw_payload=payload,
        )

    def handle_message(
        self,
        *,
        signature: str,
        timestamp: str,
        nonce: str,
        xml_text: str,
    ) -> WechatCallbackResult:
        if not self.is_valid_signature(signature=signature, timestamp=timestamp, nonce=nonce):
            raise ValueError("invalid signature")
        request = self.parse_callback_xml(xml_text)
        if request.message_type == "event":
            return WechatCallbackResult(
                request=request,
                response_xml=self.build_text_response(
                    request,
                    "草莓已连接公众号，发送订单文字或截图即可识别并生成待确认草稿。",
                ),
            )
        result = self._process_request(request)
        return WechatCallbackResult(
            request=request,
            response_xml=self.build_result_response(request, result),
        )

    def preview_message(
        self,
        request: WechatCallbackRequest,
        *,
        shop_name: str = "",
        platform: str = "",
    ) -> dict[str, Any]:
        if self.mobile_order_service is None:
            raise ValueError("missing_mobile_order_service")
        return self.mobile_order_service.preview(
            request.recognized_text,
            shop_name=shop_name,
            platform=platform,
            image_url=request.image_url,
        )

    def create_draft_from_message(
        self,
        request: WechatCallbackRequest,
        *,
        shop_name: str = "",
        platform: str = "",
    ) -> dict[str, Any]:
        if self.mobile_order_service is None:
            raise ValueError("missing_mobile_order_service")
        return self.mobile_order_service.create_draft(
            request.recognized_text,
            shop_name=shop_name,
            platform=platform,
            image_url=request.image_url,
        )

    def preview_batch_message(
        self,
        request: WechatCallbackRequest,
        *,
        shop_name: str = "",
        platform: str = "",
    ) -> dict[str, Any]:
        if self.mobile_order_service is None:
            raise ValueError("missing_mobile_order_service")
        preview_batch = getattr(self.mobile_order_service, "preview_batch", None)
        if not callable(preview_batch):
            return self.create_draft_from_message(
                request,
                shop_name=shop_name,
                platform=platform,
            )
        return preview_batch(
            request.recognized_text,
            shop_name=shop_name,
            platform=platform,
            image_url=request.image_url,
        )

    def build_text_response(self, request: WechatCallbackRequest, message: str) -> str:
        return (
            "<xml>"
            f"<ToUserName><![CDATA[{request.sender_id}]]></ToUserName>"
            f"<FromUserName><![CDATA[{request.account_id}]]></FromUserName>"
            "<CreateTime>0</CreateTime>"
            "<MsgType><![CDATA[text]]></MsgType>"
            f"<Content><![CDATA[{message}]]></Content>"
            "</xml>"
        )

    def build_result_response(
        self,
        request: WechatCallbackRequest,
        result: dict[str, Any],
    ) -> str:
        lines: list[str] = []
        if result.get("batch_preview"):
            if result.get("ok"):
                total = _safe_int(result.get("total")) or len(result.get("orders") or [])
                lines.append(f"草莓识别到 {total} 单，请打开手机助手确认后批量创建草稿。")
                for item in list(result.get("orders") or [])[:5]:
                    lines.extend(_format_batch_order_summary(item))
                if _batch_has_missing_fields(result):
                    lines.append("提醒：有订单信息不完整，回电脑确认。")
            else:
                warnings = [str(item).strip() for item in result.get("warnings", []) if str(item).strip()]
                if warnings:
                    lines.append("草莓暂时没识别完整：")
                    lines.extend(warnings[:3])
                else:
                    lines.append("草莓暂时没识别到有效订单信息，请换一张更清晰的图或直接发文字。")
        elif result.get("ok"):
            lines.append("草莓已识别，并已生成待确认草稿。")
            output_one = str(result.get("output_one", "")).strip()
            output_two = str(result.get("output_two", "")).strip()
            if output_one:
                lines.append(f"结果一：{output_one}")
            if output_two:
                lines.append(f"结果二：{output_two}")
            draft_record_id = str(result.get("draft_record_id", "")).strip()
            if draft_record_id:
                lines.append(f"草稿编号：{draft_record_id}")
            if result.get("missing_fields"):
                lines.append("提醒：这单信息还不完整，回电脑确认后再写飞书。")
        else:
            warnings = [str(item).strip() for item in result.get("warnings", []) if str(item).strip()]
            if warnings:
                lines.append("草莓暂时没识别完整：")
                lines.extend(warnings[:3])
            else:
                lines.append("草莓暂时没识别到有效订单信息，请换一张更清晰的图或直接发文字。")
        return self.build_text_response(request, "\n".join(lines))

    def _process_request(self, request: WechatCallbackRequest) -> dict[str, Any]:
        if self.mobile_order_service is None:
            return {
                "ok": False,
                "warnings": ["草莓系统暂未接好公众号录单服务，请稍后再试。"],
            }
        batch_preview = self.preview_batch_message(request, platform="微信小店")
        total = _safe_int(batch_preview.get("total")) or len(batch_preview.get("orders") or [])
        if total > 1:
            return {**batch_preview, "batch_preview": True}
        return self.create_draft_from_message(request, platform="微信小店")


class WechatCallbackHttpServer:
    def __init__(
        self,
        service: WechatCallbackService,
        *,
        host: str = "127.0.0.1",
        port: int = 0,
    ):
        self.service = service
        self.host = host
        self.port = port
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
        handler = _make_handler(self.service)
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


def _make_handler(service: WechatCallbackService) -> type[BaseHTTPRequestHandler]:
    class WechatCallbackRequestHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - stdlib callback name
            parsed = urlparse(self.path)
            if parsed.path != service.callback_path:
                self._send_text(404, "not found")
                return
            query = _parse_query(parsed.query)
            try:
                body = service.verify_server(
                    signature=query.get("signature", ""),
                    timestamp=query.get("timestamp", ""),
                    nonce=query.get("nonce", ""),
                    echostr=query.get("echostr", ""),
                )
            except ValueError as exc:
                self._send_text(401, str(exc))
                return
            self._send_text(200, body)

        def do_POST(self) -> None:  # noqa: N802 - stdlib callback name
            parsed = urlparse(self.path)
            if parsed.path != service.callback_path:
                self._send_text(404, "not found")
                return
            query = _parse_query(parsed.query)
            content_length = int(self.headers.get("Content-Length", "0") or "0")
            xml_text = self.rfile.read(content_length).decode("utf-8")
            try:
                result = service.handle_message(
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

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            return

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

    return WechatCallbackRequestHandler


def _build_signature(token: str, timestamp: str, nonce: str) -> str:
    parts = sorted([str(token), str(timestamp), str(nonce)])
    return hashlib.sha1("".join(parts).encode("utf-8")).hexdigest()


def _parse_query(query: str) -> dict[str, str]:
    return {
        key: values[0].strip()
        for key, values in parse_qs(query, keep_blank_values=True).items()
        if values
    }


def _xml_text(value: str | None) -> str:
    return str(value or "").strip()


def _format_batch_order_summary(item: Any) -> list[str]:
    if not isinstance(item, dict):
        return []
    index = _safe_int(item.get("index")) or 1
    order_preview = item.get("order_preview") if isinstance(item.get("order_preview"), dict) else {}
    order_id = str(order_preview.get("order_id", "")).strip()
    tail = order_id[-4:] if order_id else "-"
    recipient_name = str(order_preview.get("recipient_name", "")).strip() or "-"
    output_one = _short_text(item.get("output_one"), limit=34)
    output_two = _short_text(item.get("output_two"), limit=30)
    lines = [f"{index}. 订单尾号：{tail}，收件人：{recipient_name}"]
    result_parts: list[str] = []
    if output_one:
        result_parts.append(f"结果一：{output_one}")
    if output_two:
        result_parts.append(f"结果二：{output_two}")
    if result_parts:
        lines.append("；".join(result_parts))
    elif item.get("warnings"):
        warning = _short_text((item.get("warnings") or [""])[0], limit=34)
        if warning:
            lines.append(f"提醒：{warning}")
    return lines[:2]


def _batch_has_missing_fields(result: dict[str, Any]) -> bool:
    if result.get("missing_fields"):
        return True
    for item in result.get("orders") or []:
        if isinstance(item, dict) and item.get("missing_fields"):
            return True
    return False


def _short_text(value: Any, *, limit: int) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return f"{text[:limit - 1]}…"


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
