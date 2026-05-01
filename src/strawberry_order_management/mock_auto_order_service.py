from __future__ import annotations

import argparse
import json
import re
import threading
import time
import uuid
from copy import deepcopy
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Protocol
from urllib.parse import parse_qs, urlparse

from strawberry_order_management.services.auto_order import (
    AUTO_ORDER_ITEM_STATUS_FAILED,
    AUTO_ORDER_ITEM_STATUS_READY_TO_PAY,
    enabled_jd_accounts,
    now_timestamp,
)


def _text(value: Any) -> str:
    return str(value or "").strip()


@dataclass
class _QueuedTask:
    task_id: str
    payload: dict[str, Any]
    submitted_at: str
    updated_at: str
    task_status: str = "queued"
    message: str = "排队中"
    item_results: list[dict[str, Any]] | None = None
    debug_steps: list[dict[str, str]] | None = None
    debug_screenshot_path: str = ""
    debug_updated_at: str = ""
    debug_stage: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_status": self.task_status,
            "message": self.message,
            "submitted_at": self.submitted_at,
            "updated_at": self.updated_at,
            "item_results": deepcopy(self.item_results or []),
            "debug_steps": deepcopy(self.debug_steps or []),
            "debug_screenshot_path": self.debug_screenshot_path,
            "debug_updated_at": self.debug_updated_at,
            "debug_stage": self.debug_stage,
        }


class AutoOrderBrowserError(ValueError):
    def __init__(
        self,
        message: str,
        *,
        debug_steps: list[dict[str, str]] | None = None,
        debug_screenshot_path: str = "",
        debug_updated_at: str = "",
        debug_stage: str = "",
        keep_browser_open: bool = False,
    ) -> None:
        super().__init__(message)
        self.debug_steps = list(debug_steps or [])
        self.debug_screenshot_path = _text(debug_screenshot_path)
        self.debug_updated_at = _text(debug_updated_at)
        self.debug_stage = _text(debug_stage)
        self.keep_browser_open = bool(keep_browser_open)


class AutoOrderTaskProcessor(Protocol):
    def process_task(
        self,
        payload: dict[str, Any],
        on_item_result: Callable[[dict[str, Any]], None],
        on_debug_update: Callable[[dict[str, Any]], None] = lambda _payload: None,
    ) -> tuple[str, str, list[dict[str, Any]]]:
        ...

    def inspect_environment(self, payload: dict[str, Any]) -> dict[str, Any]:
        ...


class AutoOrderBrowserRunner(Protocol):
    def run_item(self, payload: dict[str, Any]) -> dict[str, Any] | str:
        ...

    def inspect_environment(self, payload: dict[str, Any]) -> dict[str, Any]:
        ...


class QueuedAutoOrderTaskStore:
    def __init__(self, processor: AutoOrderTaskProcessor) -> None:
        self._processor = processor
        self._tasks: dict[str, _QueuedTask] = {}
        self._queue: list[str] = []
        self._lock = threading.Lock()
        self._event = threading.Event()
        self._stop_event = threading.Event()
        self._worker = threading.Thread(target=self._work_loop, daemon=True)
        self._worker.start()

    def create_task(self, payload: dict[str, Any]) -> dict[str, Any]:
        timestamp = now_timestamp()
        task = _QueuedTask(
            task_id=str(uuid.uuid4()),
            payload=deepcopy(payload),
            submitted_at=timestamp,
            updated_at=timestamp,
            item_results=[],
            debug_steps=[],
        )
        with self._lock:
            self._tasks[task.task_id] = task
            self._queue.append(task.task_id)
        self._event.set()
        return task.to_dict()

    def inspect_environment(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._processor.inspect_environment(deepcopy(payload))

    def get_task(self, task_id: str) -> dict[str, Any]:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                raise KeyError(task_id)
            return task.to_dict()

    def stop(self) -> None:
        self._stop_event.set()
        self._event.set()
        self._worker.join(timeout=3)

    def _work_loop(self) -> None:
        while not self._stop_event.is_set():
            self._event.wait(0.1)
            if self._stop_event.is_set():
                break
            task_id = ""
            with self._lock:
                if self._queue:
                    task_id = self._queue.pop(0)
                else:
                    self._event.clear()
            if not task_id:
                continue
            self._process_task(task_id)

    def _process_task(self, task_id: str) -> None:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return
            task.task_status = "running"
            task.message = "执行中"
            task.updated_at = now_timestamp()
            payload = deepcopy(task.payload)

        def on_item_result(item_result: dict[str, Any]) -> None:
            with self._lock:
                current_task = self._tasks.get(task_id)
                if current_task is None:
                    return
                current_results = list(current_task.item_results or [])
                current_results.append(deepcopy(item_result))
                current_task.item_results = current_results
                current_task.updated_at = now_timestamp()

        def on_debug_update(debug_payload: dict[str, Any]) -> None:
            with self._lock:
                current_task = self._tasks.get(task_id)
                if current_task is None:
                    return
                if "debug_steps" in debug_payload:
                    current_task.debug_steps = deepcopy(list(debug_payload.get("debug_steps") or []))
                if "debug_screenshot_path" in debug_payload:
                    current_task.debug_screenshot_path = _text(debug_payload.get("debug_screenshot_path"))
                if "debug_updated_at" in debug_payload:
                    current_task.debug_updated_at = _text(debug_payload.get("debug_updated_at"))
                if "debug_stage" in debug_payload:
                    current_task.debug_stage = _text(debug_payload.get("debug_stage"))
                current_task.updated_at = now_timestamp()

        try:
            task_status, message, item_results = self._processor.process_task(payload, on_item_result, on_debug_update)
        except Exception as exc:  # pragma: no cover - defensive guard
            task_status = "failed"
            message = f"自动拍单服务内部异常：{exc}"
            item_results = []

        with self._lock:
            current_task = self._tasks.get(task_id)
            if current_task is None:
                return
            current_task.task_status = _text(task_status) or "failed"
            current_task.message = _text(message) or "存在失败采购位"
            current_task.item_results = deepcopy(item_results)
            current_task.updated_at = now_timestamp()


class SimulatedAutoOrderTaskProcessor:
    def __init__(self, processing_delay_seconds: float = 0.1) -> None:
        self._processing_delay_seconds = max(0.001, float(processing_delay_seconds))
        self._jd_order_counter = 8932000

    def process_task(
        self,
        payload: dict[str, Any],
        on_item_result: Callable[[dict[str, Any]], None],
        on_debug_update: Callable[[dict[str, Any]], None] = lambda _payload: None,
    ) -> tuple[str, str, list[dict[str, Any]]]:
        on_debug_update(
            {
                "debug_stage": "模拟服务执行中",
                "debug_updated_at": now_timestamp(),
                "debug_steps": [{"at": now_timestamp(), "text": "模拟服务开始处理任务"}],
                "debug_screenshot_path": "",
            }
        )
        procurement_items = list(payload.get("procurement_items") or [])
        item_results: list[dict[str, Any]] = []
        for item in procurement_items:
            time.sleep(self._processing_delay_seconds)
            result = self._build_item_result(item)
            item_results.append(result)
            on_item_result(result)
        statuses = [result["status"] for result in item_results]
        task_status = "succeeded" if statuses and all(status == AUTO_ORDER_ITEM_STATUS_READY_TO_PAY for status in statuses) else "failed"
        message = "已到待付款" if task_status == "succeeded" else "存在失败采购位"
        return task_status, message, item_results

    def inspect_environment(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "status": "success",
            "message": "模拟服务环境可用",
            "account_name": "",
            "checked_at": now_timestamp(),
            "checks": [
                {"label": "HTTP 服务连通", "status": "success", "message": "服务可访问"},
                {"label": "当前是否已登录京东", "status": "warning", "message": "模拟服务不检查登录态"},
                {"label": "自动拍单地址槽", "status": "warning", "message": "模拟服务不检查地址槽"},
            ],
        }

    def _build_item_result(self, item: dict[str, Any]) -> dict[str, Any]:
        procurement_index = int(item.get("procurement_index", 0))
        product_name = _text(item.get("product_name"))
        jd_link = _text(item.get("jd_link"))
        if not jd_link:
            return {
                "procurement_index": procurement_index,
                "status": AUTO_ORDER_ITEM_STATUS_FAILED,
                "account_name": "京东账号A",
                "jd_order_id": "",
                "error_message": "模拟服务检测到缺少京东链接",
                "last_run_at": now_timestamp(),
            }
        if any(flag in product_name.lower() for flag in ("fail", "失败", "error")):
            return {
                "procurement_index": procurement_index,
                "status": AUTO_ORDER_ITEM_STATUS_FAILED,
                "account_name": "京东账号A",
                "jd_order_id": "",
                "error_message": "模拟服务命中失败条件",
                "last_run_at": now_timestamp(),
            }
        self._jd_order_counter += 1
        return {
            "procurement_index": procurement_index,
            "status": AUTO_ORDER_ITEM_STATUS_READY_TO_PAY,
            "account_name": "京东账号A",
            "jd_order_id": f"JD{self._jd_order_counter}",
            "error_message": "",
            "last_run_at": now_timestamp(),
        }


class RealAutoOrderTaskProcessor:
    def __init__(
        self,
        *,
        browser_runner: AutoOrderBrowserRunner | None = None,
        address_slot_label: str = "自动拍单",
        stop_before_submit: bool = False,
    ) -> None:
        self._browser_runner = browser_runner or PlaywrightAutoOrderBrowserRunner()
        self._address_slot_label = _text(address_slot_label) or "自动拍单"
        self._stop_before_submit = bool(stop_before_submit)

    def process_task(
        self,
        payload: dict[str, Any],
        on_item_result: Callable[[dict[str, Any]], None],
        on_debug_update: Callable[[dict[str, Any]], None] = lambda _payload: None,
    ) -> tuple[str, str, list[dict[str, Any]]]:
        debug_steps: list[dict[str, str]] = []
        procurement_items = list(payload.get("procurement_items") or [])
        if not procurement_items:
            self._emit_debug(on_debug_update, debug_steps, "未找到可执行的采购位")
            return "failed", "未找到可执行的采购位", []

        preferred_account = self._preferred_account(payload.get("jd_accounts"))
        if preferred_account is None:
            self._append_step(debug_steps, "未找到可用京东账号环境")
            self._emit_debug(on_debug_update, debug_steps, "未找到可用京东账号环境")
            item_results = [
                self._failed_item_result(item, "", "请先在设置页启用至少一个京东账号环境")
                for item in procurement_items
            ]
            for result in item_results:
                on_item_result(result)
            return "failed", "请先在设置页启用至少一个京东账号环境", item_results

        account_name = _text(preferred_account.get("name"))
        account_environment = _text(preferred_account.get("environment"))
        self._append_step(debug_steps, f"选中账号环境：{account_name or '-'}")
        self._emit_debug(on_debug_update, debug_steps, f"选中账号环境：{account_name or '-'}")
        if not account_environment:
            self._append_step(debug_steps, "京东账号环境路径为空")
            self._emit_debug(on_debug_update, debug_steps, "京东账号环境路径为空")
            item_results = [
                self._failed_item_result(item, account_name, "请先填写京东账号环境路径后重试")
                for item in procurement_items
            ]
            for result in item_results:
                on_item_result(result)
            return "failed", "请先填写京东账号环境路径后重试", item_results

        address_output_one = _text(payload.get("address_output_one"))
        address_output_two = _text(payload.get("address_output_two"))
        if not address_output_one:
            self._append_step(debug_steps, "缺少地址提取结果一")
            self._emit_debug(on_debug_update, debug_steps, "缺少地址提取结果一")
            item_results = [
                self._failed_item_result(item, account_name, "缺少地址提取结果一")
                for item in procurement_items
            ]
            for result in item_results:
                on_item_result(result)
            return "failed", "缺少地址提取结果一", item_results

        item_results: list[dict[str, Any]] = []
        for item in procurement_items:
            jd_link = _text(item.get("jd_link"))
            if not jd_link:
                self._append_step(debug_steps, f"采购{int(item.get('procurement_index', 0)) + 1}缺少京东链接")
                self._emit_debug(on_debug_update, debug_steps, "缺少京东链接")
                result = self._failed_item_result(item, account_name, "缺少京东链接")
                item_results.append(result)
                on_item_result(result)
                continue
            run_payload = {
                "history_record_id": _text(payload.get("history_record_id")),
                "source": _text(payload.get("source")),
                "shop_name": _text(payload.get("shop_name")),
                "recipient_name": _text(payload.get("recipient_name")),
                "phone_number": _text(payload.get("phone_number")),
                "address": _text(payload.get("address")),
                "delivery_note": _text(payload.get("delivery_note")),
                "address_output_one": address_output_one,
                "address_output_two": address_output_two,
                "address_slot_label": self._address_slot_label,
                "account_name": account_name,
                "account_environment": account_environment,
                "procurement_index": int(item.get("procurement_index", 0)),
                "product_name": _text(item.get("product_name")),
                "quantity": _text(item.get("quantity")) or "1",
                "jd_link": jd_link,
                "stop_before_submit": self._stop_before_submit,
            }
            try:
                self._append_step(debug_steps, f"开始处理采购{run_payload['procurement_index'] + 1}")
                self._emit_debug(on_debug_update, debug_steps, f"开始处理采购{run_payload['procurement_index'] + 1}")
                runner_result = self._normalize_runner_result(self._browser_runner.run_item(run_payload))
                debug_steps = debug_steps + list(runner_result.get("debug_steps") or [])
                self._emit_debug(
                    on_debug_update,
                    debug_steps,
                    runner_result.get("debug_stage") or "到达待付款",
                    runner_result.get("debug_screenshot_path") or "",
                    runner_result.get("debug_updated_at") or now_timestamp(),
                )
                result = {
                    "procurement_index": run_payload["procurement_index"],
                    "status": AUTO_ORDER_ITEM_STATUS_READY_TO_PAY,
                    "account_name": account_name,
                    "jd_order_id": _text(runner_result.get("jd_order_id")),
                    "error_message": "",
                    "last_run_at": now_timestamp(),
                }
            except AutoOrderBrowserError as exc:
                debug_steps = debug_steps + list(getattr(exc, "debug_steps", []) or [])
                self._emit_debug(
                    on_debug_update,
                    debug_steps,
                    getattr(exc, "debug_stage", "") or str(exc),
                    getattr(exc, "debug_screenshot_path", ""),
                    getattr(exc, "debug_updated_at", "") or now_timestamp(),
                )
                result = self._failed_item_result(item, account_name, str(exc))
            item_results.append(result)
            on_item_result(result)

        statuses = [result["status"] for result in item_results]
        if statuses and all(status == AUTO_ORDER_ITEM_STATUS_READY_TO_PAY for status in statuses):
            self._emit_debug(on_debug_update, debug_steps, "到达待付款")
            return "succeeded", "已到待付款", item_results
        return "failed", self._summarize_failures(item_results), item_results

    def inspect_environment(self, payload: dict[str, Any]) -> dict[str, Any]:
        preferred_account = self._preferred_account(payload.get("jd_accounts"))
        if preferred_account is None:
            return {
                "status": "failed",
                "message": "请先在设置页启用至少一个京东账号环境",
                "account_name": "",
                "checked_at": now_timestamp(),
                "checks": [
                    {"label": "HTTP 服务连通", "status": "success", "message": "服务可访问"},
                    {"label": "京东账号环境", "status": "failed", "message": "未找到可用京东账号环境"},
                ],
            }
        account_name = _text(preferred_account.get("name"))
        account_environment = _text(preferred_account.get("environment"))
        if not account_environment:
            return {
                "status": "failed",
                "message": "请先填写京东账号环境路径后重试",
                "account_name": account_name,
                "checked_at": now_timestamp(),
                "checks": [
                    {"label": "HTTP 服务连通", "status": "success", "message": "服务可访问"},
                    {"label": "京东账号环境", "status": "failed", "message": "环境路径为空"},
                ],
            }
        inspect_payload = {
            "account_name": account_name,
            "account_environment": account_environment,
            "address_slot_label": self._address_slot_label,
        }
        try:
            result = dict(self._browser_runner.inspect_environment(inspect_payload))
        except AutoOrderBrowserError as exc:
            return {
                "status": "failed",
                "message": str(exc),
                "account_name": account_name,
                "checked_at": now_timestamp(),
                "checks": [
                    {"label": "HTTP 服务连通", "status": "success", "message": "服务可访问"},
                    {"label": "京东环境自检", "status": "failed", "message": str(exc)},
                ],
            }
        result.setdefault("status", "success")
        result.setdefault("message", "京东环境可用")
        result.setdefault("account_name", account_name)
        result.setdefault("checked_at", now_timestamp())
        result.setdefault("checks", [])
        return result

    @staticmethod
    def _preferred_account(accounts: Any) -> dict[str, Any] | None:
        candidates = enabled_jd_accounts(accounts)
        if not candidates:
            return None
        return candidates[0]

    @staticmethod
    def _append_step(steps: list[dict[str, str]], text: str) -> None:
        steps.append({"at": now_timestamp(), "text": _text(text)})

    @staticmethod
    def _emit_debug(
        callback: Callable[[dict[str, Any]], None],
        steps: list[dict[str, str]],
        stage: str,
        screenshot_path: str = "",
        updated_at: str = "",
    ) -> None:
        callback(
            {
                "debug_steps": deepcopy(steps),
                "debug_stage": _text(stage),
                "debug_screenshot_path": _text(screenshot_path),
                "debug_updated_at": _text(updated_at) or now_timestamp(),
            }
        )

    @staticmethod
    def _normalize_runner_result(value: dict[str, Any] | str) -> dict[str, Any]:
        if isinstance(value, dict):
            steps: list[dict[str, str]] = []
            for item in list(value.get("debug_steps") or []):
                if not isinstance(item, dict):
                    continue
                steps.append({"at": _text(item.get("at")), "text": _text(item.get("text"))})
            return {
                "jd_order_id": _text(value.get("jd_order_id")),
                "debug_stage": _text(value.get("debug_stage")),
                "debug_steps": steps,
                "debug_updated_at": _text(value.get("debug_updated_at")),
                "debug_screenshot_path": _text(value.get("debug_screenshot_path")),
            }
        return {
            "jd_order_id": _text(value),
            "debug_stage": "",
            "debug_steps": [],
            "debug_updated_at": "",
            "debug_screenshot_path": "",
        }

    @staticmethod
    def _failed_item_result(item: dict[str, Any], account_name: str, message: str) -> dict[str, Any]:
        return {
            "procurement_index": int(item.get("procurement_index", 0)),
            "status": AUTO_ORDER_ITEM_STATUS_FAILED,
            "account_name": _text(account_name),
            "jd_order_id": "",
            "error_message": _text(message),
            "last_run_at": now_timestamp(),
        }

    @staticmethod
    def _summarize_failures(item_results: list[dict[str, Any]]) -> str:
        parts = []
        for item in item_results:
            if _text(item.get("status")) != AUTO_ORDER_ITEM_STATUS_FAILED:
                continue
            procurement_index = int(item.get("procurement_index", 0)) + 1
            error_message = _text(item.get("error_message")) or "存在失败采购位"
            parts.append(f"采购{procurement_index}：{error_message}")
        return "；".join(parts) or "存在失败采购位"


class PlaywrightAutoOrderBrowserRunner:
    def __init__(self, *, operation_timeout_ms: int = 15000) -> None:
        self._operation_timeout_ms = max(1000, int(operation_timeout_ms))
        self._held_contexts: list[Any] = []

    def _load_playwright(self):
        try:
            from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
            from playwright.sync_api import sync_playwright
        except ImportError as exc:  # pragma: no cover - depends on optional runtime dependency
            raise AutoOrderBrowserError(
                "未安装 Playwright，请先执行 `pip install playwright` 并运行 `python -m playwright install chromium`"
            ) from exc
        return sync_playwright, PlaywrightTimeoutError

    @classmethod
    def validate_runtime(cls) -> None:
        sync_playwright, _ = cls()._load_playwright()
        cls._ensure_writable_directory(cls._failure_screenshot_dir(), "地址失败截图目录")
        try:
            with sync_playwright() as playwright:
                executable_path = Path(playwright.chromium.executable_path)
                if not executable_path.exists():
                    raise AutoOrderBrowserError(
                        "未安装 Chromium，请先执行 `python -m playwright install chromium`"
                    )
        except AutoOrderBrowserError:
            raise
        except Exception as exc:  # pragma: no cover - runtime only
            raise AutoOrderBrowserError(cls._friendly_runtime_error(str(exc))) from exc

    @classmethod
    def _failure_screenshot_dir(cls) -> Path:
        return Path.home() / ".config" / "strawberry-order-management" / "auto-order-failures"

    @classmethod
    def _ensure_writable_directory(cls, directory: Path, label: str) -> None:
        try:
            directory.mkdir(parents=True, exist_ok=True)
            probe = directory / f".write-test-{uuid.uuid4().hex}"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
        except Exception as exc:
            raise AutoOrderBrowserError(f"{label}不可写，请检查目录权限后重试") from exc

    @classmethod
    def _friendly_runtime_error(cls, raw_message: str) -> str:
        message = _text(raw_message)
        if "Executable doesn't exist" in message or "executable doesn't exist" in message:
            return "未安装 Chromium，请先执行 `python -m playwright install chromium`"
        return "真实自动拍单运行时初始化失败，请检查 Playwright / Chromium 环境"

    def _launch_persistent_context(self, playwright, account_environment: str):
        self._ensure_writable_directory(Path(account_environment), "浏览器环境目录")
        try:
            return playwright.chromium.launch_persistent_context(
                user_data_dir=account_environment,
                channel="chrome",
                headless=False,
                viewport={"width": 1366, "height": 920},
                args=["--disable-blink-features=AutomationControlled"],
            )
        except Exception as exc:  # pragma: no cover - runtime only
            raise AutoOrderBrowserError(self._friendly_runtime_error(str(exc))) from exc

    def inspect_environment(self, payload: dict[str, Any]) -> dict[str, Any]:
        account_name = _text(payload.get("account_name"))
        account_environment = _text(payload.get("account_environment"))
        address_slot_label = _text(payload.get("address_slot_label")) or "自动拍单"
        checks = [{"label": "HTTP 服务连通", "status": "success", "message": "服务可访问"}]
        if not account_environment:
            checks.append({"label": "京东账号环境", "status": "failed", "message": "环境路径为空"})
            return {
                "status": "failed",
                "message": "请先填写京东账号环境路径后重试",
                "account_name": account_name,
                "checked_at": now_timestamp(),
                "checks": checks,
            }
        self.validate_runtime()
        sync_playwright, PlaywrightTimeoutError = self._load_playwright()
        try:
            with sync_playwright() as playwright:
                context = self._launch_persistent_context(playwright, account_environment)
                try:
                    page = context.pages[0] if context.pages else context.new_page()
                    page.goto("https://www.jd.com", wait_until="domcontentloaded", timeout=self._operation_timeout_ms)
                    checks.append({"label": "京东账号环境", "status": "success", "message": "浏览器环境可打开"})
                    if self._looks_like_login_page(page):
                        checks.append({"label": "当前是否已登录京东", "status": "failed", "message": "请先手动登录该京东环境后重试"})
                        return {
                            "status": "failed",
                            "message": "请先手动登录该京东环境后重试",
                            "account_name": account_name,
                            "checked_at": now_timestamp(),
                            "checks": checks,
                        }
                    checks.append({"label": "当前是否已登录京东", "status": "success", "message": "已登录京东"})
                    page = self._open_home_address_book(page)
                    page.wait_for_timeout(1000)
                    if self._has_visible_text(page, (address_slot_label,)):
                        checks.append({"label": "自动拍单地址槽", "status": "success", "message": f"已找到{address_slot_label}地址槽"})
                        return {
                            "status": "success",
                            "message": "京东环境可用",
                            "account_name": account_name,
                            "checked_at": now_timestamp(),
                            "checks": checks,
                        }
                    checks.append({"label": "自动拍单地址槽", "status": "failed", "message": f"未找到{address_slot_label}标签地址"})
                    return {
                        "status": "failed",
                        "message": f"未找到{address_slot_label}标签地址",
                        "account_name": account_name,
                        "checked_at": now_timestamp(),
                        "checks": checks,
                    }
                finally:
                    context.close()
        except PlaywrightTimeoutError as exc:  # pragma: no cover - browser runtime only
            raise AutoOrderBrowserError("页面操作超时，请检查京东页面是否卡住") from exc
        except AutoOrderBrowserError:
            raise
        except Exception as exc:  # pragma: no cover - runtime only
            raise AutoOrderBrowserError("京东环境自检失败，请检查浏览器环境和账号登录状态") from exc

    def run_item(self, payload: dict[str, Any]) -> dict[str, Any]:
        account_environment = _text(payload.get("account_environment"))
        if not account_environment:
            raise AutoOrderBrowserError("请先填写京东账号环境路径后重试")

        self.validate_runtime()
        sync_playwright, PlaywrightTimeoutError = self._load_playwright()
        debug_steps: list[dict[str, str]] = []
        page = None
        try:
            with sync_playwright() as playwright:
                context = self._launch_persistent_context(playwright, account_environment)
                keep_context_open = False
                try:
                    page = context.pages[0] if context.pages else context.new_page()
                    self._step(debug_steps, "选中账号环境", f"账号：{_text(payload.get('account_name')) or '-'}")
                    page.goto(_text(payload.get("jd_link")), wait_until="domcontentloaded", timeout=self._operation_timeout_ms)
                    page.wait_for_timeout(1200)
                    self._ensure_desktop_product_page(page, debug_steps)
                    self._raise_if_verification_page(page, debug_steps, "打开商品链接")
                    self._step(debug_steps, "打开商品链接", "进入商品页", page)
                    if self._looks_like_login_page(page):
                        self._raise_with_context(page, "请先手动登录该京东环境后重试", debug_steps, "检查登录态")
                    self._step(debug_steps, "检查登录态", "未命中登录页", page)
                    self._click_buy_now(page)
                    self._raise_if_verification_page(page, debug_steps, "点击立即购买")
                    self._step(debug_steps, "点击立即购买", "命中立即购买按钮", page)
                    self._ensure_quantity(page, _text(payload.get("quantity")) or "1")
                    address_output_two = _text(payload.get("address_output_two"))
                    if self._settlement_active_address_matches(page, address_output_two):
                        self._step(debug_steps, "复用现有收货地址", "当前选中地址已匹配结果二", page)
                    elif self._select_existing_settlement_address(page, address_output_two):
                        self._step(debug_steps, "切换现有收货地址", "命中已有匹配地址", page)
                    else:
                        self._open_address_editor(page)
                        self._step(debug_steps, "进入/打开地址编辑", "命中收货地址入口", page)
                        self._open_address_slot_editor(page, _text(payload.get("address_slot_label")) or "自动拍单")
                        self._step(debug_steps, "找到自动拍单地址槽", "命中自动拍单标签地址", page)
                        self._paste_address_output(
                            page,
                            _text(payload.get("address_output_one")),
                            recipient_name=_text(payload.get("recipient_name")),
                            phone_number=_text(payload.get("phone_number")),
                            address=_text(payload.get("address")),
                        )
                        self._step(debug_steps, "粘贴结果一", "使用地址粘贴识别", page)
                        self._append_doorplate_suffix(page, address_output_two)
                        self._step(debug_steps, "追加结果二到门牌号", "补门牌号尾部", page)
                        self._confirm_address_editor(page)
                        self._raise_if_verification_page(page, debug_steps, "保存地址")
                        self._step(debug_steps, "保存地址", "命中确认按钮", page)
                    if bool(payload.get("stop_before_submit")):
                        self._step(
                            debug_steps,
                            "提交前检查点",
                            "已停在提交前检查点，请人工确认后关闭烟测开关再重试",
                            page,
                        )
                        self._raise_with_context(
                            page,
                            "已停在提交前检查点，请人工确认后关闭烟测开关再重试",
                            debug_steps,
                            "提交前检查点",
                        )
                    self._submit_order(page, debug_steps)
                    self._raise_if_verification_page(page, debug_steps, "提交订单")
                    self._step(debug_steps, "提交订单", "命中提交按钮", page)
                    if self._looks_like_login_page(page):
                        self._raise_with_context(page, "请先手动登录该京东环境后重试", debug_steps, "检查登录态")
                    self._step(debug_steps, "到达待付款", "命中待付款/收银台", page)
                    return {
                        "jd_order_id": self._extract_jd_order_id(page),
                        "debug_stage": "到达待付款",
                        "debug_steps": debug_steps,
                        "debug_updated_at": now_timestamp(),
                        "debug_screenshot_path": "",
                    }
                except AutoOrderBrowserError as exc:
                    if exc.keep_browser_open:
                        keep_context_open = True
                        self._held_contexts.append(context)
                    raise
                finally:
                    if not keep_context_open:
                        context.close()
        except PlaywrightTimeoutError as exc:  # pragma: no cover - browser runtime only
            raise AutoOrderBrowserError(
                "页面操作超时，请检查京东页面是否卡住",
                debug_steps=debug_steps,
                debug_screenshot_path=self._capture_failure_screenshot(page, "timeout"),
                debug_updated_at=now_timestamp(),
                debug_stage="页面操作超时",
            ) from exc
        except AutoOrderBrowserError:
            raise
        except Exception as exc:  # pragma: no cover - runtime only
            raise AutoOrderBrowserError(
                "真实自动拍单执行失败，请检查浏览器环境和京东页面",
                debug_steps=debug_steps,
                debug_screenshot_path=self._capture_failure_screenshot(page, "unexpected"),
                debug_updated_at=now_timestamp(),
                debug_stage="执行异常",
            ) from exc

    @staticmethod
    def _build_step_text(stage: str, detail: str = "", url: str = "") -> str:
        parts = [_text(stage)]
        if _text(detail):
            parts.append(_text(detail))
        if _text(url):
            parts.append(f"URL: {_text(url)}")
        return "｜".join(part for part in parts if part)

    @classmethod
    def _step(
        cls,
        debug_steps: list[dict[str, str]],
        stage: str,
        detail: str = "",
        page=None,
    ) -> None:  # pragma: no cover - browser runtime only
        debug_steps.append(
            {
                "at": now_timestamp(),
                "text": cls._build_step_text(stage, detail, cls._current_url(page)),
            }
        )

    def _raise_with_context(self, page, message: str, debug_steps: list[dict[str, str]], stage: str) -> None:
        raise AutoOrderBrowserError(
            message,
            debug_steps=debug_steps,
            debug_screenshot_path=self._capture_failure_screenshot(page, stage),
            debug_updated_at=now_timestamp(),
            debug_stage=stage,
        )

    def _raise_verification_with_context(self, page, debug_steps: list[dict[str, str]], stage: str) -> None:
        message = "触发京东验证，请在打开的 Google Chrome 窗口完成验证后手动重试"
        self._step(debug_steps, stage, "触发京东验证，等待人工处理", page)
        raise AutoOrderBrowserError(
            message,
            debug_steps=debug_steps,
            debug_screenshot_path=self._capture_failure_screenshot(page, stage),
            debug_updated_at=now_timestamp(),
            debug_stage=stage,
            keep_browser_open=True,
        )

    @staticmethod
    def _capture_failure_screenshot(page, stage: str) -> str:  # pragma: no cover - browser runtime only
        if page is None:
            return ""
        screenshot_dir = PlaywrightAutoOrderBrowserRunner._failure_screenshot_dir()
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{time.strftime('%Y%m%d-%H%M%S')}-{re.sub(r'[^0-9A-Za-z_-]+', '-', stage or 'failure')}.png"
        screenshot_path = screenshot_dir / filename
        try:
            page.screenshot(path=str(screenshot_path), full_page=True)
        except Exception:
            return ""
        return str(screenshot_path)

    @staticmethod
    def _current_url(page) -> str:  # pragma: no cover - browser runtime only
        if page is None:
            return ""
        try:
            return _text(page.url)
        except Exception:
            return ""

    def _looks_like_login_page(self, page) -> bool:  # pragma: no cover - browser runtime only
        url = _text(page.url).lower()
        if any(flag in url for flag in ("passport.jd.com", "plogin", "login")):
            return True
        if self._has_visible_selector(
            page,
            (
                "#formlogin",
                ".login-box",
                ".login-tab",
                "input[placeholder*='用户名']",
                "input[placeholder*='账号']",
                "input[placeholder*='手机号']",
                "input[placeholder*='短信验证码']",
            ),
        ):
            return True
        return self._has_visible_text(page, ("账号登录", "短信验证码登录", "扫码登录"))

    def _looks_like_verification_page(self, page) -> bool:  # pragma: no cover - browser runtime only
        url = _text(self._current_url(page)).lower()
        if any(
            flag in url
            for flag in (
                "captcha",
                "verify",
                "challenge",
                "aq.jd.com",
                "iv.jd.com",
                "security.jd.com",
            )
        ):
            return True
        if self._has_visible_selector(
            page,
            (
                "iframe[src*='captcha']",
                "iframe[src*='verify']",
                "div[class*='captcha']",
                "div[id*='captcha']",
                "div[class*='verify']",
                "div[class*='slider']",
                "canvas[class*='captcha']",
            ),
        ):
            return True
        return self._has_visible_text(
            page,
            (
                "安全验证",
                "请完成验证",
                "请进行验证",
                "拖动滑块",
                "向右滑动",
                "点击按钮进行验证",
                "验证后继续",
                "人机验证",
            ),
        )

    def _raise_if_verification_page(self, page, debug_steps: list[dict[str, str]], stage: str) -> None:
        if self._looks_like_verification_page(page):
            self._raise_verification_with_context(page, debug_steps, stage)

    def _click_buy_now(self, page) -> None:  # pragma: no cover - browser runtime only
        buy_response = None
        try:
            with page.expect_response(
                lambda response: "functionId=pcCart_jc_buyNow" in _text(getattr(response, "url", "")),
                timeout=3000,
            ) as response_info:
                if not self._trigger_buy_now_click(page):
                    raise AutoOrderBrowserError("未找到立即购买按钮")
            buy_response = self._response_json(response_info.value)
        except AutoOrderBrowserError:
            raise
        except Exception:
            if not self._trigger_buy_now_click(page):
                raise AutoOrderBrowserError("未找到立即购买按钮")
        page.wait_for_timeout(1000)
        redirect_url = self._buy_now_redirect_url(buy_response)
        if redirect_url and "item.jd.com/" in _text(getattr(page, "url", "")):
            page.goto(redirect_url, wait_until="domcontentloaded", timeout=self._operation_timeout_ms)
            page.wait_for_timeout(1200)

    def _ensure_desktop_product_page(self, page, debug_steps: list[dict[str, str]]) -> None:  # pragma: no cover
        current_url = self._current_url(page)
        if "item.jd.com/" in current_url:
            return
        page_html = self._safe_page_content(page)
        desktop_url = self._extract_desktop_product_url(current_url, page_html)
        if desktop_url:
            page.goto(desktop_url, wait_until="domcontentloaded", timeout=self._operation_timeout_ms)
            page.wait_for_timeout(800)
            self._step(debug_steps, "分享链接转商品页", f"切换到桌面商品页：{desktop_url}", page)
            return
        if self._looks_like_share_or_mobile_jd_link(current_url):
            raise AutoOrderBrowserError("当前链接不是可直接拍单的京东商品页，像是分享/活动/订单页，请换商品页链接")

    @staticmethod
    def _safe_page_content(page) -> str:  # pragma: no cover
        try:
            return _text(page.content())
        except Exception:
            return ""

    @classmethod
    def _extract_desktop_product_url(cls, candidate_url: str, page_html: str = "") -> str:
        url_text = _text(candidate_url)
        product_id = cls._extract_product_id_from_url(url_text)
        if not product_id:
            product_id = cls._extract_product_id_from_html(page_html)
        if not product_id:
            return ""
        return f"https://item.jd.com/{product_id}.html"

    @staticmethod
    def _extract_product_id_from_url(candidate_url: str) -> str:
        url_text = _text(candidate_url)
        if not url_text:
            return ""
        for pattern in (
            r"https?://item\.jd\.com/(\d+)\.html",
            r"https?://item\.m\.jd\.com/product/(\d+)\.html",
            r"[?&](?:sku|skuId|wareId|itemId)=(\d+)",
        ):
            match = re.search(pattern, url_text, re.IGNORECASE)
            if match:
                return _text(match.group(1))
        parsed = urlparse(url_text)
        query = parse_qs(parsed.query)
        for key in ("sku", "skuId", "wareId", "itemId"):
            values = query.get(key) or query.get(key.lower()) or query.get(key.upper())
            if not values:
                continue
            value = _text(values[0])
            if value.isdigit():
                return value
        return ""

    @staticmethod
    def _extract_product_id_from_html(page_html: str) -> str:
        html = _text(page_html)
        if not html:
            return ""
        for pattern in (
            r'"skuId"\s*:\s*"(\d+)"',
            r'"wareId"\s*:\s*"(\d+)"',
            r'"itemId"\s*:\s*"(\d+)"',
            r"\bskuId\s*[:=]\s*['\"]?(\d+)",
            r"\bwareId\s*[:=]\s*['\"]?(\d+)",
        ):
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                return _text(match.group(1))
        return ""

    @staticmethod
    def _looks_like_share_or_mobile_jd_link(candidate_url: str) -> bool:
        parsed = urlparse(_text(candidate_url))
        host = (parsed.netloc or "").lower()
        if host.startswith("item.jd.com"):
            return False
        return host in {
            "3.cn",
            "u.jd.com",
            "item.m.jd.com",
            "wqitem.jd.com",
            "wqs.jd.com",
            "pro.m.jd.com",
            "h5.m.jd.com",
            "m.jd.com",
        }

    def _trigger_buy_now_click(self, page) -> bool:  # pragma: no cover - browser runtime only
        for selector in (
            ".page-right-RightBtns .bottom-btns-root > div:nth-child(2)",
            ".page-right-RightBtns .bottom-btns-root > div:last-child",
            ".page-right-suctionbottom .bottom-btns-root > div:nth-child(2)",
        ):
            if self._js_click_selector(page, selector):
                return True
        return self._click_by_text(page, ("立即购买", "马上抢", "立即抢购", "抢购", "立即下单"))

    @staticmethod
    def _js_click_selector(page, selector: str) -> bool:  # pragma: no cover
        try:
            locator = page.locator(selector).first
            locator.wait_for(state="visible", timeout=1200)
            locator.evaluate("(node) => { node.click(); return true; }", timeout=1200)
            return True
        except Exception:
            return False

    @staticmethod
    def _response_json(response) -> dict[str, Any]:  # pragma: no cover - browser runtime only
        if response is None:
            return {}
        try:
            payload = response.json()
        except Exception:
            return {}
        return payload if isinstance(payload, dict) else {}

    @staticmethod
    def _buy_now_redirect_url(payload: dict[str, Any] | None) -> str:  # pragma: no cover - browser runtime only
        if not isinstance(payload, dict):
            return ""
        if not payload.get("success"):
            return ""
        redirect_url = _text(payload.get("url"))
        if not redirect_url:
            return ""
        if redirect_url.startswith("//"):
            return f"https:{redirect_url}"
        if redirect_url.startswith("/"):
            return f"https://trade.jd.com{redirect_url}"
        return redirect_url

    def _ensure_quantity(self, page, quantity: str) -> None:  # pragma: no cover - browser runtime only
        normalized_quantity = max(1, int(quantity or "1"))
        if normalized_quantity <= 1:
            return
        selectors = (
            "input[aria-label*='数量']",
            "input[placeholder*='数量']",
            "input[name*='quantity']",
            "input[type='number']",
        )
        for selector in selectors:
            if self._fill_visible_input(page, selector, str(normalized_quantity)):
                page.wait_for_timeout(300)
                return
        plus_patterns = ("+", "增加", "加")
        for _ in range(normalized_quantity - 1):
            if not self._click_by_text(page, plus_patterns, allow_partial=True):
                raise AutoOrderBrowserError("未能设置采购数量")
            page.wait_for_timeout(200)

    def _open_address_editor(self, page) -> None:  # pragma: no cover - browser runtime only
        if self._has_visible_selector(
            page,
            (
                "textarea[placeholder*='试试粘贴']",
                "textarea[placeholder*='收件人姓名']",
                "input[placeholder*='试试粘贴']",
                "div[class*='consignee-item-wrap']",
            ),
        ):
            return
        if self._click_by_text(
            page,
            ("新增收货地址", "编辑收货地址", "管理收货地址", "修改地址", "更换地址", "使用新地址", "收货地址"),
        ):
            page.wait_for_timeout(1000)
            return
        raise AutoOrderBrowserError("未找到收货地址入口")

    def _open_address_slot_editor(self, page, address_slot_label: str) -> None:  # pragma: no cover - browser runtime only
        if not address_slot_label:
            raise AutoOrderBrowserError("缺少自动拍单地址槽标签")
        if not self._has_visible_text(page, (address_slot_label,)):
            raise AutoOrderBrowserError(f"未找到{address_slot_label}标签地址")
        if self._click_settlement_slot_editor(page, address_slot_label):
            page.wait_for_timeout(800)
            return
        if self._click_easybuy_slot_editor(page, address_slot_label):
            page.wait_for_timeout(800)
            return
        if self._click_text_then_action(page, address_slot_label, ("编辑", "修改", "管理")):
            page.wait_for_timeout(800)
            return
        if self._click_by_text(page, ("编辑", "修改", "管理"), allow_partial=True):
            page.wait_for_timeout(800)
            return
        if self._has_visible_selector(
            page,
            (
                "textarea[placeholder*='试试粘贴']",
                "textarea[placeholder*='收件人姓名']",
                "input[placeholder*='试试粘贴']",
            ),
        ):
            return
        raise AutoOrderBrowserError(f"未找到{address_slot_label}标签地址")

    def _open_home_address_book(self, page):  # pragma: no cover - browser runtime only
        page.goto("https://home.jd.com/", wait_until="domcontentloaded", timeout=self._operation_timeout_ms)
        page.wait_for_timeout(1000)
        self._dismiss_home_guide(page)
        known_pages = self._known_context_pages(page)
        if self._click_visible_selector(page, "div[class*='addressLink']"):
            page.wait_for_timeout(1200)
            return self._resolve_popup_page(page, known_pages)
        if self._click_visible_selector(page, "a[href*='easybuy.jd.com/address/getEasyBuyList.action']"):
            page.wait_for_timeout(1200)
            return self._resolve_popup_page(page, known_pages)
        if self._click_by_text(page, ("地址管理",), allow_partial=True):
            page.wait_for_timeout(1200)
            return self._resolve_popup_page(page, known_pages)
        raise AutoOrderBrowserError("未找到地址管理入口")

    @staticmethod
    def _dismiss_home_guide(page) -> None:  # pragma: no cover - browser runtime only
        try:
            locator = page.locator("div[class*='guide_close']").first
            locator.wait_for(state="visible", timeout=800)
            locator.click(timeout=800)
        except Exception:
            return

    @staticmethod
    def _known_context_pages(page) -> list[Any]:  # pragma: no cover - browser runtime only
        context = getattr(page, "context", None)
        if context is None:
            return [page]
        if callable(context):
            try:
                context = context()
            except Exception:
                return [page]
        pages = getattr(context, "pages", None)
        return list(pages or [page])

    def _resolve_popup_page(self, page, known_pages: list[Any]):  # pragma: no cover - browser runtime only
        current_pages = self._known_context_pages(page)
        for candidate in current_pages:
            if candidate not in known_pages:
                self._wait_domcontentloaded(candidate)
                return candidate
        self._wait_domcontentloaded(page)
        return page

    def _wait_domcontentloaded(self, page) -> None:  # pragma: no cover - browser runtime only
        try:
            page.wait_for_load_state("domcontentloaded", timeout=self._operation_timeout_ms)
        except Exception:
            return

    @staticmethod
    def _click_settlement_slot_editor(page, address_slot_label: str) -> bool:  # pragma: no cover - browser runtime only
        if "trade.jd.com/shopping/order/getOrderInfo.action" not in _text(getattr(page, "url", "")):
            return False
        try:
            return bool(
                page.evaluate(
                    """
                    (label) => {
                      const normalize = (value) => String(value || "").replace(/\\s+/g, " ").trim();
                      const wraps = Array.from(document.querySelectorAll("div[class*='consignee-item-wrap']"));
                      const target = wraps.find((wrap) => normalize(wrap.innerText).includes(label));
                      if (!target) {
                        return false;
                      }
                      const edit = Array.from(target.querySelectorAll("div, span, button, a")).find((node) => {
                        return normalize(node.innerText) === "编辑";
                      });
                      if (!edit) {
                        return false;
                      }
                      edit.click();
                      return true;
                    }
                    """,
                    address_slot_label,
                )
            )
        except Exception:
            return False

    @staticmethod
    def _settlement_active_address_matches(page, address_output_two: str) -> bool:  # pragma: no cover - browser runtime only
        if "trade.jd.com/shopping/order/getOrderInfo.action" not in _text(getattr(page, "url", "")):
            return False
        if not _text(address_output_two):
            return False
        try:
            return bool(
                page.evaluate(
                    """
                    (needle) => {
                      const normalize = (value) => String(value || "").replace(/\\s+/g, " ").trim();
                      const active =
                        document.querySelector("div[class*='consignee-item-'][class*='active']") ||
                        document.querySelector("div[class*='consignee-item-wrap'] div[class*='active']");
                      if (!active) {
                        return false;
                      }
                      return normalize(active.innerText).includes(normalize(needle));
                    }
                    """,
                    address_output_two,
                )
            )
        except Exception:
            return False

    @staticmethod
    def _select_existing_settlement_address(page, address_output_two: str) -> bool:  # pragma: no cover - browser runtime only
        if "trade.jd.com/shopping/order/getOrderInfo.action" not in _text(getattr(page, "url", "")):
            return False
        if not _text(address_output_two):
            return False
        PlaywrightAutoOrderBrowserRunner._click_by_text(page, ("展开全部地址", "更多地址"), allow_partial=True)
        try:
            clicked = bool(
                page.evaluate(
                    """
                    (needle) => {
                      const normalize = (value) => String(value || "").replace(/\\s+/g, " ").trim();
                      const cards = Array.from(document.querySelectorAll("div[class*='consignee-item-wrap']"));
                      const target = cards.find((card) => normalize(card.innerText).includes(normalize(needle)));
                      if (!target) {
                        return false;
                      }
                      const clickable =
                        target.querySelector("div[class*='consignee-item']") ||
                        target.querySelector("li") ||
                        target;
                      clickable.click();
                      return true;
                    }
                    """,
                    address_output_two,
                )
            )
        except Exception:
            clicked = False
        if not clicked:
            clicked = PlaywrightAutoOrderBrowserRunner._click_visible_text(page, address_output_two)
        if not clicked:
            return False
        try:
            page.wait_for_timeout(800)
        except Exception:
            return False
        return PlaywrightAutoOrderBrowserRunner._settlement_active_address_matches(page, address_output_two)

    @staticmethod
    def _click_easybuy_slot_editor(page, address_slot_label: str) -> bool:  # pragma: no cover - browser runtime only
        if "easybuy.jd.com/address/getEasyBuyList.action" not in _text(getattr(page, "url", "")):
            return False
        try:
            return bool(
                page.evaluate(
                    """
                    (label) => {
                      const normalize = (value) => String(value || "").replace(/\\s+/g, " ").trim();
                      const cards = Array.from(document.querySelectorAll(".sm.easebuy-m, .easebuy-m"));
                      const target = cards.find((card) => normalize(card.innerText).includes(label));
                      if (!target) {
                        return false;
                      }
                      const edit =
                        target.querySelector("a[onclick^='alertUpdateAddressDiagByoverseas']") ||
                        Array.from(target.querySelectorAll("a, button, span")).find((node) =>
                          /编辑|修改|管理/.test(normalize(node.innerText))
                        );
                      if (!edit) {
                        return false;
                      }
                      edit.click();
                      return true;
                    }
                    """,
                    address_slot_label,
                )
            )
        except Exception:
            return False

    @staticmethod
    def _derive_address_form_values(
        address_output_one: str,
        *,
        recipient_name: str = "",
        phone_number: str = "",
        address: str = "",
    ) -> tuple[str, str, str]:
        resolved_recipient = _text(recipient_name)
        resolved_phone = _text(phone_number)
        resolved_address = _text(address)
        inline_match = re.match(r"^(?P<name>.+?)(?P<phone>\d{11})(?P<address>.+)$", _text(address_output_one))
        if inline_match is not None:
            resolved_recipient = resolved_recipient or _text(inline_match.group("name"))
            resolved_phone = resolved_phone or _text(inline_match.group("phone"))
            resolved_address = resolved_address or _text(inline_match.group("address"))
        return resolved_recipient, resolved_phone, resolved_address

    def _fill_address_form_fields(
        self,
        page,
        *,
        recipient_name: str,
        phone_number: str,
        address: str,
    ) -> bool:  # pragma: no cover - browser runtime only
        field_specs = (
            (
                _text(recipient_name),
                (
                    "input[placeholder*='收货人']",
                    "textarea[placeholder*='收货人']",
                    "input[placeholder*='姓名']",
                    "textarea[placeholder*='姓名']",
                ),
            ),
            (
                _text(phone_number),
                (
                    "input[placeholder*='手机']",
                    "textarea[placeholder*='手机']",
                    "input[placeholder*='电话']",
                    "input[type='tel']",
                ),
            ),
            (
                _text(address),
                (
                    "input[placeholder*='收货地址']",
                    "textarea[placeholder*='收货地址']",
                    "input[placeholder*='详细地址']",
                    "textarea[placeholder*='详细地址']",
                    "input[placeholder*='选择收货地址']",
                    "textarea[placeholder*='选择收货地址']",
                    "input[placeholder*='所在地区']",
                ),
            ),
        )
        filled_any = False
        for value, selectors in field_specs:
            if not value:
                continue
            field_filled = False
            for selector in selectors:
                if self._fill_visible_input(page, selector, value):
                    page.wait_for_timeout(300)
                    field_filled = True
                    filled_any = True
                    break
            if not field_filled:
                return False
        return filled_any

    def _paste_address_output(
        self,
        page,
        address_output_one: str,
        *,
        recipient_name: str = "",
        phone_number: str = "",
        address: str = "",
    ) -> None:  # pragma: no cover - browser runtime only
        if not address_output_one:
            raise AutoOrderBrowserError("缺少地址提取结果一")
        selectors = (
            "textarea[placeholder*='试试粘贴']",
            "textarea[placeholder*='收件人姓名']",
            "input[placeholder*='试试粘贴']",
        )
        for selector in selectors:
            if self._fill_visible_input(page, selector, address_output_one):
                page.keyboard.press("Tab")
                page.wait_for_timeout(1200)
                return
        resolved_recipient, resolved_phone, resolved_address = self._derive_address_form_values(
            address_output_one,
            recipient_name=recipient_name,
            phone_number=phone_number,
            address=address,
        )
        if self._fill_address_form_fields(
            page,
            recipient_name=resolved_recipient,
            phone_number=resolved_phone,
            address=resolved_address,
        ):
            page.wait_for_timeout(800)
            return
        raise AutoOrderBrowserError("地址粘贴识别失败")

    def _append_doorplate_suffix(self, page, address_output_two: str) -> None:  # pragma: no cover - browser runtime only
        if not address_output_two:
            return
        selectors = (
            "input[placeholder*='门牌']",
            "textarea[placeholder*='门牌']",
            "input[placeholder*='6栋201']",
            "input[placeholder*='例：']",
        )
        for selector in selectors:
            current_value = self._visible_input_value(page, selector)
            if current_value is None:
                continue
            merged = f"{current_value} {address_output_two}".strip() if current_value else address_output_two
            if self._fill_visible_input(page, selector, merged):
                page.wait_for_timeout(300)
                return
        raise AutoOrderBrowserError("未找到门牌号输入框")

    def _confirm_address_editor(self, page) -> None:  # pragma: no cover - browser runtime only
        if self._click_by_text(page, ("确认", "保存", "使用该地址")):
            page.wait_for_timeout(1200)
            return
        raise AutoOrderBrowserError("地址保存失败")

    def _submit_order(self, page, debug_steps: list[dict[str, str]]) -> None:  # pragma: no cover - browser runtime only
        if not self._click_by_text(page, ("提交订单", "去支付", "提交并支付", "立即支付")):
            self._step(debug_steps, "未到待付款页", "未命中提交/支付按钮", page)
            self._raise_with_context(page, "未到待付款页", debug_steps, "未到待付款页")
        page.wait_for_timeout(1500)
        if self._looks_like_ready_to_pay_page(page):
            return
        self._step(debug_steps, "未到待付款页", "提交后未识别到收银台/待付款页", page)
        self._raise_with_context(page, "未到待付款页", debug_steps, "未到待付款页")

    def _looks_like_ready_to_pay_page(self, page) -> bool:  # pragma: no cover - browser runtime only
        current_url = self._current_url(page).lower()
        if any(
            token in current_url
            for token in (
                "cashier.jd.com",
                "pay.jd.com",
                "payment.jd.com",
                "trade.jd.com/payment",
                "trade.jd.com/pay",
                "pcashier",
                "cashier",
            )
        ):
            return True
        if self._has_visible_text(page, ("待付款", "收银台", "订单提交成功", "付款方式", "支付剩余时间", "支付订单")):
            return True
        return False

    @staticmethod
    def _click_text_then_action(page, anchor_text: str, actions: tuple[str, ...]) -> bool:  # pragma: no cover
        try:
            anchor_locator = page.get_by_text(anchor_text).first
            anchor_locator.wait_for(state="visible", timeout=1200)
            container = anchor_locator.locator("xpath=ancestor::*[self::div or self::li or self::section][1]")
            for action in actions:
                action_locator = container.get_by_text(action).first
                action_locator.wait_for(state="visible", timeout=800)
                action_locator.click(timeout=800)
                return True
        except Exception:
            return False
        return False

    @staticmethod
    def _click_by_text(page, texts: tuple[str, ...], *, allow_partial: bool = False) -> bool:  # pragma: no cover
        for text in texts:
            patterns = (
                [re.compile(re.escape(text))]
                if allow_partial
                else [re.compile(f"^{re.escape(text)}$"), re.compile(re.escape(text))]
            )
            for pattern in patterns:
                for builder in (
                    lambda: page.get_by_role("button", name=pattern).first,
                    lambda: page.get_by_text(pattern).first,
                    lambda: page.locator(f"text=/{pattern.pattern}/").first,
                ):
                    try:
                        locator = builder()
                        locator.wait_for(state="visible", timeout=1200)
                        locator.click(timeout=1200)
                        return True
                    except Exception:
                        continue
        return False

    @staticmethod
    def _click_visible_text(page, text: str) -> bool:  # pragma: no cover
        pattern = re.compile(re.escape(text))
        for builder in (
            lambda: page.get_by_text(pattern).first,
            lambda: page.locator(f"text=/{pattern.pattern}/").first,
        ):
            try:
                locator = builder()
                locator.wait_for(state="visible", timeout=1200)
                locator.click(timeout=1200)
                return True
            except Exception:
                continue
        return False

    @staticmethod
    def _click_visible_selector(page, selector: str) -> bool:  # pragma: no cover
        try:
            locator = page.locator(selector).first
            locator.wait_for(state="visible", timeout=1200)
            locator.click(timeout=1200)
            return True
        except Exception:
            return False

    @staticmethod
    def _fill_visible_input(page, selector: str, value: str) -> bool:  # pragma: no cover
        try:
            locator = page.locator(selector).first
            locator.wait_for(state="visible", timeout=1200)
            locator.click(timeout=1200)
            locator.fill(value, timeout=1200)
            return True
        except Exception:
            return False

    @staticmethod
    def _visible_input_value(page, selector: str) -> str | None:  # pragma: no cover
        try:
            locator = page.locator(selector).first
            locator.wait_for(state="visible", timeout=1200)
            return _text(locator.input_value(timeout=1200))
        except Exception:
            return None

    @staticmethod
    def _has_visible_selector(page, selectors: tuple[str, ...]) -> bool:  # pragma: no cover
        for selector in selectors:
            try:
                locator = page.locator(selector).first
                locator.wait_for(state="visible", timeout=800)
                return True
            except Exception:
                continue
        return False

    @staticmethod
    def _has_visible_text(page, texts: tuple[str, ...]) -> bool:  # pragma: no cover
        for text in texts:
            try:
                locator = page.get_by_text(re.compile(text)).first
                locator.wait_for(state="visible", timeout=800)
                return True
            except Exception:
                continue
        return False

    @staticmethod
    def _extract_jd_order_id(page) -> str:  # pragma: no cover - browser runtime only
        candidates = []
        try:
            content = page.content()
            candidates.append(content)
        except Exception:
            pass
        try:
            candidates.append(_text(page.url))
        except Exception:
            pass
        patterns = (
            re.compile(r"订单号[:：\s]*([A-Z]{0,4}\d{6,})"),
            re.compile(r"orderId[=/]([A-Z]{0,4}\d{6,})", re.IGNORECASE),
            re.compile(r"\b(JD\d{6,})\b"),
        )
        for candidate in candidates:
            for pattern in patterns:
                match = pattern.search(candidate)
                if match:
                    return _text(match.group(1))
        return ""


class BaseAutoOrderHttpServer:
    def __init__(
        self,
        *,
        host: str,
        port: int,
        api_key: str,
        task_store: QueuedAutoOrderTaskStore,
    ) -> None:
        self.host = host
        self.port = int(port)
        self.api_key = api_key
        self._task_store = task_store
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._httpd is not None:
            return
        server = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args) -> None:  # noqa: A003
                return

            def do_POST(self) -> None:  # noqa: N802
                if not self._authorize():
                    return
                parsed = urlparse(self.path)
                if parsed.path == "/auto-order/check":
                    payload = self._read_json_body()
                    result = server._task_store.inspect_environment(payload)
                    self._write_json(200, result)
                    return
                if parsed.path != "/auto-order/tasks":
                    self._write_json(404, {"message": "未找到自动拍单路径"})
                    return
                payload = self._read_json_body()
                task = server._task_store.create_task(payload)
                self._write_json(200, task)

            def do_GET(self) -> None:  # noqa: N802
                if not self._authorize():
                    return
                parsed = urlparse(self.path)
                prefix = "/auto-order/tasks/"
                if not parsed.path.startswith(prefix):
                    self._write_json(404, {"message": "未找到自动拍单路径"})
                    return
                task_id = parsed.path[len(prefix) :]
                try:
                    task = server._task_store.get_task(task_id)
                except KeyError:
                    self._write_json(404, {"message": "未找到自动拍单任务"})
                    return
                self._write_json(200, task)

            def _authorize(self) -> bool:
                expected = f"Bearer {server.api_key}"
                actual = _text(self.headers.get("Authorization"))
                if actual == expected:
                    return True
                self._write_json(401, {"message": "未授权的自动拍单请求"})
                return False

            def _read_json_body(self) -> dict[str, Any]:
                content_length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(content_length) if content_length else b"{}"
                try:
                    payload = json.loads(raw.decode("utf-8") or "{}")
                except json.JSONDecodeError:
                    payload = {}
                return payload if isinstance(payload, dict) else {}

            def _write_json(self, status_code: int, payload: dict[str, Any]) -> None:
                body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self.send_response(status_code)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self._httpd = ThreadingHTTPServer((self.host, self.port), Handler)
        self.host, self.port = self._httpd.server_address[:2]
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None
        if self._thread is not None:
            self._thread.join(timeout=3)
            self._thread = None
        self._task_store.stop()

    def url(self, path: str = "") -> str:
        normalized_path = "/" + path.lstrip("/")
        return f"http://{self.host}:{self.port}{normalized_path}"


class MockAutoOrderHttpServer(BaseAutoOrderHttpServer):
    def __init__(
        self,
        *,
        host: str = "127.0.0.1",
        port: int = 9000,
        api_key: str = "bridge-key",
        processing_delay_seconds: float = 0.1,
    ) -> None:
        super().__init__(
            host=host,
            port=port,
            api_key=api_key,
            task_store=QueuedAutoOrderTaskStore(
                SimulatedAutoOrderTaskProcessor(processing_delay_seconds=processing_delay_seconds)
            ),
        )


class RealAutoOrderHttpServer(BaseAutoOrderHttpServer):
    def __init__(
        self,
        *,
        host: str = "127.0.0.1",
        port: int = 9000,
        api_key: str = "bridge-key",
        browser_runner: AutoOrderBrowserRunner | None = None,
        address_slot_label: str = "自动拍单",
        stop_before_submit: bool = False,
    ) -> None:
        super().__init__(
            host=host,
            port=port,
            api_key=api_key,
            task_store=QueuedAutoOrderTaskStore(
                RealAutoOrderTaskProcessor(
                    browser_runner=browser_runner,
                    address_slot_label=address_slot_label,
                    stop_before_submit=stop_before_submit,
                )
            ),
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="草莓订单管理系统 - 本地自动拍单模拟服务")
    parser.add_argument("--real", action="store_true", help="启动真实自动拍单服务")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9000)
    parser.add_argument("--api-key", default="bridge-key")
    parser.add_argument("--processing-delay", type=float, default=0.15)
    parser.add_argument("--address-slot-label", default="自动拍单")
    parser.add_argument(
        "--stop-before-submit",
        action="store_true",
        help="烟测模式：跑到提交订单前最后一步就停止，不真正提交",
    )
    args = parser.parse_args()

    if args.real:
        try:
            PlaywrightAutoOrderBrowserRunner.validate_runtime()
        except AutoOrderBrowserError as exc:
            print(f"真实自动拍单服务启动失败：{exc}")
            raise SystemExit(1) from exc

        server = RealAutoOrderHttpServer(
            host=args.host,
            port=args.port,
            api_key=args.api_key,
            address_slot_label=args.address_slot_label,
            stop_before_submit=args.stop_before_submit,
        )
        server.start()
        print(f"真实自动拍单服务已启动: {server.url()}")
        print(f"API Key: {args.api_key}")
        if args.stop_before_submit:
            print("已开启 stop-before-submit：流程会停在提交前检查点，不会真正提交订单。")
        print("请确保目标京东账号环境已手动登录，且存在标签为“自动拍单”的专用地址。")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            server.stop()
        return

    server = MockAutoOrderHttpServer(
        host=args.host,
        port=args.port,
        api_key=args.api_key,
        processing_delay_seconds=args.processing_delay,
    )
    server.start()
    print(f"模拟自动拍单服务已启动: {server.url()}")
    print(f"API Key: {args.api_key}")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        server.stop()


def main_real() -> None:
    import sys

    argv = sys.argv[1:]
    if "--real" not in argv:
        argv = ["--real", *argv]
    sys.argv = [sys.argv[0], *argv]
    main()


if __name__ == "__main__":
    main()
