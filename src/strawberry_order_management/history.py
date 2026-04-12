from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any


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
        row = {**payload, "record_id": str(uuid.uuid4())}
        rows.insert(0, row)
        self._save_rows(rows)
        return row

    def update_status(self, record_id: str, status: str) -> None:
        rows = self._load_rows()
        for row in rows:
            if row.get("record_id") == record_id:
                row["status"] = status
                self._save_rows(rows)
                return
        raise KeyError(record_id)

    def list_items(self) -> list[dict[str, Any]]:
        return self._load_rows()
