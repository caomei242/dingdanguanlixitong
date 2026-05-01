from __future__ import annotations

import time

import pytest
import requests

from strawberry_order_management.mock_auto_order_service import (
    AutoOrderBrowserError,
    RealAutoOrderHttpServer,
    RealAutoOrderTaskProcessor,
)


class FakeBrowserRunner:
    def __init__(
        self,
        *,
        jd_order_id: str = "JD9001",
        error: Exception | None = None,
        inspect_result: dict | None = None,
    ) -> None:
        self.jd_order_id = jd_order_id
        self.error = error
        self.inspect_result = inspect_result or {
            "status": "success",
            "message": "京东环境可用",
            "account_name": "京东账号A",
            "checked_at": "2026-04-17 12:00:00",
            "checks": [
                {"label": "HTTP 服务连通", "status": "success", "message": "服务可访问"},
                {"label": "当前是否已登录京东", "status": "success", "message": "已登录京东"},
                {"label": "自动拍单地址槽", "status": "success", "message": "已找到自动拍单地址槽"},
            ],
        }
        self.calls: list[dict] = []

    def inspect_environment(self, payload: dict) -> dict:
        self.calls.append({"inspect": dict(payload)})
        return dict(self.inspect_result)

    def run_item(self, payload: dict):
        self.calls.append(dict(payload))
        if self.error is not None:
            raise self.error
        return {
            "jd_order_id": self.jd_order_id,
            "debug_stage": "到达待付款",
            "debug_steps": [
                {"at": "2026-04-17 12:00:01", "text": "选中账号环境：京东账号A"},
                {"at": "2026-04-17 12:00:02", "text": "打开商品链接"},
                {"at": "2026-04-17 12:00:03", "text": "到达待付款"},
            ],
            "debug_updated_at": "2026-04-17 12:00:03",
            "debug_screenshot_path": "",
        }


class FakeStopBeforeSubmitRunner(FakeBrowserRunner):
    def run_item(self, payload: dict):
        self.calls.append(dict(payload))
        if payload.get("stop_before_submit"):
            raise AutoOrderBrowserError(
                "已停在提交前检查点，请人工确认后关闭烟测开关再重试",
                debug_steps=[
                    {
                        "at": "2026-04-17 12:00:04",
                        "text": "提交订单｜命中提交按钮｜URL: https://trade.jd.com/confirm",
                    }
                ],
                debug_screenshot_path="/tmp/stop-before-submit.png",
                debug_updated_at="2026-04-17 12:00:04",
                debug_stage="提交前检查点",
            )
        return super().run_item(payload)


class _FakeSyncPlaywright:
    def __enter__(self):
        return object()

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeLocator:
    def __init__(self, page, selector: str) -> None:
        self.page = page
        self.selector = selector

    @property
    def first(self):
        return self

    def wait_for(self, state="visible", timeout=0):
        if "addressLink" in self.selector and not self.page.has_address_link:
            raise AssertionError("addressLink not visible")
        if "guide_close" in self.selector and not self.page.has_guide_close:
            raise AssertionError("guide close not visible")
        return None

    def click(self, timeout=0):
        self.page.clicked.append(self.selector)
        if "addressLink" in self.selector:
            self.page.url = "https://easybuy.jd.com/address/getEasyBuyList.action?from=home"
            self.page.address_slot_visible = True
        if "guide_close" in self.selector:
            self.page.guide_closed = True
        return None


class _FakePlaywrightPage:
    def __init__(self, *, has_address_link: bool = True, has_guide_close: bool = True) -> None:
        self.url = ""
        self.visited: list[str] = []
        self.clicked: list[str] = []
        self.guide_closed = False
        self.address_slot_visible = False
        self.has_address_link = has_address_link
        self.has_guide_close = has_guide_close
        self.easybuy_edit_label = ""

    def goto(self, url: str, wait_until="domcontentloaded", timeout=0):
        self.url = url
        self.visited.append(url)
        return None

    def wait_for_timeout(self, milliseconds: int):
        return None

    def locator(self, selector: str):
        return _FakeLocator(self, selector)

    def evaluate(self, script: str, arg=None):
        label = str(arg or "").strip()
        if "alertUpdateAddressDiagByoverseas" in script and label == "自动拍单":
            self.easybuy_edit_label = label
            return True
        return False


class _FakePlaywrightContext:
    def __init__(self, page) -> None:
        self.pages = [page]
        self.closed = False

    def close(self):
        self.closed = True
        return None


class _FakeChromiumLauncher:
    def __init__(self, return_context=None) -> None:
        self.return_context = return_context
        self.calls: list[dict] = []

    def launch_persistent_context(self, **kwargs):
        self.calls.append(dict(kwargs))
        return self.return_context


class _FakePlaywrightRuntime:
    def __init__(self, chromium) -> None:
        self.chromium = chromium


class _FakeVerificationPage:
    def __init__(self, url: str) -> None:
        self.url = url

    def goto(self, url: str, wait_until="domcontentloaded", timeout=0):
        self.url = url
        return None

    def wait_for_timeout(self, milliseconds: int):
        return None

    def screenshot(self, path: str, full_page: bool = True):
        return None


class _FakeResponseWaiter:
    def __init__(self, response) -> None:
        self.value = response

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeBuyNowResponse:
    def __init__(self, payload: dict) -> None:
        self.url = "https://api.m.jd.com/api?functionId=pcCart_jc_buyNow"
        self._payload = payload

    def json(self):
        return dict(self._payload)


class _FakeBuyNowPage:
    def __init__(self) -> None:
        self.url = "https://item.jd.com/65714611165.html"
        self.visited: list[str] = []
        self.response = _FakeBuyNowResponse(
            {
                "success": True,
                "code": 0,
                "message": "success",
                "url": "//trade.jd.com/shopping/order/getOrderInfo.action?source=common",
            }
        )

    def expect_response(self, predicate, timeout=0):
        assert predicate(self.response) is True
        return _FakeResponseWaiter(self.response)

    def wait_for_timeout(self, milliseconds: int):
        return None

    def goto(self, url: str, wait_until="domcontentloaded", timeout=0):
        self.visited.append(url)
        self.url = url
        return None


class _FakeLoginHeuristicPage:
    def __init__(self, url: str) -> None:
        self.url = url


class _FakeSettlementPage:
    def __init__(self) -> None:
        self.url = "https://trade.jd.com/shopping/order/getOrderInfo.action?source=common"
        self.settlement_edit_label = ""
        self.active_address_needle = "请电话送货上门谢谢【5182】"

    def wait_for_timeout(self, milliseconds: int):
        return None

    def evaluate(self, script: str, arg=None):
        label = str(arg or "").strip()
        if "cards.find" in script and label:
            self.active_address_needle = label
            return True
        if "consignee-item-wrap" in script and label == "自动拍单":
            self.settlement_edit_label = label
            return True
        if "consignee-item-" in script and label == self.active_address_needle:
            return True
        return False


class _FakeProductLinkPage:
    def __init__(self, url: str, html: str = "") -> None:
        self.url = url
        self._html = html
        self.visited: list[str] = []

    def goto(self, url: str, wait_until="domcontentloaded", timeout=0):
        self.visited.append(url)
        self.url = url
        return None

    def wait_for_timeout(self, milliseconds: int):
        return None

    def content(self):
        return self._html


class _FakeSubmitOrderPage:
    def __init__(self, url: str) -> None:
        self.url = url

    def wait_for_timeout(self, milliseconds: int):
        return None


def _payload(*, output_one: str = "谢18413027767四川省成都市武侯区玉林街道", output_two: str = "请电话送货上门谢谢【5182】") -> dict:
    return {
        "history_record_id": "history-1",
        "source": "intake",
        "shop_name": "乐宝零食店",
        "recipient_name": "谢",
        "phone_number": "18413027767",
        "address": "四川省成都市武侯区玉林街道",
        "delivery_note": "",
        "address_output_one": output_one,
        "address_output_two": output_two,
        "procurement_items": [
            {
                "procurement_index": 0,
                "product_name": "27000-赵露思款",
                "quantity": "1",
                "jd_link": "https://item.jd.com/1001.html",
            }
        ],
        "jd_accounts": [
            {
                "name": "京东账号B",
                "environment": "/Users/gd/.jd/account-b",
                "priority": 2,
                "enabled": True,
            },
            {
                "name": "京东账号A",
                "environment": "/Users/gd/.jd/account-a",
                "priority": 1,
                "enabled": True,
            },
        ],
    }


def test_real_auto_order_processor_uses_highest_priority_account_and_address_outputs():
    runner = FakeBrowserRunner()
    processor = RealAutoOrderTaskProcessor(browser_runner=runner)

    task_status, message, item_results = processor.process_task(_payload(), lambda item: None)

    assert task_status == "succeeded"
    assert message == "已到待付款"
    assert item_results[0]["status"] == "待付款"
    assert item_results[0]["jd_order_id"] == "JD9001"
    assert runner.calls[0]["account_name"] == "京东账号A"
    assert runner.calls[0]["account_environment"] == "/Users/gd/.jd/account-a"
    assert runner.calls[0]["address_output_one"] == "谢18413027767四川省成都市武侯区玉林街道"
    assert runner.calls[0]["address_output_two"] == "请电话送货上门谢谢【5182】"
    assert runner.calls[0]["address_slot_label"] == "自动拍单"


def test_real_auto_order_processor_fails_when_address_output_one_missing():
    runner = FakeBrowserRunner()
    processor = RealAutoOrderTaskProcessor(browser_runner=runner)

    task_status, message, item_results = processor.process_task(_payload(output_one=""), lambda item: None)

    assert task_status == "failed"
    assert "缺少地址提取结果一" in message
    assert item_results[0]["status"] == "失败"
    assert item_results[0]["error_message"] == "缺少地址提取结果一"
    assert runner.calls == []


def test_real_auto_order_processor_returns_browser_failures_per_item():
    runner = FakeBrowserRunner(error=AutoOrderBrowserError("未找到自动拍单标签地址"))
    processor = RealAutoOrderTaskProcessor(browser_runner=runner)

    task_status, message, item_results = processor.process_task(_payload(), lambda item: None)

    assert task_status == "failed"
    assert "未找到自动拍单标签地址" in message
    assert item_results[0]["status"] == "失败"
    assert item_results[0]["error_message"] == "未找到自动拍单标签地址"


def test_real_auto_order_processor_still_succeeds_when_browser_cannot_extract_jd_order_id():
    runner = FakeBrowserRunner(jd_order_id="")
    processor = RealAutoOrderTaskProcessor(browser_runner=runner)

    task_status, message, item_results = processor.process_task(_payload(), lambda item: None)

    assert task_status == "succeeded"
    assert message == "已到待付款"
    assert item_results[0]["status"] == "待付款"
    assert item_results[0]["jd_order_id"] == ""


def test_real_auto_order_http_server_keeps_existing_task_protocol():
    server = RealAutoOrderHttpServer(
        host="127.0.0.1",
        port=0,
        api_key="bridge-key",
        browser_runner=FakeBrowserRunner(jd_order_id=""),
    )
    server.start()
    try:
        submit_response = requests.post(
            server.url("/auto-order/tasks"),
            json=_payload(),
            headers={"Authorization": "Bearer bridge-key"},
            timeout=3,
        )
        ticket = submit_response.json()
        assert ticket["task_status"] == "queued"

        snapshot = ticket
        deadline = time.time() + 3
        while time.time() < deadline:
            snapshot = requests.get(
                server.url(f"/auto-order/tasks/{ticket['task_id']}"),
                headers={"Authorization": "Bearer bridge-key"},
                timeout=3,
            ).json()
            if snapshot["task_status"] == "succeeded":
                break
            time.sleep(0.02)

        assert snapshot["task_status"] == "succeeded"
        assert snapshot["item_results"][0]["status"] == "待付款"
        assert snapshot["item_results"][0]["jd_order_id"] == ""
        assert snapshot["debug_stage"] == "到达待付款"
        assert snapshot["debug_steps"][0]["text"] == "选中账号环境：京东账号A"
    finally:
        server.stop()


def test_real_auto_order_http_server_exposes_environment_check_endpoint():
    server = RealAutoOrderHttpServer(
        host="127.0.0.1",
        port=0,
        api_key="bridge-key",
        browser_runner=FakeBrowserRunner(),
    )
    server.start()
    try:
        response = requests.post(
            server.url("/auto-order/check"),
            json={"jd_accounts": _payload()["jd_accounts"]},
            headers={"Authorization": "Bearer bridge-key"},
            timeout=3,
        )
        data = response.json()

        assert response.status_code == 200
        assert data["status"] == "success"
        assert data["checks"][1]["message"] == "已登录京东"
    finally:
        server.stop()


def test_real_auto_order_processor_can_stop_before_submit_and_emit_debug_payload():
    runner = FakeStopBeforeSubmitRunner()
    processor = RealAutoOrderTaskProcessor(browser_runner=runner, stop_before_submit=True)
    debug_updates = []

    task_status, message, item_results = processor.process_task(
        _payload(),
        lambda item: None,
        lambda payload: debug_updates.append(dict(payload)),
    )

    assert task_status == "failed"
    assert message == "采购1：已停在提交前检查点，请人工确认后关闭烟测开关再重试"
    assert item_results[0]["status"] == "失败"
    assert item_results[0]["error_message"] == "已停在提交前检查点，请人工确认后关闭烟测开关再重试"
    assert runner.calls[0]["stop_before_submit"] is True
    assert debug_updates[-1]["debug_stage"] == "提交前检查点"
    assert debug_updates[-1]["debug_screenshot_path"] == "/tmp/stop-before-submit.png"
    assert "URL: https://trade.jd.com/confirm" in debug_updates[-1]["debug_steps"][-1]["text"]


def test_real_auto_order_http_server_can_stop_before_submit():
    server = RealAutoOrderHttpServer(
        host="127.0.0.1",
        port=0,
        api_key="bridge-key",
        browser_runner=FakeStopBeforeSubmitRunner(),
        stop_before_submit=True,
    )
    server.start()
    try:
        ticket = requests.post(
            server.url("/auto-order/tasks"),
            json=_payload(),
            headers={"Authorization": "Bearer bridge-key"},
            timeout=3,
        ).json()

        snapshot = ticket
        deadline = time.time() + 3
        while time.time() < deadline:
            snapshot = requests.get(
                server.url(f"/auto-order/tasks/{ticket['task_id']}"),
                headers={"Authorization": "Bearer bridge-key"},
                timeout=3,
            ).json()
            if snapshot["task_status"] == "failed":
                break
            time.sleep(0.02)

        assert snapshot["task_status"] == "failed"
        assert "已停在提交前检查点" in snapshot["message"]
        assert snapshot["debug_stage"] == "提交前检查点"
        assert snapshot["debug_screenshot_path"] == "/tmp/stop-before-submit.png"
    finally:
        server.stop()


def test_playwright_runner_builds_step_text_with_stage_and_url():
    from strawberry_order_management.mock_auto_order_service import PlaywrightAutoOrderBrowserRunner

    assert (
        PlaywrightAutoOrderBrowserRunner._build_step_text(
            "打开商品链接",
            "命中立即购买入口",
            "https://item.jd.com/1001.html",
        )
        == "打开商品链接｜命中立即购买入口｜URL: https://item.jd.com/1001.html"
    )


def test_playwright_runner_validate_runtime_reports_missing_playwright(monkeypatch):
    from strawberry_order_management.mock_auto_order_service import PlaywrightAutoOrderBrowserRunner

    def fake_load_playwright(self):
        raise AutoOrderBrowserError("未安装 Playwright，请先执行 `pip install playwright` 并运行 `python -m playwright install chromium`")

    monkeypatch.setattr(PlaywrightAutoOrderBrowserRunner, "_load_playwright", fake_load_playwright)

    with pytest.raises(AutoOrderBrowserError, match="未安装 Playwright"):
        PlaywrightAutoOrderBrowserRunner.validate_runtime()


def test_playwright_runner_inspect_environment_opens_easybuy_address_page_via_home(monkeypatch):
    from strawberry_order_management.mock_auto_order_service import PlaywrightAutoOrderBrowserRunner

    page = _FakePlaywrightPage()
    context = _FakePlaywrightContext(page)
    runner = PlaywrightAutoOrderBrowserRunner()

    monkeypatch.setattr(PlaywrightAutoOrderBrowserRunner, "validate_runtime", lambda self: None)
    monkeypatch.setattr(
        PlaywrightAutoOrderBrowserRunner,
        "_load_playwright",
        lambda self: (lambda: _FakeSyncPlaywright(), TimeoutError),
    )
    monkeypatch.setattr(
        PlaywrightAutoOrderBrowserRunner,
        "_launch_persistent_context",
        lambda self, playwright, account_environment: context,
    )
    monkeypatch.setattr(PlaywrightAutoOrderBrowserRunner, "_looks_like_login_page", lambda self, current_page: False)
    monkeypatch.setattr(
        PlaywrightAutoOrderBrowserRunner,
        "_has_visible_text",
        lambda self, current_page, texts: current_page.address_slot_visible and "自动拍单" in texts,
    )

    result = runner.inspect_environment(
        {
            "account_name": "京东账号A",
            "account_environment": "/Users/gd/.jd/primary",
            "address_slot_label": "自动拍单",
        }
    )

    assert result["status"] == "success"
    assert page.visited == ["https://www.jd.com", "https://home.jd.com/"]
    assert any("guide_close" in selector for selector in page.clicked)
    assert any("addressLink" in selector for selector in page.clicked)
    assert context.closed is True


def test_playwright_runner_can_open_easybuy_address_slot_editor_by_alias(monkeypatch):
    from strawberry_order_management.mock_auto_order_service import PlaywrightAutoOrderBrowserRunner

    page = _FakePlaywrightPage()
    page.url = "https://easybuy.jd.com/address/getEasyBuyList.action?from=home"
    runner = PlaywrightAutoOrderBrowserRunner()

    monkeypatch.setattr(
        PlaywrightAutoOrderBrowserRunner,
        "_has_visible_text",
        lambda self, current_page, texts: "自动拍单" in texts,
    )
    monkeypatch.setattr(PlaywrightAutoOrderBrowserRunner, "_click_text_then_action", lambda *args, **kwargs: False)
    monkeypatch.setattr(PlaywrightAutoOrderBrowserRunner, "_click_by_text", lambda *args, **kwargs: False)
    monkeypatch.setattr(PlaywrightAutoOrderBrowserRunner, "_has_visible_selector", lambda *args, **kwargs: False)

    runner._open_address_slot_editor(page, "自动拍单")

    assert page.easybuy_edit_label == "自动拍单"


def test_playwright_runner_click_buy_now_can_follow_redirect_from_buy_api(monkeypatch):
    from strawberry_order_management.mock_auto_order_service import PlaywrightAutoOrderBrowserRunner

    page = _FakeBuyNowPage()
    runner = PlaywrightAutoOrderBrowserRunner()

    monkeypatch.setattr(PlaywrightAutoOrderBrowserRunner, "_click_by_text", lambda *args, **kwargs: True)

    runner._click_buy_now(page)

    assert page.visited == ["https://trade.jd.com/shopping/order/getOrderInfo.action?source=common"]
    assert page.url == "https://trade.jd.com/shopping/order/getOrderInfo.action?source=common"


def test_playwright_runner_extracts_desktop_product_url_from_mobile_product_url():
    from strawberry_order_management.mock_auto_order_service import PlaywrightAutoOrderBrowserRunner

    assert (
        PlaywrightAutoOrderBrowserRunner._extract_desktop_product_url(
            "https://item.m.jd.com/product/65714611165.html"
        )
        == "https://item.jd.com/65714611165.html"
    )


def test_playwright_runner_extracts_desktop_product_url_from_share_page_html():
    from strawberry_order_management.mock_auto_order_service import PlaywrightAutoOrderBrowserRunner

    html = '<html><script>window.__INIT_DATA__={"skuId":"65714611165"}</script></html>'

    assert (
        PlaywrightAutoOrderBrowserRunner._extract_desktop_product_url(
            "https://3.cn/2L319f-6?jkl=@I8zOk4E9UjwB@",
            html,
        )
        == "https://item.jd.com/65714611165.html"
    )


def test_playwright_runner_can_switch_share_link_page_to_desktop_product_page():
    from strawberry_order_management.mock_auto_order_service import PlaywrightAutoOrderBrowserRunner

    runner = PlaywrightAutoOrderBrowserRunner()
    page = _FakeProductLinkPage("https://item.m.jd.com/product/65714611165.html")
    debug_steps = []

    runner._ensure_desktop_product_page(page, debug_steps)

    assert page.visited == ["https://item.jd.com/65714611165.html"]
    assert page.url == "https://item.jd.com/65714611165.html"
    assert any("分享链接转商品页" in step["text"] for step in debug_steps)


def test_playwright_runner_rejects_unrecognized_share_link_before_clicking_buy_now():
    from strawberry_order_management.mock_auto_order_service import PlaywrightAutoOrderBrowserRunner

    runner = PlaywrightAutoOrderBrowserRunner()
    page = _FakeProductLinkPage("https://3.cn/2L319f-6?jkl=@I8zOk4E9UjwB@", "<html>no sku</html>")

    with pytest.raises(AutoOrderBrowserError, match="不是可直接拍单的京东商品页"):
        runner._ensure_desktop_product_page(page, [])


def test_playwright_runner_submit_order_accepts_cashier_url_without_ready_text(monkeypatch):
    from strawberry_order_management.mock_auto_order_service import PlaywrightAutoOrderBrowserRunner

    runner = PlaywrightAutoOrderBrowserRunner()
    page = _FakeSubmitOrderPage("https://cashier.jd.com/payment/pay.action?orderId=123")

    monkeypatch.setattr(PlaywrightAutoOrderBrowserRunner, "_click_by_text", lambda *args, **kwargs: True)
    monkeypatch.setattr(PlaywrightAutoOrderBrowserRunner, "_has_visible_text", lambda *args, **kwargs: False)

    runner._submit_order(page, [])


def test_playwright_runner_submit_order_captures_context_when_not_ready_to_pay(monkeypatch):
    from strawberry_order_management.mock_auto_order_service import PlaywrightAutoOrderBrowserRunner

    runner = PlaywrightAutoOrderBrowserRunner()
    page = _FakeSubmitOrderPage("https://trade.jd.com/shopping/order/getOrderInfo.action?source=common")
    debug_steps = [{"at": "2026-04-18 19:05:15", "text": "提交订单｜命中提交按钮"}]

    monkeypatch.setattr(PlaywrightAutoOrderBrowserRunner, "_click_by_text", lambda *args, **kwargs: True)
    monkeypatch.setattr(PlaywrightAutoOrderBrowserRunner, "_has_visible_text", lambda *args, **kwargs: False)
    monkeypatch.setattr(
        PlaywrightAutoOrderBrowserRunner,
        "_capture_failure_screenshot",
        lambda *args, **kwargs: "/tmp/not-ready-to-pay.png",
    )

    with pytest.raises(AutoOrderBrowserError, match="未到待付款页") as exc_info:
        runner._submit_order(page, debug_steps)

    exc = exc_info.value
    assert exc.debug_stage == "未到待付款页"
    assert exc.debug_screenshot_path == "/tmp/not-ready-to-pay.png"
    assert any("未到待付款页" in step["text"] for step in exc.debug_steps)


def test_playwright_runner_does_not_treat_item_page_login_word_as_real_login_page(monkeypatch):
    from strawberry_order_management.mock_auto_order_service import PlaywrightAutoOrderBrowserRunner

    runner = PlaywrightAutoOrderBrowserRunner()
    page = _FakeLoginHeuristicPage("https://item.jd.com/65714611165.html")

    monkeypatch.setattr(
        PlaywrightAutoOrderBrowserRunner,
        "_has_visible_text",
        lambda self, current_page, texts: "登录" in texts,
    )
    monkeypatch.setattr(PlaywrightAutoOrderBrowserRunner, "_has_visible_selector", lambda *args, **kwargs: False)

    assert runner._looks_like_login_page(page) is False


def test_playwright_runner_treats_settlement_page_as_existing_address_editor_context(monkeypatch):
    from strawberry_order_management.mock_auto_order_service import PlaywrightAutoOrderBrowserRunner

    runner = PlaywrightAutoOrderBrowserRunner()
    page = _FakeSettlementPage()

    monkeypatch.setattr(
        PlaywrightAutoOrderBrowserRunner,
        "_has_visible_selector",
        lambda self, current_page, selectors: any("consignee-item-wrap" in selector for selector in selectors),
    )

    runner._open_address_editor(page)


def test_playwright_runner_can_open_settlement_address_slot_editor_by_alias(monkeypatch):
    from strawberry_order_management.mock_auto_order_service import PlaywrightAutoOrderBrowserRunner

    runner = PlaywrightAutoOrderBrowserRunner()
    page = _FakeSettlementPage()

    monkeypatch.setattr(
        PlaywrightAutoOrderBrowserRunner,
        "_has_visible_text",
        lambda self, current_page, texts: "自动拍单" in texts,
    )
    monkeypatch.setattr(PlaywrightAutoOrderBrowserRunner, "_click_text_then_action", lambda *args, **kwargs: False)
    monkeypatch.setattr(PlaywrightAutoOrderBrowserRunner, "_click_by_text", lambda *args, **kwargs: False)
    monkeypatch.setattr(PlaywrightAutoOrderBrowserRunner, "_has_visible_selector", lambda *args, **kwargs: False)

    runner._open_address_slot_editor(page, "自动拍单")

    assert page.settlement_edit_label == "自动拍单"


def test_playwright_runner_can_reuse_matching_active_settlement_address(monkeypatch):
    from strawberry_order_management.mock_auto_order_service import PlaywrightAutoOrderBrowserRunner

    runner = PlaywrightAutoOrderBrowserRunner()
    page = _FakeSettlementPage()

    assert runner._settlement_active_address_matches(page, "请电话送货上门谢谢【5182】") is True


def test_playwright_runner_can_switch_to_existing_settlement_address(monkeypatch):
    from strawberry_order_management.mock_auto_order_service import PlaywrightAutoOrderBrowserRunner

    runner = PlaywrightAutoOrderBrowserRunner()
    page = _FakeSettlementPage()

    assert runner._settlement_active_address_matches(page, "请电话送货上门谢谢【6862】") is False
    assert runner._select_existing_settlement_address(page, "请电话送货上门谢谢【6862】") is True
    assert runner._settlement_active_address_matches(page, "请电话送货上门谢谢【6862】") is True


def test_playwright_runner_click_by_text_allow_partial_escapes_special_chars(monkeypatch):
    from strawberry_order_management.mock_auto_order_service import PlaywrightAutoOrderBrowserRunner

    class _FakeTextPage:
        def get_by_role(self, *args, **kwargs):
            raise AssertionError("should not reach role builder")

        def get_by_text(self, pattern):
            class _Locator:
                def __init__(self, compiled_pattern):
                    self.first = self
                    self._pattern = compiled_pattern

                def wait_for(self, state="visible", timeout=0):
                    return None

                def click(self, timeout=0):
                    return None

            assert pattern.search("+") is not None
            return _Locator(pattern)

        def locator(self, selector):
            raise AssertionError("should not fall back to locator builder")

    assert PlaywrightAutoOrderBrowserRunner._click_by_text(_FakeTextPage(), ("+",), allow_partial=True) is True


def test_playwright_runner_launches_google_chrome_channel():
    from strawberry_order_management.mock_auto_order_service import PlaywrightAutoOrderBrowserRunner

    context = _FakePlaywrightContext(_FakePlaywrightPage())
    chromium = _FakeChromiumLauncher(return_context=context)
    runner = PlaywrightAutoOrderBrowserRunner()

    launched_context = runner._launch_persistent_context(
        _FakePlaywrightRuntime(chromium),
        "/Users/gd/.jd/account-a",
    )

    assert launched_context is context
    assert chromium.calls[0]["channel"] == "chrome"
    assert chromium.calls[0]["user_data_dir"] == "/Users/gd/.jd/account-a"


def test_playwright_runner_keeps_browser_open_when_verification_is_triggered(monkeypatch):
    from strawberry_order_management.mock_auto_order_service import PlaywrightAutoOrderBrowserRunner

    page = _FakeVerificationPage("https://item.jd.com/1001.html")
    context = _FakePlaywrightContext(page)
    runner = PlaywrightAutoOrderBrowserRunner()

    monkeypatch.setattr(PlaywrightAutoOrderBrowserRunner, "validate_runtime", lambda self: None)
    monkeypatch.setattr(
        PlaywrightAutoOrderBrowserRunner,
        "_load_playwright",
        lambda self: (lambda: _FakeSyncPlaywright(), TimeoutError),
    )
    monkeypatch.setattr(
        PlaywrightAutoOrderBrowserRunner,
        "_launch_persistent_context",
        lambda self, playwright, account_environment: context,
    )
    monkeypatch.setattr(PlaywrightAutoOrderBrowserRunner, "_ensure_desktop_product_page", lambda *args, **kwargs: None)
    monkeypatch.setattr(PlaywrightAutoOrderBrowserRunner, "_looks_like_login_page", lambda *args, **kwargs: False)
    monkeypatch.setattr(
        PlaywrightAutoOrderBrowserRunner,
        "_click_buy_now",
        lambda self, current_page: setattr(current_page, "url", "https://aq.jd.com/captcha?scene=buy"),
    )
    monkeypatch.setattr(PlaywrightAutoOrderBrowserRunner, "_capture_failure_screenshot", lambda *args, **kwargs: "/tmp/verify.png")

    with pytest.raises(AutoOrderBrowserError, match="触发京东验证") as exc_info:
        runner.run_item(
            {
                "account_environment": "/Users/gd/.jd/account-a",
                "account_name": "京东主号",
                "jd_link": "https://item.jd.com/1001.html",
                "quantity": "1",
                "address_output_two": "",
            }
        )

    exc = exc_info.value
    assert exc.keep_browser_open is True
    assert exc.debug_stage == "点击立即购买"
    assert exc.debug_screenshot_path == "/tmp/verify.png"
    assert context.closed is False


def test_playwright_runner_derives_address_form_values_from_output_one():
    from strawberry_order_management.mock_auto_order_service import PlaywrightAutoOrderBrowserRunner

    runner = PlaywrightAutoOrderBrowserRunner()

    recipient_name, phone_number, address = runner._derive_address_form_values(
        "养乐多17834732441江苏省泰州市姜堰区三水街道锦联社区48号3单元306室"
    )

    assert recipient_name == "养乐多"
    assert phone_number == "17834732441"
    assert address == "江苏省泰州市姜堰区三水街道锦联社区48号3单元306室"


def test_playwright_runner_paste_address_output_can_fall_back_to_structured_form_fields(monkeypatch):
    from strawberry_order_management.mock_auto_order_service import PlaywrightAutoOrderBrowserRunner

    runner = PlaywrightAutoOrderBrowserRunner()
    page = _FakeSubmitOrderPage("https://trade.jd.com/shopping/order/getOrderInfo.action?source=common")
    filled = []

    def fake_fill_visible_input(current_page, selector, value):
        filled.append((selector, value))
        if "试试粘贴" in selector:
            return False
        if "收货人" in selector and value == "养乐多":
            return True
        if "手机" in selector and value == "17834732441":
            return True
        if "收货地址" in selector and value == "江苏省泰州市姜堰区三水街道锦联社区48号3单元306室":
            return True
        return False

    monkeypatch.setattr(PlaywrightAutoOrderBrowserRunner, "_fill_visible_input", staticmethod(fake_fill_visible_input))

    runner._paste_address_output(
        page,
        "养乐多17834732441江苏省泰州市姜堰区三水街道锦联社区48号3单元306室",
        recipient_name="",
        phone_number="",
        address="",
    )

    assert any("试试粘贴" in selector for selector, _ in filled)
    assert any("收货人" in selector and value == "养乐多" for selector, value in filled)
    assert any("手机" in selector and value == "17834732441" for selector, value in filled)
    assert any("收货地址" in selector and value == "江苏省泰州市姜堰区三水街道锦联社区48号3单元306室" for selector, value in filled)
