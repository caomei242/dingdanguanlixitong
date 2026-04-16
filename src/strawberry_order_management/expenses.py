from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any


_DEFAULT_FIELDS = {
    "expense_date": "",
    "scope_type": "",
    "shop_name": "",
    "order_id": "",
    "platform": "",
    "category": "",
    "amount": "",
    "remark": "",
    "created_at": "",
    "updated_at": "",
}


class ExpenseStore:
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
        now = _now_timestamp()
        row["created_at"] = now
        row["updated_at"] = now
        normalized = self._normalize_row(row)
        rows.insert(0, normalized)
        self._save_rows(rows)
        return normalized

    def get(self, record_id: str) -> dict[str, Any]:
        for row in self._load_rows():
            if row.get("record_id") == record_id:
                return self._normalize_row(row)
        raise KeyError(record_id)

    def update(self, record_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        rows = self._load_rows()
        for index, row in enumerate(rows):
            if row.get("record_id") == record_id:
                merged = dict(row)
                merged.update({key: value for key, value in patch.items() if key != "record_id"})
                merged["updated_at"] = _now_timestamp()
                normalized = self._normalize_row(merged)
                normalized["record_id"] = record_id
                normalized["created_at"] = str(row.get("created_at", "")).strip() or normalized["created_at"]
                rows[index] = normalized
                self._save_rows(rows)
                return normalized
        raise KeyError(record_id)

    def delete(self, record_id: str) -> None:
        rows = self._load_rows()
        kept_rows = [row for row in rows if row.get("record_id") != record_id]
        if len(kept_rows) == len(rows):
            raise KeyError(record_id)
        self._save_rows(kept_rows)

    def list_items(self) -> list[dict[str, Any]]:
        return [self._normalize_row(row) for row in self._load_rows()]

    def _normalize_row(self, row: dict[str, Any]) -> dict[str, Any]:
        normalized = {"record_id": str(row.get("record_id", "")).strip()}
        for key, default in _DEFAULT_FIELDS.items():
            normalized[key] = str(row.get(key, default)).strip()
        return normalized


def default_expense_path() -> Path:
    return Path.home() / ".config" / "strawberry-order-management" / "expenses.json"


def _now_timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
