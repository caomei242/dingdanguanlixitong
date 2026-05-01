from __future__ import annotations

import hashlib
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from strawberry_order_management.history import HistoryStore
from strawberry_order_management.services.mobile_order import MobileOrderService
from strawberry_order_management.services.wechat_callback import (
    WechatCallbackHttpServer,
    WechatCallbackRequest,
    WechatCallbackService,
)


def test_verify_server_returns_echo_string_for_valid_signature(tmp_path: Path):
    service = _build_service(tmp_path, token="wechat-secret")
    signature = _wechat_signature("wechat-secret", "1714108800", "nonce-1")

    result = service.verify_server(
        signature=signature,
        timestamp="1714108800",
        nonce="nonce-1",
        echostr="hello-wechat",
    )

    assert result == "hello-wechat"


def test_parse_text_message_builds_mobile_order_request(tmp_path: Path):
    service = _build_service(tmp_path)

    request = service.parse_callback_xml(
        """
        <xml>
          <ToUserName><![CDATA[gh_123]]></ToUserName>
          <FromUserName><![CDATA[user_open_id]]></FromUserName>
          <CreateTime>1714108800</CreateTime>
          <MsgType><![CDATA[text]]></MsgType>
          <Content><![CDATA[张春娜15789799611山西省太原市小店区北营街道富力金禧城A区5栋1单元2402]]></Content>
          <MsgId>1234567890</MsgId>
        </xml>
        """
    )

    assert request == WechatCallbackRequest(
        source="wechat_official_account",
        account_id="gh_123",
        sender_id="user_open_id",
        message_type="text",
        message_id="1234567890",
        created_at="1714108800",
        recognized_text="张春娜15789799611山西省太原市小店区北营街道富力金禧城A区5栋1单元2402",
        image_url="",
        media_id="",
        raw_payload={
            "ToUserName": "gh_123",
            "FromUserName": "user_open_id",
            "CreateTime": "1714108800",
            "MsgType": "text",
            "Content": "张春娜15789799611山西省太原市小店区北营街道富力金禧城A区5栋1单元2402",
            "MsgId": "1234567890",
        },
    )
    assert request.to_mobile_order_payload() == {
        "text": "张春娜15789799611山西省太原市小店区北营街道富力金禧城A区5栋1单元2402",
        "image_url": "",
    }


def test_parse_image_message_builds_mobile_order_request(tmp_path: Path):
    service = _build_service(tmp_path)

    request = service.parse_callback_xml(
        """
        <xml>
          <ToUserName><![CDATA[gh_123]]></ToUserName>
          <FromUserName><![CDATA[user_open_id]]></FromUserName>
          <CreateTime>1714108801</CreateTime>
          <MsgType><![CDATA[image]]></MsgType>
          <PicUrl><![CDATA[https://example.com/order.jpg]]></PicUrl>
          <MediaId><![CDATA[media-123]]></MediaId>
          <MsgId>1234567891</MsgId>
        </xml>
        """
    )

    assert request.message_type == "image"
    assert request.media_id == "media-123"
    assert request.image_url == "https://example.com/order.jpg"
    assert request.recognized_text == ""
    assert request.to_mobile_order_payload() == {
        "text": "",
        "image_url": "https://example.com/order.jpg",
    }


def test_preview_message_reuses_mobile_order_preview_chain(tmp_path: Path):
    service = _build_service(tmp_path)
    request = WechatCallbackRequest(
        source="wechat_official_account",
        account_id="gh_123",
        sender_id="user_open_id",
        message_type="text",
        message_id="1234567890",
        created_at="1714108800",
        recognized_text="张春娜[2666]15789799611山西省太原市小店区北营街道富力金禧城A区5栋1单元2402[2666]",
        raw_payload={},
    )

    result = service.preview_message(request, platform="微信小店")

    assert result["ok"] is True
    assert result["output_two"] == "请电话送货上门谢谢【2666】"
    assert result["order_preview"]["platform"] == "微信小店"


def test_batch_preview_response_does_not_create_draft_for_multiple_orders():
    mobile_order_service = BatchPreviewMobileOrderStub()
    service = WechatCallbackService(
        token="wechat-token",
        mobile_order_service=mobile_order_service,
    )
    request = WechatCallbackRequest(
        source="wechat_official_account",
        account_id="gh_123",
        sender_id="user_open_id",
        message_type="text",
        message_id="1234567890",
        created_at="1714108800",
        recognized_text="两单订单文字",
        raw_payload={},
    )

    result = service._process_request(request)
    response_xml = service.build_result_response(request, result)

    assert mobile_order_service.create_draft_calls == 0
    assert result["batch_preview"] is True
    assert "识别到 2 单" in response_xml
    assert "订单尾号：1234，收件人：张三" in response_xml
    assert "订单尾号：5678，收件人：李四" in response_xml
    assert "结果一：张三13800000000上海市浦东新区测试路1号" in response_xml
    assert "结果二：请电话送货上门谢谢【1234】" in response_xml


def test_http_get_returns_echostr_for_valid_signature(tmp_path: Path):
    server = WechatCallbackHttpServer(
        _build_service(tmp_path, token="wechat-secret"),
        host="127.0.0.1",
        port=0,
    )
    server.start()
    try:
        signature = _wechat_signature("wechat-secret", "1714108800", "nonce-1")
        query = urllib.parse.urlencode(
            {
                "signature": signature,
                "timestamp": "1714108800",
                "nonce": "nonce-1",
                "echostr": "hello-wechat",
            }
        )
        with urllib.request.urlopen(f"{server.base_url}/wechat/callback?{query}", timeout=2) as response:
            body = response.read().decode("utf-8")

        assert body == "hello-wechat"
    finally:
        server.stop()


def test_http_post_text_message_returns_result_xml_and_creates_draft(tmp_path: Path):
    server = WechatCallbackHttpServer(
        _build_service(tmp_path, token="wechat-secret"),
        host="127.0.0.1",
        port=0,
    )
    server.start()
    try:
        payload = """
        <xml>
          <ToUserName><![CDATA[gh_123]]></ToUserName>
          <FromUserName><![CDATA[user_open_id]]></FromUserName>
          <CreateTime>1714108800</CreateTime>
          <MsgType><![CDATA[text]]></MsgType>
          <Content><![CDATA[张春娜[2666]15789799611山西省太原市小店区北营街道富力金禧城A区5栋1单元2402[2666]]]></Content>
          <MsgId>1234567890</MsgId>
        </xml>
        """.strip().encode("utf-8")
        signature = _wechat_signature("wechat-secret", "1714108800", "nonce-2")
        url = (
            f"{server.base_url}/wechat/callback?"
            + urllib.parse.urlencode(
                {
                    "signature": signature,
                    "timestamp": "1714108800",
                    "nonce": "nonce-2",
                }
            )
        )
        request = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/xml"},
            method="POST",
        )

        with urllib.request.urlopen(request, timeout=2) as response:
            body = response.read().decode("utf-8")

        assert "<MsgType><![CDATA[text]]></MsgType>" in body
        assert "<ToUserName><![CDATA[user_open_id]]></ToUserName>" in body
        assert "<FromUserName><![CDATA[gh_123]]></FromUserName>" in body
        assert "草莓已识别，并已生成待确认草稿。" in body
        assert "结果一：张春娜15789799611山西省太原市小店区北营街道富力金禧城A区5栋1单元2402" in body
        assert "结果二：请电话送货上门谢谢【2666】" in body
        assert "草稿编号：" in body
    finally:
        server.stop()


def test_http_post_rejects_invalid_signature(tmp_path: Path):
    server = WechatCallbackHttpServer(
        _build_service(tmp_path, token="wechat-secret"),
        host="127.0.0.1",
        port=0,
    )
    server.start()
    try:
        request = urllib.request.Request(
            (
                f"{server.base_url}/wechat/callback?"
                + urllib.parse.urlencode(
                    {
                        "signature": "bad-signature",
                        "timestamp": "1714108800",
                        "nonce": "nonce-2",
                    }
                )
            ),
            data=b"<xml></xml>",
            headers={"Content-Type": "application/xml"},
            method="POST",
        )

        try:
            urllib.request.urlopen(request, timeout=2)
        except urllib.error.HTTPError as exc:
            assert exc.code == 401
            body = exc.read().decode("utf-8")
        else:
            raise AssertionError("request unexpectedly succeeded")

        assert body == "invalid signature"
    finally:
        server.stop()


def _build_service(tmp_path: Path, *, token: str = "wechat-token") -> WechatCallbackService:
    mobile_order_service = MobileOrderService(HistoryStore(tmp_path / "history.json"))
    return WechatCallbackService(token=token, mobile_order_service=mobile_order_service)


class BatchPreviewMobileOrderStub:
    def __init__(self):
        self.create_draft_calls = 0

    def preview_batch(self, text: str, *, shop_name: str = "", platform: str = "", image_url: str = "") -> dict:
        return {
            "ok": True,
            "total": 2,
            "recognized_count": 2,
            "orders": [
                {
                    "index": 1,
                    "ok": True,
                    "output_one": "张三13800000000上海市浦东新区测试路1号",
                    "output_two": "请电话送货上门谢谢【1234】",
                    "order_preview": {
                        "order_id": "2026042900001234",
                        "recipient_name": "张三",
                    },
                    "missing_fields": [],
                    "warnings": [],
                },
                {
                    "index": 2,
                    "ok": True,
                    "output_one": "李四13900000000杭州市西湖区测试路2号",
                    "output_two": "请电话送货上门谢谢【5678】",
                    "order_preview": {
                        "order_id": "2026042900005678",
                        "recipient_name": "李四",
                    },
                    "missing_fields": [],
                    "warnings": [],
                },
            ],
            "warnings": [],
        }

    def create_draft(self, *args, **kwargs) -> dict:
        self.create_draft_calls += 1
        return {"ok": True}


def _wechat_signature(token: str, timestamp: str, nonce: str) -> str:
    parts = sorted([token, timestamp, nonce])
    return hashlib.sha1("".join(parts).encode("utf-8")).hexdigest()
