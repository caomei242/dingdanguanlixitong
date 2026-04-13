from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any


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

        normalized["order_snapshot"] = order_snapshot
        normalized["address_snapshot"] = address_snapshot
        normalized["sync_source"] = str(normalized.get("sync_source", "")).strip() or "-"
        return normalized


def default_history_path() -> Path:
    return Path.home() / ".config" / "strawberry-order-management" / "history.json"
