from __future__ import annotations

from pathlib import Path

import base64
import pytest

from strawberry_order_management.models import ParsedOrder
from strawberry_order_management.services.feishu_client import FeishuClient
from strawberry_order_management.services.helper_client import HelperClient
from strawberry_order_management.services.ocr_client import OCRClient
from strawberry_order_management.services.pipeline import OrderPipeline, build_feishu_payload


class FakeResponse:
    def __init__(self, payload: dict):
        self.payload = payload
        self.raise_called = False

    def raise_for_status(self) -> None:
        self.raise_called = True

    def json(self) -> dict:
        return self.payload


class BadJsonResponse:
    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        raise ValueError("bad json")


def test_build_feishu_payload_uses_income_amount_for_income_column():
    order = ParsedOrder(
        order_id="6952003434324366473",
        placed_at="2026-04-11 20:57:15",
        order_status="已发货",
        product_name="澳大利亚进口婴儿水",
        quantity="1",
        order_amount="405.00",
        income_amount="162.00",
        recipient_name="何女士",
        phone_number="15781304332",
        code="3612",
        address="四川省成都市金牛区营门口街道友谊花园9-2304",
        delivery_note="请电话送货上门谢谢【3612】",
    )

    payload = build_feishu_payload(order)

    assert payload["备注"] == "请电话送货上门谢谢【3612】"
    assert payload["收入"] == "162.00"
    assert payload["价格"] == "405.00"
    assert payload["发货地址"] == "何女士 15781304332-3612 四川省成都市金牛区营门口街道友谊花园9-2304"


def test_order_pipeline_extracts_order_from_ocr_then_helper_text():
    raw_text = Path("tests/fixtures/ocr/jd_order_01.txt").read_text(encoding="utf-8")
    calls: list[str] = []

    class OcrStub:
        def extract_text(self, image_bytes: bytes) -> str:
            calls.append(f"ocr:{image_bytes!r}")
            return raw_text

    class HelperStub:
        def enrich_text(self, extracted_text: str) -> str:
            calls.append(f"helper:{extracted_text[:6]}")
            return extracted_text

    pipeline = OrderPipeline(OcrStub(), HelperStub(), None)

    order = pipeline.extract_order(b"fake-image-bytes")

    assert order.order_id == "6952003434324366473"
    assert order.delivery_note == "请电话送货上门谢谢【3612】"
    assert calls == ["ocr:b'fake-image-bytes'", "helper:订单编号 6"]


def test_ocr_client_posts_image_bytes_and_returns_text(monkeypatch: pytest.MonkeyPatch):
    captured: dict[str, object] = {}

    def fake_post(url, headers=None, files=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["files"] = files
        captured["timeout"] = timeout
        return FakeResponse({"text": "ocr text"})

    monkeypatch.setattr("strawberry_order_management.services.ocr_client.requests.post", fake_post)

    client = OCRClient("https://ocr.example.com/", "secret")

    assert client.extract_text(b"image-bytes") == "ocr text"
    assert captured["url"] == "https://ocr.example.com/ocr"
    assert captured["headers"] == {"Authorization": "Bearer secret"}
    assert captured["files"] == {"file": ("order.png", b"image-bytes", "image/png")}
    assert captured["timeout"] == 30


def test_ocr_client_supports_minimax_image_understanding_style_prompt(
    monkeypatch: pytest.MonkeyPatch,
):
    captured: dict[str, object] = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return FakeResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": "订单编号 6952003434324366473\n下单时间 2026-04-11 20:57:15"
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr(
        "strawberry_order_management.services.ocr_client.requests.post", fake_post
    )

    client = OCRClient("https://api.minimaxi.com/v1", "secret")
    text = client.extract_text(b"image-bytes")

    expected_base64 = base64.b64encode(b"image-bytes").decode("utf-8")
    assert text == "订单编号 6952003434324366473\n下单时间 2026-04-11 20:57:15"
    assert captured["url"] == "https://api.minimaxi.com/v1/chat/completions"
    assert captured["headers"] == {"Authorization": "Bearer secret"}
    assert captured["json"]["model"] == "MiniMax-Text-01"
    assert "订单编号 / 下单时间 / 订单状态 / 商品信息 / 单价/数量 / 商家收入金额 / 收货信息" in captured["json"]["messages"][0]["content"]
    assert "不要总结、改写、翻译、解释" in captured["json"]["messages"][0]["content"]
    assert "姓名 [编号] 手机号 地址 [编号]" in captured["json"]["messages"][1]["content"]
    assert captured["json"]["messages"][1]["content"].endswith(
        f"[Image base64:{expected_base64}]"
    )
    assert captured["timeout"] == 30


def test_ocr_client_raises_readable_error_on_invalid_json(monkeypatch: pytest.MonkeyPatch):
    def fake_post(url, headers=None, files=None, timeout=None):
        return BadJsonResponse()

    monkeypatch.setattr("strawberry_order_management.services.ocr_client.requests.post", fake_post)

    client = OCRClient("https://ocr.example.com/", "secret")

    with pytest.raises(ValueError, match="OCR API response is not valid JSON"):
        client.extract_text(b"image-bytes")


def test_ocr_client_raises_readable_error_when_text_missing(monkeypatch: pytest.MonkeyPatch):
    def fake_post(url, headers=None, files=None, timeout=None):
        return FakeResponse({"result": "ocr text"})

    monkeypatch.setattr("strawberry_order_management.services.ocr_client.requests.post", fake_post)

    client = OCRClient("https://ocr.example.com/", "secret")

    with pytest.raises(ValueError, match="OCR API response missing 'text'"):
        client.extract_text(b"image-bytes")


def test_ocr_client_raises_readable_error_when_minimax_choices_missing(
    monkeypatch: pytest.MonkeyPatch,
):
    def fake_post(url, headers=None, json=None, timeout=None):
        return FakeResponse({"result": "ocr text"})

    monkeypatch.setattr(
        "strawberry_order_management.services.ocr_client.requests.post", fake_post
    )

    client = OCRClient("https://api.minimaxi.com/v1", "secret")

    with pytest.raises(ValueError, match="MiniMax OCR response missing choices"):
        client.extract_text(b"image-bytes")


def test_helper_client_posts_text_and_returns_text(monkeypatch: pytest.MonkeyPatch):
    captured: dict[str, object] = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return FakeResponse({"text": "helper text"})

    monkeypatch.setattr("strawberry_order_management.services.helper_client.requests.post", fake_post)

    client = HelperClient("https://helper.example.com/", "secret")

    assert client.enrich_text("raw text") == "helper text"
    assert captured["url"] == "https://helper.example.com/extract"
    assert captured["headers"] == {"Authorization": "Bearer secret"}
    assert captured["json"] == {"text": "raw text"}
    assert captured["timeout"] == 30


def test_helper_client_supports_minimax_openai_compatible_endpoint(
    monkeypatch: pytest.MonkeyPatch,
):
    captured: dict[str, object] = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return FakeResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": "订单编号 1\n下单时间 2026-04-11 20:57:15"
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr(
        "strawberry_order_management.services.helper_client.requests.post", fake_post
    )

    client = HelperClient("https://api.minimaxi.com/v1", "secret")

    text = client.enrich_text("ocr raw text")

    assert text == "订单编号 1\n下单时间 2026-04-11 20:57:15"
    assert captured["url"] == "https://api.minimaxi.com/v1/chat/completions"
    assert captured["headers"] == {"Authorization": "Bearer secret"}
    assert captured["json"]["model"] == "MiniMax-M2.5"
    assert "订单编号" in captured["json"]["messages"][0]["content"]
    assert "收货信息 姓名 [编号] 手机号 地址 [编号]" in captured["json"]["messages"][0]["content"]
    assert "不要加 Markdown，不要加 JSON，不要加代码块" in captured["json"]["messages"][0]["content"]
    assert "字段名后面不要加中文冒号" in captured["json"]["messages"][0]["content"]
    assert captured["json"]["messages"][1]["content"].endswith("ocr raw text")
    assert captured["timeout"] == 30


def test_helper_client_raises_readable_error_on_invalid_json(monkeypatch: pytest.MonkeyPatch):
    def fake_post(url, headers=None, json=None, timeout=None):
        return BadJsonResponse()

    monkeypatch.setattr("strawberry_order_management.services.helper_client.requests.post", fake_post)

    client = HelperClient("https://helper.example.com/", "secret")

    with pytest.raises(ValueError, match="Helper API response is not valid JSON"):
        client.enrich_text("raw text")


def test_helper_client_raises_readable_error_when_text_missing(monkeypatch: pytest.MonkeyPatch):
    def fake_post(url, headers=None, json=None, timeout=None):
        return FakeResponse({"result": "helper text"})

    monkeypatch.setattr("strawberry_order_management.services.helper_client.requests.post", fake_post)

    client = HelperClient("https://helper.example.com/", "secret")

    with pytest.raises(ValueError, match="Helper API response missing 'text'"):
        client.enrich_text("raw text")


def test_helper_client_raises_readable_error_when_minimax_choices_missing(
    monkeypatch: pytest.MonkeyPatch,
):
    def fake_post(url, headers=None, json=None, timeout=None):
        return FakeResponse({"result": "helper text"})

    monkeypatch.setattr(
        "strawberry_order_management.services.helper_client.requests.post", fake_post
    )

    client = HelperClient("https://api.minimaxi.com/v1", "secret")

    with pytest.raises(ValueError, match="MiniMax response missing choices"):
        client.enrich_text("raw text")


def test_feishu_client_posts_fields_and_returns_response(monkeypatch: pytest.MonkeyPatch):
    captured: dict[str, object] = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return FakeResponse({"data": {"record_id": "rec_1"}})

    monkeypatch.setattr("strawberry_order_management.services.feishu_client.requests.post", fake_post)

    client = FeishuClient("app", "secret", "app_token", "tbl_1")

    result = client.create_record("access_token", {"备注": "ok"})

    assert result == {"data": {"record_id": "rec_1"}}
    assert captured["url"] == "https://open.feishu.cn/open-apis/bitable/v1/apps/app_token/tables/tbl_1/records"
    assert captured["headers"] == {"Authorization": "Bearer access_token"}
    assert captured["json"] == {"fields": {"备注": "ok"}}
    assert captured["timeout"] == 30


def test_build_feishu_payload_rejects_invalid_placed_at_format():
    order = ParsedOrder(
        order_id="6952003434324366473",
        placed_at="2026-04-11",
        order_status="已发货",
        product_name="澳大利亚进口婴儿水",
        quantity="1",
        order_amount="405.00",
        income_amount="162.00",
        recipient_name="何女士",
        phone_number="15781304332",
        code="3612",
        address="四川省成都市金牛区营门口街道友谊花园9-2304",
        delivery_note="请电话送货上门谢谢【3612】",
    )

    with pytest.raises(ValueError, match="placed_at must be in 'YYYY-MM-DD HH:MM:SS' format"):
        build_feishu_payload(order)
