from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
import base64
import hashlib
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from strawberry_order_management.history import HistoryStore
from strawberry_order_management.models import ParsedOrder
from strawberry_order_management.services.mobile_order import (
    MobileOrderHttpServer,
    MobileOrderService,
)
from strawberry_order_management.services.wechat_callback import WechatCallbackService


ADDRESS_TEXT = "张春娜[2666]15789799611山西省太原市小店区北营街道富力金禧城A区5栋1单元2402[2666]"


class ImagePipelineStub:
    def __init__(self):
        self.calls: list[bytes] = []

    def extract_order(self, image_bytes: bytes) -> ParsedOrder:
        self.calls.append(image_bytes)
        return ParsedOrder(
            order_id="3735824608022632960",
            placed_at="2026-04-20 09:55:00",
            order_status="已发货",
            product_name="【次日达】赵露丝同款27000合瓶盖澳大利亚进口婴儿水",
            specification="1L/瓶*12瓶",
            quantity="1",
            order_amount="355.00",
            income_amount="142.00",
            recipient_name="潇寒",
            phone_number="18401352224",
            code="9530",
            address="河北省石家庄市裕华区裕华区塔南路位同新村南区位同新村南区多层4幢1单元102",
            delivery_note="请电话送货上门谢谢【9530】",
            platform="微信小店",
        )


def test_preview_returns_address_outputs(tmp_path: Path):
    service = MobileOrderService(HistoryStore(tmp_path / "history.json"))

    result = service.preview(ADDRESS_TEXT, shop_name="乐宝零食店", platform="微信小店")

    assert result["ok"] is True
    assert result["output_one"] == "张春娜15789799611山西省太原市小店区北营街道富力金禧城A区5栋1单元2402"
    assert result["output_two"] == "请电话送货上门谢谢【2666】"
    assert result["order_preview"]["recipient_name"] == "张春娜"
    assert result["order_preview"]["phone_number"] == "15789799611"
    assert result["order_preview"]["code"] == "2666"
    assert result["order_preview"]["platform"] == "微信小店"


def test_create_draft_appends_history_without_feishu_or_auto_order(tmp_path: Path):
    store = HistoryStore(tmp_path / "history.json")
    service = MobileOrderService(store)

    result = service.create_draft(ADDRESS_TEXT, shop_name="乐宝零食店")

    assert result["ok"] is True
    assert result["draft"]["record_id"]
    row = store.list_items()[0]
    assert row["sync_source"] == "手机助手草稿"
    assert row["status"] == "待确认"
    assert row["message"] == "手机助手录入草稿，待电脑确认写入飞书"
    assert row["address_snapshot"]["output_one"] == result["output_one"]
    assert row["address_snapshot"]["output_two"] == result["output_two"]
    assert row["order_snapshot"]["recipient_name"] == "张春娜"
    assert "feishu_result" not in row
    assert row["auto_order_status"] == ""
    assert row["auto_order_task_id"] == ""


def test_missing_fields_are_reported_without_rejecting_address_draft(tmp_path: Path):
    service = MobileOrderService(HistoryStore(tmp_path / "history.json"))

    result = service.create_draft("张春娜15789799611山西省太原市小店区北营街道富力金禧城A区5栋1单元2402")

    assert result["ok"] is True
    assert result["draft"]["record_id"]
    assert "order_id" in result["missing_fields"]
    assert "product_name" in result["missing_fields"]
    assert "recipient_name" not in result["missing_fields"]
    assert result["warnings"]


def test_preview_accepts_image_base64_and_uses_strawberry_ocr_pipeline(tmp_path: Path):
    pipeline = ImagePipelineStub()
    service = MobileOrderService(HistoryStore(tmp_path / "history.json"), order_pipeline=pipeline)

    result = service.preview(
        "",
        image_base64=base64.b64encode(b"fake-image").decode("ascii"),
        shop_name="乐宝零食店--微信",
        platform="微信小店",
    )

    assert pipeline.calls == [b"fake-image"]
    assert result["ok"] is True
    assert result["output_one"] == (
        "潇寒18401352224河北省石家庄市裕华区裕华区塔南路位同新村南区位同新村南区多层4幢1单元102"
    )
    assert result["output_two"] == "请电话送货上门谢谢【9530】"
    assert result["order_preview"]["order_id"] == "3735824608022632960"
    assert result["order_preview"]["platform"] == "微信小店"


def test_preview_batch_returns_multiple_order_previews(tmp_path: Path):
    service = MobileOrderService(HistoryStore(tmp_path / "history.json"))

    result = service.preview_batch(
        "\n".join(
            [
                _mobile_order_text("6925968364688539154", "60.00", "桃子", "17804472821", "8131"),
                _mobile_order_text("6925956120875073042", "130.00", "桃子", "18413059360", "4317"),
            ]
        ),
        shop_name="乐宝零食店",
        platform="抖店",
    )

    assert result["ok"] is True
    assert result["total"] == 2
    assert result["recognized_count"] == 2
    assert [item["order_preview"]["order_id"] for item in result["orders"]] == [
        "6925968364688539154",
        "6925956120875073042",
    ]
    assert [item["output_two"] for item in result["orders"]] == [
        "请电话送货上门谢谢【8131】",
        "请电话送货上门谢谢【4317】",
    ]
    assert result["orders"][0]["output_one"] == "桃子17804472821山东省潍坊市寿光市洛城街道永泰花园小区"
    assert "订单编号" not in result["orders"][0]["output_one"]


def test_create_drafts_batch_appends_selected_orders_and_skips_duplicates(tmp_path: Path):
    store = HistoryStore(tmp_path / "history.json")
    service = MobileOrderService(store)
    text = "\n".join(
        [
            _mobile_order_text("6925968364688539154", "60.00", "桃子", "17804472821", "8131"),
            _mobile_order_text("6925956120875073042", "130.00", "桃子", "18413059360", "4317"),
        ]
    )

    first = service.create_drafts_batch(text, selected_indexes=[1])
    second = service.create_drafts_batch(text, selected_indexes=[1, 2])

    assert first["created_count"] == 1
    assert first["orders"][0]["draft_status"] == "created"
    assert first["orders"][1]["draft_status"] == "skipped"
    assert second["created_count"] == 1
    assert second["skipped_count"] == 1
    rows = store.list_items()
    assert len(rows) == 2
    assert {row["order_snapshot"]["order_id"] for row in rows} == {
        "6925968364688539154",
        "6925956120875073042",
    }
    assert {row["sync_source"] for row in rows} == {"手机助手批量草稿"}


def test_http_preview_batch_with_valid_authorization(tmp_path: Path):
    server = MobileOrderHttpServer(
        MobileOrderService(HistoryStore(tmp_path / "history.json")),
        api_key="secret",
    )
    server.start()
    try:
        request = urllib.request.Request(
            f"{server.base_url}/mobile/orders/preview-batch",
            data=json.dumps(
                {
                    "text": "\n".join(
                        [
                            _mobile_order_text("6925968364688539154", "60.00", "桃子", "17804472821", "8131"),
                            _mobile_order_text("6925956120875073042", "130.00", "桃子", "18413059360", "4317"),
                        ]
                    )
                },
                ensure_ascii=False,
            ).encode("utf-8"),
            headers={
                "Authorization": "Bearer secret",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        with urllib.request.urlopen(request, timeout=2) as response:
            payload = json.loads(response.read().decode("utf-8"))

        assert payload["ok"] is True
        assert payload["total"] == 2
        assert payload["orders"][1]["order_preview"]["order_id"] == "6925956120875073042"
    finally:
        server.stop()


def test_image_request_without_ocr_pipeline_returns_readable_warning(tmp_path: Path):
    service = MobileOrderService(HistoryStore(tmp_path / "history.json"))

    result = service.preview("", image_base64=base64.b64encode(b"fake-image").decode("ascii"))

    assert result["ok"] is False
    assert "图片识别需要先在电脑端配置并启动草莓系统 OCR" in result["warnings"]


def test_http_authorization_failure(tmp_path: Path):
    server = MobileOrderHttpServer(
        MobileOrderService(HistoryStore(tmp_path / "history.json")),
        api_key="secret",
    )
    server.start()
    try:
        request = urllib.request.Request(
            f"{server.base_url}/mobile/orders/preview",
            data=json.dumps({"text": ADDRESS_TEXT}, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            urllib.request.urlopen(request, timeout=2)
        except urllib.error.HTTPError as exc:
            assert exc.code == 401
            payload = json.loads(exc.read().decode("utf-8"))
        else:
            raise AssertionError("request unexpectedly succeeded")

        assert payload == {"ok": False, "error": "unauthorized"}
    finally:
        server.stop()


def test_http_preview_with_valid_authorization(tmp_path: Path):
    server = MobileOrderHttpServer(
        MobileOrderService(HistoryStore(tmp_path / "history.json")),
        api_key="secret",
    )
    server.start()
    try:
        request = urllib.request.Request(
            f"{server.base_url}/mobile/orders/preview",
            data=json.dumps({"text": ADDRESS_TEXT}, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": "Bearer secret",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        with urllib.request.urlopen(request, timeout=2) as response:
            payload = json.loads(response.read().decode("utf-8"))

        assert payload["ok"] is True
        assert payload["output_two"] == "请电话送货上门谢谢【2666】"
        assert payload["order_preview"]["recipient_name"] == "张春娜"
    finally:
        server.stop()


def test_mobile_entry_page_is_served_without_authorization(tmp_path: Path):
    server = MobileOrderHttpServer(
        MobileOrderService(
            HistoryStore(tmp_path / "history.json"),
            default_shop_name="乐宝零食店--微信",
            default_platform="微信小店",
        ),
        api_key="secret",
    )
    server.start()
    try:
        with urllib.request.urlopen(f"{server.base_url}/mobile", timeout=2) as response:
            body = response.read().decode("utf-8")

        assert "草莓手机助手录单" in body
        assert "乐宝零食店--微信" in body
        assert "微信小店" in body
    finally:
        server.stop()


def test_root_path_serves_mobile_entry_page(tmp_path: Path):
    server = MobileOrderHttpServer(
        MobileOrderService(HistoryStore(tmp_path / "history.json")),
        api_key="secret",
    )
    server.start()
    try:
        with urllib.request.urlopen(server.base_url, timeout=2) as response:
            body = response.read().decode("utf-8")

        assert "草莓手机助手录单" in body
        assert "先识别看看" in body
    finally:
        server.stop()


def test_mobile_http_server_can_serve_wechat_callback_on_same_port(tmp_path: Path):
    service = MobileOrderService(HistoryStore(tmp_path / "history.json"))
    server = MobileOrderHttpServer(
        service,
        api_key="secret",
        wechat_callback_service=WechatCallbackService(
            token="wechat-secret",
            mobile_order_service=service,
        ),
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


def test_concurrent_http_drafts_do_not_overwrite_history(tmp_path: Path):
    store = HistoryStore(tmp_path / "history.json")
    server = MobileOrderHttpServer(MobileOrderService(store), api_key="secret")
    server.start()
    try:
        def create_draft(index: int) -> str:
            request = urllib.request.Request(
                f"{server.base_url}/mobile/orders/drafts",
                data=json.dumps(
                    {"text": ADDRESS_TEXT.replace("2402", f"24{index:02d}")},
                    ensure_ascii=False,
                ).encode("utf-8"),
                headers={
                    "Authorization": "Bearer secret",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=3) as response:
                payload = json.loads(response.read().decode("utf-8"))
            assert payload["ok"] is True
            return payload["draft_record_id"]

        with ThreadPoolExecutor(max_workers=12) as executor:
            record_ids = list(executor.map(create_draft, range(24)))

        rows = store.list_items()
        assert len(rows) == 24
        assert {row["record_id"] for row in rows} == set(record_ids)
    finally:
        server.stop()


def _wechat_signature(token: str, timestamp: str, nonce: str) -> str:
    parts = sorted([token, timestamp, nonce])
    return hashlib.sha1("".join(parts).encode("utf-8")).hexdigest()


def _mobile_order_text(
    order_id: str,
    income_amount: str,
    recipient_name: str,
    phone_number: str,
    code: str,
) -> str:
    return f"""
    订单编号 {order_id}
    下单时间 2026-04-29 15:58:48
    订单状态 待发货
    商品信息
    【明日达】赵露丝同款27000澳大利亚进口婴儿水宝宝水高端矿泉水
    500ml/瓶*12袋(赵露思同款澳版)
    单价/数量 ¥325.00 x1
    商家收入金额 ¥{income_amount}
    收货信息 {recipient_name} [{code}] {phone_number} 山东省潍坊市寿光市洛城街道永泰花园小区 [{code}]
    """
