from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from strawberry_order_management.extractors.address import clean_virtual_number_artifacts
from strawberry_order_management.services.auto_order import normalize_procurement_items


_ORDER_SNAPSHOT_KEYS = {
    "order_id",
    "placed_at",
    "order_status",
    "product_name",
    "quantity",
    "order_amount",
    "income_amount",
    "recipient_name",
    "phone_number",
    "code",
    "address",
    "delivery_note",
    "procurement_items",
}


def _normalize_auto_order_debug(value: Any) -> dict[str, Any]:
    payload = dict(value or {}) if isinstance(value, dict) else {}
    steps: list[dict[str, str]] = []
    for item in list(payload.get("steps") or []):
        if not isinstance(item, dict):
            continue
        steps.append(
            {
                "at": str(item.get("at", "")).strip(),
                "text": str(item.get("text", "")).strip(),
            }
        )
    return {
        "steps": steps,
        "screenshot_path": str(payload.get("screenshot_path", "")).strip(),
        "updated_at": str(payload.get("updated_at", "")).strip(),
        "stage": str(payload.get("stage", "")).strip(),
        "summary": str(payload.get("summary", "")).strip(),
    }


class HistoryStore:
    def __init__(self, path: Path):
        self.path = path

    def _load_rows(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        try:
            rows = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
        return rows if isinstance(rows, list) else []

    def _save_rows(self, rows: list[dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(rows, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def append(self, payload: dict[str, Any]) -> dict[str, Any]:
        rows = self._load_rows()
        row = {**payload}
        row.pop("record_id", None)
        row["record_id"] = str(uuid.uuid4())
        rows.insert(0, row)
        self._save_rows(rows)
        return row

    def get(self, record_id: str) -> dict[str, Any]:
        for row in self._load_rows():
            if row.get("record_id") == record_id:
                return self._normalize_row(row)
        raise KeyError(record_id)

    def update(self, record_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        rows = self._load_rows()
        for row in rows:
            if row.get("record_id") == record_id:
                patch_without_record_id = {key: value for key, value in patch.items() if key != "record_id"}
                row.update(patch_without_record_id)
                self._save_rows(rows)
                return self._normalize_row(row)
        raise KeyError(record_id)

    def delete(self, record_id: str) -> None:
        rows = self._load_rows()
        kept_rows = [row for row in rows if row.get("record_id") != record_id]
        if len(kept_rows) == len(rows):
            raise KeyError(record_id)
        self._save_rows(kept_rows)

    def update_status(self, record_id: str, status: str) -> None:
        self.update(record_id, {"status": status})

    def list_items(self) -> list[dict[str, Any]]:
        return [self._normalize_row(row) for row in self._load_rows()]

    def _normalize_row(self, row: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(row)
        order_snapshot = normalized.get("order_snapshot")
        if not isinstance(order_snapshot, dict):
            order_snapshot = {
                key: value
                for key, value in normalized.items()
                if key in _ORDER_SNAPSHOT_KEYS and value is not None
            }
        else:
            order_snapshot = dict(order_snapshot)
        order_snapshot["procurement_items"] = normalize_procurement_items(order_snapshot.get("procurement_items"))
        order_snapshot["address"] = clean_virtual_number_artifacts(order_snapshot.get("address", ""))

        address_snapshot = normalized.get("address_snapshot")
        if not isinstance(address_snapshot, dict):
            address_snapshot = {
                key: value
                for key, value in normalized.items()
                if key in {"output_one", "output_two", "output_three", "address"}
            }
        else:
            address_snapshot = dict(address_snapshot)
        address_snapshot.setdefault("output_one", "")
        address_snapshot.setdefault("output_two", "")
        address_snapshot["output_one"] = clean_virtual_number_artifacts(address_snapshot.get("output_one", ""))

        normalized["order_snapshot"] = order_snapshot
        normalized["address_snapshot"] = address_snapshot
        normalized["sync_source"] = str(normalized.get("sync_source", "")).strip() or "-"
        normalized["auto_order_status"] = str(normalized.get("auto_order_status", "")).strip()
        normalized["auto_order_message"] = str(normalized.get("auto_order_message", "")).strip()
        normalized["auto_order_last_run_at"] = str(normalized.get("auto_order_last_run_at", "")).strip()
        normalized["auto_order_task_id"] = str(normalized.get("auto_order_task_id", "")).strip()
        normalized["auto_order_task_status"] = str(normalized.get("auto_order_task_status", "")).strip()
        normalized["auto_order_task_submitted_at"] = str(
            normalized.get("auto_order_task_submitted_at", "")
        ).strip()
        normalized["auto_order_task_last_polled_at"] = str(
            normalized.get("auto_order_task_last_polled_at", "")
        ).strip()
        normalized["auto_order_debug"] = _normalize_auto_order_debug(normalized.get("auto_order_debug"))
        feishu_record_id = str(normalized.get("feishu_record_id", "")).strip()
        if not feishu_record_id:
            feishu_result = normalized.get("feishu_result")
            if isinstance(feishu_result, dict):
                data = feishu_result.get("data")
                if isinstance(data, dict):
                    feishu_record_id = str(data.get("record_id", "")).strip()
                    if not feishu_record_id:
                        record = data.get("record")
                        if isinstance(record, dict):
                            feishu_record_id = (
                                str(record.get("record_id", "")).strip()
                                or str(record.get("id", "")).strip()
                            )
        if feishu_record_id:
            normalized["feishu_record_id"] = feishu_record_id
        return normalized


def default_history_path() -> Path:
    return Path.home() / ".config" / "strawberry-order-management" / "history.json"
