from __future__ import annotations

from pathlib import Path

import base64
import pytest
import requests

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


class HttpErrorResponse:
    def __init__(self, status_code: int, text: str):
        self.status_code = status_code
        self.text = text

    def raise_for_status(self) -> None:
        raise requests.HTTPError(f"{self.status_code} Server Error", response=self)

    def json(self) -> dict:
        raise ValueError("bad json")


class JsonHttpErrorResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self.payload = payload
        self.text = str(payload)

    def raise_for_status(self) -> None:
        raise requests.HTTPError(f"{self.status_code} Client Error", response=self)

    def json(self) -> dict:
        return self.payload


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
    assert payload["平台"] == "抖店"
    assert payload["收入"] == "162.00"
    assert "价格" not in payload
    assert payload["发货地址"] == "何女士 15781304332-3612 四川省成都市金牛区营门口街道友谊花园9-2304"


def test_build_feishu_payload_includes_financial_fields_and_custom_costs():
    order = ParsedOrder(
        order_id="1",
        placed_at="2026-04-13 12:00:00",
        order_status="已发货",
        product_name="测试商品",
        quantity="1",
        order_amount="100.00",
        income_amount="80.00",
        recipient_name="张三",
        phone_number="13800138000",
        code="9527",
        address="上海市浦东新区测试路 1 号",
        delivery_note="请电话联系",
        platform="抖店",
        platform_fee_rate="10",
        platform_fee_amount="8",
        other_cost="2",
        procurement_total_cost="30",
        gross_profit="36",
        custom_cost_labels=("包装费", "赠品", ""),
        custom_cost_values=("1.5", "2.5", ""),
    )

    payload = build_feishu_payload(
        order,
        {
            "平台扣点比例": "平台扣点比例",
            "平台扣点金额": "平台扣点金额",
            "其他成本": "其他成本",
            "采购总成本": "采购总成本",
            "毛利润": "毛利润",
            "自定义字段1": "包装费",
            "自定义字段2": "赠品",
        },
        shop_name="乐宝零食店",
    )

    assert payload["平台扣点比例"] == "10"
    assert payload["平台扣点金额"] == "8"
    assert payload["其他成本"] == "2"
    assert payload["采购总成本"] == "30"
    assert payload["毛利润"] == "36"
    assert payload["包装费"] == "1.5"
    assert payload["赠品"] == "2.5"


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


def test_ocr_client_raises_friendly_error_when_minimax_plan_lacks_ocr_model(
    monkeypatch: pytest.MonkeyPatch,
):
    def fake_post(url, headers=None, json=None, timeout=None):
        return HttpErrorResponse(
            500,
            (
                '{"type":"error","error":{"type":"server_error","message":'
                '"your current token plan not support model, MiniMax-Text-01 (2061)"}}'
            ),
        )

    monkeypatch.setattr(
        "strawberry_order_management.services.ocr_client.requests.post", fake_post
    )

    client = OCRClient("https://api.minimaxi.com/v1", "secret")

    with pytest.raises(
        ValueError,
        match="当前 MiniMax 套餐不支持截图 OCR 模型",
    ):
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


def test_helper_client_strips_thinking_content_from_minimax_response(
    monkeypatch: pytest.MonkeyPatch,
):
    def fake_post(url, headers=None, json=None, timeout=None):
        return FakeResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": (
                                "<think>internal reasoning</think>\n\n"
                                "订单编号 1\n"
                                "下单时间 2026-04-11 20:57:15"
                            )
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr(
        "strawberry_order_management.services.helper_client.requests.post", fake_post
    )

    client = HelperClient("https://api.minimaxi.com/v1", "secret")

    assert client.enrich_text("ocr raw text") == "订单编号 1\n下单时间 2026-04-11 20:57:15"


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
    assert captured["headers"] == {
        "Authorization": "Bearer access_token",
        "Content-Type": "application/json; charset=utf-8",
    }
    assert captured["json"] == {"fields": {"备注": "ok"}}
    assert captured["timeout"] == 30


def test_feishu_client_fetches_tenant_access_token_from_app_credentials(
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
                "code": 0,
                "msg": "ok",
                "tenant_access_token": "tenant_token",
                "app_access_token": "app_token",
            }
        )

    monkeypatch.setattr("strawberry_order_management.services.feishu_client.requests.post", fake_post)

    client = FeishuClient("app", "secret", "app_token", "tbl_1")

    tenant_access_token = client.get_tenant_access_token()

    assert tenant_access_token == "tenant_token"
    assert captured["url"] == "https://open.feishu.cn/open-apis/auth/v3/app_access_token/internal"
    assert captured["headers"] == {"Content-Type": "application/json; charset=utf-8"}
    assert captured["json"] == {"app_id": "app", "app_secret": "secret"}
    assert captured["timeout"] == 30


def test_feishu_client_raises_readable_error_on_business_error(
    monkeypatch: pytest.MonkeyPatch,
):
    def fake_post(url, headers=None, json=None, timeout=None):
        return FakeResponse({"code": 99991663, "msg": "invalid app credentials"})

    monkeypatch.setattr("strawberry_order_management.services.feishu_client.requests.post", fake_post)

    client = FeishuClient("app", "secret", "app_token", "tbl_1")

    with pytest.raises(ValueError, match="invalid app credentials"):
        client.get_tenant_access_token()


def test_feishu_client_resolves_bitable_tokens_from_wiki_url(
    monkeypatch: pytest.MonkeyPatch,
):
    captured_calls: list[tuple[str, dict | None, dict | None]] = []

    def fake_get(url, headers=None, params=None, timeout=None):
        captured_calls.append((url, headers, params))
        return FakeResponse(
            {
                "code": 0,
                "msg": "success",
                "data": {
                    "node": {
                        "obj_type": "bitable",
                        "obj_token": "basc1234567890",
                    }
                },
            }
        )

    monkeypatch.setattr("strawberry_order_management.services.feishu_client.requests.get", fake_get)

    client = FeishuClient("app", "secret", "app_token", "tbl_1")

    result = client.resolve_bitable_from_wiki_url(
        "https://my.feishu.cn/wiki/QTXMwCDpQi9n6VkfDxJc5mNTnjh?table=tblWZDrx4gqXpc5M&view=vew5lZdMQj",
        access_token="tenant_token_123",
    )

    assert result == {
        "app_token": "basc1234567890",
        "table_id": "tblWZDrx4gqXpc5M",
        "wiki_url": "https://my.feishu.cn/wiki/QTXMwCDpQi9n6VkfDxJc5mNTnjh?table=tblWZDrx4gqXpc5M&view=vew5lZdMQj",
    }
    assert captured_calls == [
        (
            "https://open.feishu.cn/open-apis/wiki/v2/spaces/get_node",
            {"Authorization": "Bearer tenant_token_123"},
            {"token": "QTXMwCDpQi9n6VkfDxJc5mNTnjh"},
        )
    ]


def test_feishu_client_rejects_wiki_url_without_table_id():
    client = FeishuClient("app", "secret", "app_token", "tbl_1")

    with pytest.raises(ValueError, match="链接里缺少 Table ID"):
        client.resolve_bitable_from_wiki_url(
            "https://my.feishu.cn/wiki/QTXMwCDpQi9n6VkfDxJc5mNTnjh"
        )


def test_feishu_client_surfaces_json_message_on_wiki_resolution_http_error(
    monkeypatch: pytest.MonkeyPatch,
):
    def fake_get(url, headers=None, params=None, timeout=None):
        return JsonHttpErrorResponse(
            400,
            {
                "code": 99991672,
                "msg": "No wiki permission",
                "error": {"log_id": "123"},
            },
        )

    monkeypatch.setattr("strawberry_order_management.services.feishu_client.requests.get", fake_get)

    client = FeishuClient("app", "secret", "app_token", "tbl_1")

    with pytest.raises(ValueError, match="No wiki permission"):
        client.resolve_bitable_from_wiki_url(
            "https://my.feishu.cn/wiki/QTXMwCDpQi9n6VkfDxJc5mNTnjh?table=tblWZDrx4gqXpc5M",
            access_token="tenant_token_123",
        )


def test_feishu_client_lists_table_field_names(monkeypatch: pytest.MonkeyPatch):
    captured: dict[str, object] = {}

    def fake_get(url, headers=None, params=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["params"] = params
        captured["timeout"] = timeout
        return FakeResponse(
            {
                "code": 0,
                "msg": "ok",
                "data": {
                    "items": [
                        {"field_name": "店铺"},
                        {"field_name": "平台"},
                        {"field_name": "收入"},
                    ]
                },
            }
        )

    monkeypatch.setattr("strawberry_order_management.services.feishu_client.requests.get", fake_get)

    client = FeishuClient("app", "secret", "app_token", "tbl_1")

    result = client.list_field_names("tenant_token_123")

    assert result == {"店铺", "平台", "收入"}
    assert captured["url"] == "https://open.feishu.cn/open-apis/bitable/v1/apps/app_token/tables/tbl_1/fields"
    assert captured["headers"] == {"Authorization": "Bearer tenant_token_123"}
    assert captured["params"] == {"page_size": 500}
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
