from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from urllib.parse import urljoin

import requests


AUTO_ORDER_STATUS_PENDING = "待处理"
AUTO_ORDER_STATUS_RUNNING = "执行中"
AUTO_ORDER_STATUS_PARTIAL = "部分成功"
AUTO_ORDER_STATUS_READY_TO_PAY = "已到待付款"
AUTO_ORDER_STATUS_FAILED = "失败"
AUTO_ORDER_STATUS_OPTIONS = (
    AUTO_ORDER_STATUS_PENDING,
    AUTO_ORDER_STATUS_RUNNING,
    AUTO_ORDER_STATUS_PARTIAL,
    AUTO_ORDER_STATUS_READY_TO_PAY,
    AUTO_ORDER_STATUS_FAILED,
)

AUTO_ORDER_ITEM_STATUS_PENDING = "待执行"
AUTO_ORDER_ITEM_STATUS_RUNNING = "执行中"
AUTO_ORDER_ITEM_STATUS_READY_TO_PAY = "待付款"
AUTO_ORDER_ITEM_STATUS_FAILED = "失败"

AUTO_ORDER_TASK_STATUS_QUEUED = "queued"
AUTO_ORDER_TASK_STATUS_RUNNING = "running"
AUTO_ORDER_TASK_STATUS_SUCCEEDED = "succeeded"
AUTO_ORDER_TASK_STATUS_FAILED = "failed"
AUTO_ORDER_TASK_TERMINAL_STATUSES = frozenset(
    {AUTO_ORDER_TASK_STATUS_SUCCEEDED, AUTO_ORDER_TASK_STATUS_FAILED}
)

AUTO_ORDER_RESUME_HINT = "上次任务未续追，请确认后手动重试"
AUTO_ORDER_MISSING_RESULT_MESSAGE = "任务结束但未返回采购位结果"

_AUTO_ORDER_ITEM_KEYS = (
    "jd_status",
    "jd_account_name",
    "jd_order_id",
    "jd_error_message",
    "jd_last_run_at",
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _priority(value: Any, fallback: int = 1) -> int:
    try:
        return max(0, int(str(value).strip()))
    except (TypeError, ValueError):
        return fallback


def _int_value(value: Any, fallback: int) -> int:
    try:
        return max(0, int(str(value).strip()))
    except (TypeError, ValueError):
        return fallback


def now_timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def normalize_jd_account(account: dict[str, Any], fallback_priority: int = 1) -> dict[str, Any]:
    return {
        "name": _text(account.get("name")),
        "environment": _text(account.get("environment") or account.get("path")),
        "enabled": bool(account.get("enabled", True)),
        "address_slot_verified": bool(account.get("address_slot_verified", False)),
        "priority": _priority(account.get("priority"), fallback_priority),
    }


def normalize_jd_accounts(accounts: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(list(accounts or []), start=1):
        if not isinstance(item, dict):
            continue
        normalized_account = normalize_jd_account(item, index)
        if normalized_account["name"]:
            normalized.append(normalized_account)
    return normalized


def enabled_jd_accounts(accounts: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None) -> list[dict[str, Any]]:
    return sorted(
        [item for item in normalize_jd_accounts(accounts) if item["enabled"]],
        key=lambda item: (item["priority"], item["name"]),
    )


def preferred_jd_account(accounts: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None) -> dict[str, Any] | None:
    candidates = enabled_jd_accounts(accounts)
    if not candidates:
        return None
    return candidates[0]


def ready_jd_accounts(accounts: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None) -> list[dict[str, Any]]:
    return sorted(
        [item for item in normalize_jd_accounts(accounts) if item["enabled"] and item["address_slot_verified"]],
        key=lambda item: (item["priority"], item["name"]),
    )


def preferred_ready_jd_account(
    accounts: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None,
) -> dict[str, Any] | None:
    candidates = ready_jd_accounts(accounts)
    if not candidates:
        return None
    return candidates[0]


def normalize_auto_order_bridge_config(payload: dict[str, Any] | None) -> dict[str, Any]:
    payload = dict(payload or {})
    poll_interval_value = (
        payload["auto_order_bridge_poll_interval_seconds"]
        if "auto_order_bridge_poll_interval_seconds" in payload
        else payload.get("poll_interval_seconds")
    )
    timeout_value = (
        payload["auto_order_bridge_timeout_seconds"]
        if "auto_order_bridge_timeout_seconds" in payload
        else payload.get("timeout_seconds")
    )
    return {
        "enabled": bool(payload.get("auto_order_bridge_enabled", payload.get("enabled", False))),
        "base_url": _text(payload.get("auto_order_bridge_base_url") or payload.get("base_url")),
        "api_key": _text(payload.get("auto_order_bridge_api_key") or payload.get("api_key")),
        "submit_path": _text(payload.get("auto_order_bridge_submit_path") or payload.get("submit_path"))
        or "/auto-order/tasks",
        "poll_path_template": _text(
            payload.get("auto_order_bridge_poll_path_template") or payload.get("poll_path_template")
        )
        or "/auto-order/tasks/{task_id}",
        "poll_interval_seconds": _int_value(poll_interval_value, 3),
        "timeout_seconds": _int_value(timeout_value, 1200),
    }


def procurement_item_has_content(item: dict[str, Any] | None) -> bool:
    item = item or {}
    return any(_text(item.get(key)) for key in ("product_name", "cost", "tracking_number", "jd_link"))


def normalize_procurement_item(item: dict[str, Any] | None) -> dict[str, Any]:
    item = dict(item or {})
    product_name = _text(item.get("product_name"))
    quantity = _text(item.get("quantity"))
    cost = _text(item.get("cost"))
    tracking_number = _text(item.get("tracking_number"))
    jd_link = _text(item.get("jd_link"))
    if any((product_name, cost, tracking_number, jd_link)):
        quantity = quantity or "1"
    elif quantity == "1":
        quantity = ""
    normalized: dict[str, Any] = {
        "product_name": product_name,
        "quantity": quantity,
        "cost": cost,
    }
    if tracking_number:
        normalized["tracking_number"] = tracking_number
    if jd_link:
        normalized["jd_link"] = jd_link
    for key in _AUTO_ORDER_ITEM_KEYS:
        value = _text(item.get(key))
        if value:
            normalized[key] = value
    return normalized


def normalize_procurement_items(
    items: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None,
    *,
    size: int = 3,
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    source_items = list(items or [])
    for index in range(size):
        source_item = source_items[index] if index < len(source_items) and isinstance(source_items[index], dict) else {}
        normalized.append(normalize_procurement_item(source_item))
    return normalized


def procurement_item_auto_status(item: dict[str, Any] | None) -> str:
    normalized = normalize_procurement_item(item)
    if not procurement_item_has_content(normalized):
        return ""
    status = _text(normalized.get("jd_status"))
    if status:
        return status
    return AUTO_ORDER_ITEM_STATUS_PENDING


def summarize_auto_order_status(items: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None) -> str:
    statuses = [
        procurement_item_auto_status(item)
        for item in normalize_procurement_items(items)
        if procurement_item_has_content(item)
    ]
    statuses = [status for status in statuses if status]
    if not statuses:
        return ""
    if all(status == AUTO_ORDER_ITEM_STATUS_PENDING for status in statuses):
        return AUTO_ORDER_STATUS_PENDING
    if any(status == AUTO_ORDER_ITEM_STATUS_RUNNING for status in statuses):
        return AUTO_ORDER_STATUS_RUNNING
    ready_count = sum(status == AUTO_ORDER_ITEM_STATUS_READY_TO_PAY for status in statuses)
    if ready_count == len(statuses):
        return AUTO_ORDER_STATUS_READY_TO_PAY
    if ready_count > 0:
        return AUTO_ORDER_STATUS_PARTIAL
    if any(status == AUTO_ORDER_ITEM_STATUS_FAILED for status in statuses):
        return AUTO_ORDER_STATUS_FAILED
    return AUTO_ORDER_STATUS_PENDING


def summarize_auto_order_message(items: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None) -> str:
    parts: list[str] = []
    for index, item in enumerate(normalize_procurement_items(items), start=1):
        if not procurement_item_has_content(item):
            continue
        if _text(item.get("jd_status")) != AUTO_ORDER_ITEM_STATUS_FAILED:
            continue
        error_message = _text(item.get("jd_error_message"))
        if error_message:
            parts.append(f"采购{index}：{error_message}")
    return "；".join(parts)


def row_auto_order_status(row: dict[str, Any]) -> str:
    stored = _text(row.get("auto_order_status"))
    if stored:
        return stored
    order_snapshot = row.get("order_snapshot") or {}
    return summarize_auto_order_status(order_snapshot.get("procurement_items")) or AUTO_ORDER_STATUS_PENDING


def row_has_auto_order_scope(row: dict[str, Any]) -> bool:
    order_snapshot = row.get("order_snapshot") or {}
    return any(procurement_item_has_content(item) for item in normalize_procurement_items(order_snapshot.get("procurement_items")))


def unresolved_procurement_indices(row: dict[str, Any]) -> tuple[int, ...]:
    order_snapshot = row.get("order_snapshot") or {}
    indices: list[int] = []
    for index, item in enumerate(normalize_procurement_items(order_snapshot.get("procurement_items"))):
        if not procurement_item_has_content(item):
            continue
        if procurement_item_auto_status(item) == AUTO_ORDER_ITEM_STATUS_READY_TO_PAY:
            continue
        indices.append(index)
    return tuple(indices)


def row_needs_manual_retry_hint(row: dict[str, Any], active_task_ids: set[str] | None = None) -> bool:
    active_task_ids = active_task_ids or set()
    task_id = _text(row.get("auto_order_task_id"))
    task_status = _text(row.get("auto_order_task_status"))
    if not task_id or task_id in active_task_ids:
        return False
    return task_status in {AUTO_ORDER_TASK_STATUS_QUEUED, AUTO_ORDER_TASK_STATUS_RUNNING}


def row_auto_order_resume_hint(row: dict[str, Any], active_task_ids: set[str] | None = None) -> str:
    if row_needs_manual_retry_hint(row, active_task_ids):
        return AUTO_ORDER_RESUME_HINT
    return ""


def apply_auto_order_result(
    items: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None,
    result: "AutoOrderResult",
) -> list[dict[str, Any]]:
    updated_items = normalize_procurement_items(items)
    by_index = {item_result.procurement_index: item_result for item_result in result.item_results}
    for index, item in enumerate(updated_items):
        item_result = by_index.get(index)
        if item_result is None:
            continue
        item["jd_status"] = _text(item_result.status)
        item["jd_account_name"] = _text(item_result.account_name)
        item["jd_order_id"] = _text(item_result.jd_order_id)
        item["jd_error_message"] = _text(item_result.error_message)
        item["jd_last_run_at"] = _text(item_result.last_run_at)
    return updated_items


def build_failed_auto_order_result(
    items: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None,
    procurement_indices: tuple[int, ...],
    message: str,
    *,
    account_name: str = "",
    last_run_at: str | None = None,
) -> "AutoOrderResult":
    timestamp = _text(last_run_at) or now_timestamp()
    item_results = tuple(
        AutoOrderItemResult(
            procurement_index=index,
            status=AUTO_ORDER_ITEM_STATUS_FAILED,
            account_name=account_name,
            jd_order_id="",
            error_message=message,
            last_run_at=timestamp,
        )
        for index in procurement_indices
    )
    merged_items = apply_auto_order_result(items, AutoOrderResult("", "", timestamp, item_results))
    return AutoOrderResult(
        order_status=summarize_auto_order_status(merged_items) or AUTO_ORDER_STATUS_FAILED,
        message=summarize_auto_order_message(merged_items) or message,
        last_run_at=timestamp,
        item_results=item_results,
    )


def task_ticket_to_snapshot(ticket: "AutoOrderTaskTicket") -> "AutoOrderTaskSnapshot":
    return AutoOrderTaskSnapshot(
        task_id=ticket.task_id,
        task_status=ticket.task_status,
        message=ticket.message,
        submitted_at=ticket.submitted_at,
        updated_at=ticket.updated_at,
        item_results=(),
    )


def task_snapshot_to_result(
    snapshot: "AutoOrderTaskSnapshot",
    procurement_indices: tuple[int, ...],
    current_items: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None,
) -> "AutoOrderResult":
    timestamp = _text(snapshot.updated_at) or now_timestamp()
    item_results = list(snapshot.item_results)
    result_by_index = {item_result.procurement_index: item_result for item_result in item_results}

    if snapshot.task_status in AUTO_ORDER_TASK_TERMINAL_STATUSES:
        for index in procurement_indices:
            if index in result_by_index:
                continue
            if snapshot.task_status == AUTO_ORDER_TASK_STATUS_SUCCEEDED:
                item_results.append(
                    AutoOrderItemResult(
                        procurement_index=index,
                        status=AUTO_ORDER_ITEM_STATUS_FAILED,
                        error_message=AUTO_ORDER_MISSING_RESULT_MESSAGE,
                        last_run_at=timestamp,
                    )
                )
            else:
                item_results.append(
                    AutoOrderItemResult(
                        procurement_index=index,
                        status=AUTO_ORDER_ITEM_STATUS_FAILED,
                        error_message=_text(snapshot.message) or AUTO_ORDER_STATUS_FAILED,
                        last_run_at=timestamp,
                    )
                )
    elif not item_results:
        default_status = (
            AUTO_ORDER_ITEM_STATUS_PENDING
            if snapshot.task_status == AUTO_ORDER_TASK_STATUS_QUEUED
            else AUTO_ORDER_ITEM_STATUS_RUNNING
        )
        item_results.extend(
            AutoOrderItemResult(
                procurement_index=index,
                status=default_status,
                last_run_at=timestamp,
            )
            for index in procurement_indices
        )

    result = AutoOrderResult(
        order_status="",
        message=_text(snapshot.message),
        last_run_at=timestamp,
        item_results=tuple(item_results),
    )
    merged_items = apply_auto_order_result(current_items, result)
    order_status = summarize_auto_order_status(merged_items)
    message = summarize_auto_order_message(merged_items) or _text(snapshot.message)
    if not order_status:
        if snapshot.task_status == AUTO_ORDER_TASK_STATUS_RUNNING:
            order_status = AUTO_ORDER_STATUS_RUNNING
        elif snapshot.task_status == AUTO_ORDER_TASK_STATUS_FAILED:
            order_status = AUTO_ORDER_STATUS_FAILED
        else:
            order_status = AUTO_ORDER_STATUS_PENDING
    return AutoOrderResult(
        order_status=order_status,
        message=message,
        last_run_at=timestamp,
        item_results=tuple(item_results),
    )


@dataclass(frozen=True)
class AutoOrderRequest:
    history_record_id: str
    source: str
    shop_name: str
    recipient_name: str
    phone_number: str
    address: str
    delivery_note: str
    address_output_one: str
    address_output_two: str
    procurement_indices: tuple[int, ...]
    procurement_items: tuple[dict[str, Any], ...]
    jd_accounts: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class AutoOrderItemResult:
    procurement_index: int
    status: str
    account_name: str = ""
    jd_order_id: str = ""
    error_message: str = ""
    last_run_at: str = ""


@dataclass(frozen=True)
class AutoOrderResult:
    order_status: str
    message: str
    last_run_at: str
    item_results: tuple[AutoOrderItemResult, ...]


@dataclass(frozen=True)
class AutoOrderTaskTicket:
    task_id: str
    task_status: str
    message: str = ""
    submitted_at: str = ""
    updated_at: str = ""


@dataclass(frozen=True)
class AutoOrderTaskSnapshot:
    task_id: str
    task_status: str
    message: str = ""
    submitted_at: str = ""
    updated_at: str = ""
    item_results: tuple[AutoOrderItemResult, ...] = ()
    debug_steps: tuple[dict[str, str], ...] = ()
    debug_screenshot_path: str = ""
    debug_updated_at: str = ""
    debug_stage: str = ""


@dataclass(frozen=True)
class AutoOrderCheckResult:
    status: str
    message: str
    account_name: str = ""
    checked_at: str = ""
    checks: tuple[dict[str, str], ...] = ()


class AutoOrderExecutor(Protocol):
    def run(self, request: AutoOrderRequest) -> AutoOrderResult:
        ...


class AutoOrderBridge(Protocol):
    def submit(self, request: AutoOrderRequest) -> AutoOrderTaskTicket:
        ...

    def poll(self, ticket: AutoOrderTaskTicket) -> AutoOrderTaskSnapshot:
        ...

    def check(self, jd_accounts: list[dict[str, Any]] | tuple[dict[str, Any], ...]) -> AutoOrderCheckResult:
        ...


class AutoOrderBridgeError(ValueError):
    pass


class SafeFailAutoOrderExecutor:
    MESSAGE = "当前版本未接入真实京东执行器"

    def run(self, request: AutoOrderRequest) -> AutoOrderResult:
        timestamp = now_timestamp()
        preferred_account = preferred_jd_account(request.jd_accounts)
        item_results = tuple(
            AutoOrderItemResult(
                procurement_index=index,
                status=AUTO_ORDER_ITEM_STATUS_FAILED,
                account_name=_text((preferred_account or {}).get("name")),
                error_message=self.MESSAGE,
                last_run_at=timestamp,
            )
            for index in request.procurement_indices
        )
        merged_items = apply_auto_order_result(request.procurement_items, AutoOrderResult("", "", timestamp, item_results))
        return AutoOrderResult(
            order_status=summarize_auto_order_status(merged_items) or AUTO_ORDER_STATUS_FAILED,
            message=summarize_auto_order_message(merged_items) or self.MESSAGE,
            last_run_at=timestamp,
            item_results=item_results,
        )


class LocalHttpAutoOrderBridge:
    CHECK_PATH = "/auto-order/check"

    def __init__(self, payload: dict[str, Any] | None) -> None:
        self.config = normalize_auto_order_bridge_config(payload)

    def submit(self, request: AutoOrderRequest) -> AutoOrderTaskTicket:
        self._assert_ready()
        try:
            response = requests.post(
                self._url(self.config["submit_path"]),
                json=self._submit_payload(request),
                headers=self._headers(),
                timeout=15,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise AutoOrderBridgeError(f"自动拍单服务请求失败：{exc}") from exc
        data = self._response_payload(response)
        task_id = _text(data.get("task_id"))
        if not task_id:
            raise AutoOrderBridgeError("自动拍单服务返回缺少 task_id")
        return AutoOrderTaskTicket(
            task_id=task_id,
            task_status=_text(data.get("task_status")) or AUTO_ORDER_TASK_STATUS_QUEUED,
            message=_text(data.get("message")),
            submitted_at=_text(data.get("submitted_at")),
            updated_at=_text(data.get("updated_at")),
        )

    def poll(self, ticket: AutoOrderTaskTicket) -> AutoOrderTaskSnapshot:
        self._assert_ready()
        path_template = self.config["poll_path_template"]
        path = path_template.replace("{task_id}", ticket.task_id)
        try:
            response = requests.get(
                self._url(path),
                headers=self._headers(),
                timeout=15,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise AutoOrderBridgeError(f"自动拍单服务轮询失败：{exc}") from exc
        data = self._response_payload(response)
        task_id = _text(data.get("task_id")) or ticket.task_id
        return AutoOrderTaskSnapshot(
            task_id=task_id,
            task_status=_text(data.get("task_status")) or ticket.task_status or AUTO_ORDER_TASK_STATUS_RUNNING,
            message=_text(data.get("message")),
            submitted_at=_text(data.get("submitted_at")) or ticket.submitted_at,
            updated_at=_text(data.get("updated_at")),
            item_results=self._item_results(data.get("item_results")),
            debug_steps=self._debug_steps(data.get("debug_steps")),
            debug_screenshot_path=_text(data.get("debug_screenshot_path")),
            debug_updated_at=_text(data.get("debug_updated_at")),
            debug_stage=_text(data.get("debug_stage")),
        )

    def check(self, jd_accounts: list[dict[str, Any]] | tuple[dict[str, Any], ...]) -> AutoOrderCheckResult:
        self._assert_ready()
        try:
            response = requests.post(
                self._url(self.CHECK_PATH),
                json={
                    "jd_accounts": [
                        {
                            "name": account["name"],
                            "environment": account["environment"],
                            "priority": account["priority"],
                            "address_slot_verified": bool(account.get("address_slot_verified")),
                        }
                        for account in ready_jd_accounts(jd_accounts)
                    ]
                },
                headers=self._headers(),
                timeout=15,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise AutoOrderBridgeError(f"自动拍单服务自检失败：{exc}") from exc
        data = self._response_payload(response)
        return AutoOrderCheckResult(
            status=_text(data.get("status")) or "failed",
            message=_text(data.get("message")),
            account_name=_text(data.get("account_name")),
            checked_at=_text(data.get("checked_at")),
            checks=self._checks(data.get("checks")),
        )

    def _submit_payload(self, request: AutoOrderRequest) -> dict[str, Any]:
        procurement_items = normalize_procurement_items(request.procurement_items)
        enabled_accounts_payload = [
            {
                "name": account["name"],
                "environment": account["environment"],
                "priority": account["priority"],
                "address_slot_verified": bool(account.get("address_slot_verified")),
            }
            for account in ready_jd_accounts(request.jd_accounts)
        ]
        target_items: list[dict[str, Any]] = []
        for index in request.procurement_indices:
            if index < 0 or index >= len(procurement_items):
                continue
            item = procurement_items[index]
            if not procurement_item_has_content(item):
                continue
            target_items.append(
                {
                    "procurement_index": index,
                    "product_name": _text(item.get("product_name")),
                    "quantity": _text(item.get("quantity")) or "1",
                    "jd_link": _text(item.get("jd_link")),
                }
            )
        return {
            "history_record_id": request.history_record_id,
            "source": request.source,
            "shop_name": request.shop_name,
            "recipient_name": request.recipient_name,
            "phone_number": request.phone_number,
            "address": request.address,
            "delivery_note": request.delivery_note,
            "address_output_one": _text(request.address_output_one),
            "address_output_two": _text(request.address_output_two),
            "procurement_items": target_items,
            "jd_accounts": enabled_accounts_payload,
        }

    @staticmethod
    def _item_results(value: Any) -> tuple[AutoOrderItemResult, ...]:
        results: list[AutoOrderItemResult] = []
        for item in list(value or []):
            if not isinstance(item, dict):
                continue
            try:
                procurement_index = int(item.get("procurement_index"))
            except (TypeError, ValueError):
                continue
            results.append(
                AutoOrderItemResult(
                    procurement_index=procurement_index,
                    status=_text(item.get("status")),
                    account_name=_text(item.get("account_name")),
                    jd_order_id=_text(item.get("jd_order_id")),
                    error_message=_text(item.get("error_message")),
                    last_run_at=_text(item.get("last_run_at")),
                )
            )
        return tuple(results)

    @staticmethod
    def _debug_steps(value: Any) -> tuple[dict[str, str], ...]:
        steps: list[dict[str, str]] = []
        for item in list(value or []):
            if not isinstance(item, dict):
                continue
            text = _text(item.get("text"))
            at = _text(item.get("at"))
            if not text and not at:
                continue
            steps.append({"at": at, "text": text})
        return tuple(steps)

    @staticmethod
    def _checks(value: Any) -> tuple[dict[str, str], ...]:
        checks: list[dict[str, str]] = []
        for item in list(value or []):
            if not isinstance(item, dict):
                continue
            checks.append(
                {
                    "label": _text(item.get("label")),
                    "status": _text(item.get("status")),
                    "message": _text(item.get("message")),
                }
            )
        return tuple(checks)

    @staticmethod
    def _response_payload(response) -> dict[str, Any]:
        try:
            payload = response.json()
        except ValueError as exc:
            raise AutoOrderBridgeError("自动拍单服务返回了无效 JSON") from exc
        if not isinstance(payload, dict):
            raise AutoOrderBridgeError("自动拍单服务返回格式不正确")
        data = payload.get("data")
        if isinstance(data, dict):
            return data
        return payload

    def _assert_ready(self) -> None:
        missing = []
        if not self.config["base_url"]:
            missing.append("自动拍单服务 Base URL")
        if not self.config["api_key"]:
            missing.append("自动拍单服务 API Key")
        if missing:
            raise AutoOrderBridgeError(f"请先在设置页填写：{'、'.join(missing)}")

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.config['api_key']}",
            "Content-Type": "application/json",
        }

    def _url(self, path: str) -> str:
        base_url = self.config["base_url"].rstrip("/") + "/"
        normalized_path = _text(path).lstrip("/")
        return urljoin(base_url, normalized_path)
