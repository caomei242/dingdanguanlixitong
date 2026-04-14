# Intake Layout And History Workbench Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rework the intake screen into a clearer operator layout and turn history into a full workbench with detailed records, edit/delete actions, and re-submit to Feishu.

**Architecture:** Keep the current PySide6 desktop app structure, but split the work into three safe layers: intake UI re-layout, history data model/storage upgrade, and history workbench interactions. Preserve backwards compatibility with existing config/history JSON by reading old rows defensively and normalizing them into richer in-memory structures for the new UI.

**Tech Stack:** Python 3, PySide6, existing JSON `ConfigStore`/`HistoryStore`, pytest, pytest-qt

---

## File Map

- Modify: `src/strawberry_order_management/history.py`
  - Expand history store CRUD beyond append/list, support update/delete/get by id while preserving JSON compatibility.
- Modify: `src/strawberry_order_management/ui/pages/history_page.py`
  - Replace simple list page with list-plus-detail workbench UI and signals for edit/delete/resubmit.
- Modify: `src/strawberry_order_management/ui/widgets/order_card_widget.py`
  - Add a compact layout mode for intake and a way to load/save history snapshot data consistently.
- Modify: `src/strawberry_order_management/ui/pages/intake_page.py`
  - Re-layout intake sections into clearer cards/grid without changing the core OCR/address flow.
- Modify: `src/strawberry_order_management/ui/main_window.py`
  - Persist richer history snapshots, wire history actions, and reuse Feishu submission logic for history re-submit.
- Modify: `src/strawberry_order_management/ui/theme.py`
  - Style the new intake cards, compact fields, history list items, detail panel, and action buttons.
- Test: `tests/ui/test_history_page.py`
  - New tests for workbench rendering, selection, edit/delete/resubmit affordances.
- Modify: `tests/ui/test_main_window.py`
  - Cover richer history persistence and history actions through the main window.
- Modify: `tests/ui/test_intake_page.py`
  - Assert the new intake layout still submits and stores complete data.
- Modify: `tests/test_history_store.py`
  - New store-level tests for CRUD and compatibility normalization.

### Task 1: Upgrade History Storage To Full Snapshots

**Files:**
- Modify: `src/strawberry_order_management/history.py`
- Create: `tests/test_history_store.py`

- [ ] **Step 1: Write the failing store tests**

```python
from strawberry_order_management.history import HistoryStore


def test_history_store_appends_snapshot_with_generated_record_id(tmp_path):
    store = HistoryStore(tmp_path / "history.json")

    row = store.append(
        {
            "shop_name": "乐宝零食店",
            "sync_source": "确认写入飞书",
            "status": "已写入飞书",
            "order_snapshot": {
                "order_id": "69525544900545379782",
                "recipient_name": "田宝山",
                "income_amount": "142.00",
            },
            "address_snapshot": {
                "output_one": "田宝山15784081541山东省德州市齐河县晏城街道玫瑰园4号楼",
                "output_two": "请电话送货上门谢谢【5842】",
            },
            "created_at": "2026-04-13T10:24:18",
        }
    )

    assert row["record_id"]
    assert store.list_items()[0]["order_snapshot"]["recipient_name"] == "田宝山"


def test_history_store_can_update_and_delete_rows(tmp_path):
    store = HistoryStore(tmp_path / "history.json")
    row = store.append({"shop_name": "乐宝零食店", "status": "仅存历史"})

    store.update(row["record_id"], {"status": "写入失败", "message": "FieldNameNotFound"})
    updated = store.get(row["record_id"])
    assert updated["status"] == "写入失败"
    assert updated["message"] == "FieldNameNotFound"

    store.delete(row["record_id"])
    assert store.list_items() == []


def test_history_store_normalizes_legacy_rows(tmp_path):
    path = tmp_path / "history.json"
    path.write_text(
        '[{"shop_name":"草莓店","order_id":"1","recipient_name":"何女士","status":"已写入飞书"}]',
        encoding="utf-8",
    )
    store = HistoryStore(path)

    row = store.list_items()[0]

    assert row["order_snapshot"]["order_id"] == "1"
    assert row["order_snapshot"]["recipient_name"] == "何女士"
    assert row["sync_source"] == "-"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_history_store.py -q`
Expected: FAIL because `HistoryStore` does not yet provide `get`, `update`, `delete`, or legacy normalization.

- [ ] **Step 3: Write minimal store implementation**

```python
class HistoryStore:
    def get(self, record_id: str) -> dict[str, Any]:
        for row in self.list_items():
            if row.get("record_id") == record_id:
                return row
        raise KeyError(record_id)

    def update(self, record_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        rows = self._load_rows()
        for row in rows:
            if row.get("record_id") == record_id:
                row.update(patch)
                self._save_rows(rows)
                return row
        raise KeyError(record_id)

    def delete(self, record_id: str) -> None:
        rows = [row for row in self._load_rows() if row.get("record_id") != record_id]
        self._save_rows(rows)

    def list_items(self) -> list[dict[str, Any]]:
        return [self._normalize_row(row) for row in self._load_rows()]

    def _normalize_row(self, row: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(row)
        order_snapshot = normalized.get("order_snapshot") or {}
        if not order_snapshot:
            order_snapshot = {
                "order_id": normalized.get("order_id", ""),
                "recipient_name": normalized.get("recipient_name", ""),
                "product_name": normalized.get("product_name", ""),
            }
        normalized["order_snapshot"] = order_snapshot
        normalized["address_snapshot"] = normalized.get("address_snapshot") or {
            "output_one": "",
            "output_two": "",
        }
        normalized["sync_source"] = str(normalized.get("sync_source", "")).strip() or "-"
        return normalized
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_history_store.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/strawberry_order_management/history.py tests/test_history_store.py
git commit -m "feat: expand history snapshots and store operations"
```

### Task 2: Rebuild History Page As A Workbench

**Files:**
- Modify: `src/strawberry_order_management/ui/pages/history_page.py`
- Create: `tests/ui/test_history_page.py`
- Modify: `src/strawberry_order_management/ui/theme.py`

- [ ] **Step 1: Write the failing history page tests**

```python
from strawberry_order_management.ui.pages.history_page import HistoryPage


def test_history_page_renders_list_and_detail_panel(qtbot):
    page = HistoryPage()
    qtbot.addWidget(page)

    page.load_rows(
        [
            {
                "record_id": "rec_1",
                "shop_name": "乐宝零食店",
                "sync_source": "确认写入飞书",
                "status": "已写入飞书",
                "created_at": "2026-04-13T10:24:18",
                "order_snapshot": {
                    "order_id": "69525544900545379782",
                    "recipient_name": "田宝山",
                    "phone_number": "15784081541",
                    "address": "山东省德州市齐河县晏城街道玫瑰园4号楼",
                },
                "address_snapshot": {"output_one": "结果一", "output_two": "结果二"},
            }
        ]
    )

    assert page.list_widget.count() == 1
    assert "乐宝零食店" in page.detail_title_label.text()
    assert "结果一" in page.detail_output_one.toPlainText()


def test_history_page_emits_edit_delete_and_resubmit_actions(qtbot):
    page = HistoryPage()
    qtbot.addWidget(page)
    page.load_rows([...])

    edited = []
    deleted = []
    resent = []
    page.edit_requested.connect(edited.append)
    page.delete_requested.connect(deleted.append)
    page.resubmit_requested.connect(resent.append)

    page.edit_button.click()
    page.delete_button.click()
    page.resubmit_button.click()

    assert edited == ["rec_1"]
    assert deleted == ["rec_1"]
    assert resent == ["rec_1"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen python3 -m pytest tests/ui/test_history_page.py -q`
Expected: FAIL because `HistoryPage` is still a simple `QListWidget` summary.

- [ ] **Step 3: Write minimal history workbench implementation**

```python
class HistoryPage(QWidget):
    edit_requested = Signal(str)
    delete_requested = Signal(str)
    resubmit_requested = Signal(str)

    def __init__(self) -> None:
        self.list_widget = QListWidget()
        self.detail_title_label = QLabel("未选择记录")
        self.detail_output_one = QTextEdit()
        self.detail_output_two = QTextEdit()
        self.edit_button = QPushButton("编辑记录")
        self.delete_button = QPushButton("删除记录")
        self.resubmit_button = QPushButton("重新写入飞书")
        self._rows = []
        self._current_record_id = None
        ...

    def load_rows(self, rows: list[dict]) -> None:
        self._rows = rows
        self.list_widget.clear()
        for row in rows:
            item = QListWidgetItem(self._summary_text(row))
            item.setData(Qt.ItemDataRole.UserRole, row["record_id"])
            self.list_widget.addItem(item)
        if rows:
            self.list_widget.setCurrentRow(0)

    def _load_detail(self, record_id: str) -> None:
        row = self._find_row(record_id)
        self._current_record_id = record_id
        self.detail_title_label.setText(
            f'{row["shop_name"]} · {row["order_snapshot"].get("recipient_name", "-")}'
        )
        self.detail_output_one.setPlainText(row["address_snapshot"].get("output_one", ""))
        self.detail_output_two.setPlainText(row["address_snapshot"].get("output_two", ""))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `QT_QPA_PLATFORM=offscreen python3 -m pytest tests/ui/test_history_page.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/strawberry_order_management/ui/pages/history_page.py src/strawberry_order_management/ui/theme.py tests/ui/test_history_page.py
git commit -m "feat: rebuild history page as workbench"
```

### Task 3: Re-layout Intake Page Without Breaking Submission Flow

**Files:**
- Modify: `src/strawberry_order_management/ui/widgets/order_card_widget.py`
- Modify: `src/strawberry_order_management/ui/pages/intake_page.py`
- Modify: `src/strawberry_order_management/ui/theme.py`
- Modify: `tests/ui/test_intake_page.py`

- [ ] **Step 1: Write the failing intake layout tests**

```python
from PySide6.QtWidgets import QLabel
from strawberry_order_management.ui.pages.intake_page import IntakePage


def test_intake_page_groups_order_fields_into_compact_sections(qtbot):
    page = IntakePage(use_background_thread=False)
    qtbot.addWidget(page)

    assert page.findChild(QLabel, "ProcurementSectionTitle").text() == "采购信息"
    assert page.order_card_widget.layout().rowCount() < 20


def test_intake_page_keeps_existing_submit_behavior_after_layout_change(qtbot):
    submitted = []
    page = IntakePage(on_submit=submitted.append, use_background_thread=False)
    qtbot.addWidget(page)
    page.shop_selector.addItems(["草莓店"])
    page.shop_selector.setCurrentText("草莓店")
    page.show_order(...)

    page.submit_button.click()

    assert submitted[0]["shop_name"] == "草莓店"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen python3 -m pytest tests/ui/test_intake_page.py -q`
Expected: FAIL because the current order form is still a long plain form without grouped sections.

- [ ] **Step 3: Write minimal intake re-layout**

```python
class OrderCardWidget(QWidget):
    def __init__(self) -> None:
        header_grid = QGridLayout()
        detail_stack = QVBoxLayout()
        procurement_card = QFrame()
        procurement_title = QLabel("采购信息")
        procurement_title.setObjectName("ProcurementSectionTitle")
        ...
```

Use the existing widgets and signals rather than replacing the OCR/submit logic. Only move them into a more compact composition.

- [ ] **Step 4: Run test to verify it passes**

Run: `QT_QPA_PLATFORM=offscreen python3 -m pytest tests/ui/test_intake_page.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/strawberry_order_management/ui/widgets/order_card_widget.py src/strawberry_order_management/ui/pages/intake_page.py src/strawberry_order_management/ui/theme.py tests/ui/test_intake_page.py
git commit -m "feat: compact intake layout for order entry"
```

### Task 4: Persist Rich History Snapshots From Intake And Feishu Sync

**Files:**
- Modify: `src/strawberry_order_management/ui/main_window.py`
- Modify: `tests/ui/test_main_window.py`

- [ ] **Step 1: Write the failing main window tests**

```python
def test_main_window_saves_rich_history_snapshot_for_history_only(qtbot, tmp_path):
    ...
    window.intake_page.show_order(_sample_order())
    window.intake_page.shop_selector.setCurrentText("草莓店")
    window.intake_page.save_history_button.click()

    row = history_store.list_items()[0]
    assert row["sync_source"] == "仅存历史"
    assert row["order_snapshot"]["recipient_name"] == "何女士"
    assert row["address_snapshot"]["output_two"] == "请电话送货上门谢谢【3612】"


def test_main_window_updates_same_history_record_after_feishu_submit(qtbot, tmp_path, monkeypatch):
    ...
    window.intake_page.submit_button.click()
    row = history_store.list_items()[0]
    assert row["sync_source"] == "确认写入飞书"
    assert row["status"] == "已写入飞书"
    assert row["feishu_result"] == "rec_123"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen python3 -m pytest tests/ui/test_main_window.py -q`
Expected: FAIL because history rows are still stored as flat summaries.

- [ ] **Step 3: Write minimal snapshot persistence**

```python
def _build_history_snapshot(self, payload: dict, sync_source: str, status: str, message: str = "") -> dict:
    order = payload["order"]
    return {
        "shop_name": payload.get("shop_name") or "-",
        "sync_source": sync_source,
        "status": status,
        "message": message,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "order_snapshot": {
            "order_id": order.order_id,
            "placed_at": order.placed_at,
            "order_status": order.order_status,
            "product_name": order.product_name,
            "income_amount": order.income_amount,
            "recipient_name": order.recipient_name,
            "phone_number": order.phone_number,
            "code": order.code,
            "address": order.address,
            "delivery_note": order.delivery_note,
            "procurement_items": [...],
        },
        "address_snapshot": {
            "output_one": self.intake_page.address_widget.output_one.toPlainText().strip(),
            "output_two": self.intake_page.address_widget.output_two.toPlainText().strip(),
        },
    }
```

Persist the history row once, then update that same row after Feishu success/failure instead of appending duplicates.

- [ ] **Step 4: Run test to verify it passes**

Run: `QT_QPA_PLATFORM=offscreen python3 -m pytest tests/ui/test_main_window.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/strawberry_order_management/ui/main_window.py tests/ui/test_main_window.py
git commit -m "feat: persist detailed history snapshots"
```

### Task 5: Add Edit/Delete/Re-submit From History

**Files:**
- Modify: `src/strawberry_order_management/ui/pages/history_page.py`
- Modify: `src/strawberry_order_management/ui/main_window.py`
- Modify: `tests/ui/test_history_page.py`
- Modify: `tests/ui/test_main_window.py`

- [ ] **Step 1: Write the failing action tests**

```python
def test_main_window_deletes_history_record_from_workbench(qtbot, tmp_path):
    ...
    window.history_page.load_rows(history_store.list_items())
    window.history_page.delete_button.click()
    assert history_store.list_items() == []


def test_main_window_resubmits_selected_history_record_to_feishu(qtbot, tmp_path, monkeypatch):
    ...
    window.history_page.load_rows(history_store.list_items())
    window.history_page.resubmit_button.click()
    qtbot.waitUntil(lambda: history_store.list_items()[0]["status"] == "已写入飞书")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen python3 -m pytest tests/ui/test_history_page.py tests/ui/test_main_window.py -q`
Expected: FAIL because the history actions are not wired to the store or Feishu submission flow.

- [ ] **Step 3: Write minimal action wiring**

```python
class MainWindow(QMainWindow):
    def __init__(...):
        ...
        self.history_page.delete_requested.connect(self._handle_history_delete)
        self.history_page.resubmit_requested.connect(self._handle_history_resubmit)

    def _handle_history_delete(self, record_id: str) -> None:
        self._history_store.delete(record_id)
        self.history_page.load_rows(self._history_store.list_items())

    def _handle_history_resubmit(self, record_id: str) -> None:
        row = self._history_store.get(record_id)
        payload = self._history_row_to_submission_payload(row)
        task = self._build_feishu_submission_task(payload)
        task["history_record_id"] = record_id
        self._start_submit_job(task)
```

Update success/failure handlers so that when `history_record_id` exists, they update that row instead of appending a new one.

- [ ] **Step 4: Run test to verify it passes**

Run: `QT_QPA_PLATFORM=offscreen python3 -m pytest tests/ui/test_history_page.py tests/ui/test_main_window.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/strawberry_order_management/ui/pages/history_page.py src/strawberry_order_management/ui/main_window.py tests/ui/test_history_page.py tests/ui/test_main_window.py
git commit -m "feat: add history delete and resubmit actions"
```

### Task 6: Add History Editing For Local Corrections

**Files:**
- Modify: `src/strawberry_order_management/ui/pages/history_page.py`
- Modify: `src/strawberry_order_management/ui/main_window.py`
- Modify: `tests/ui/test_history_page.py`
- Modify: `tests/ui/test_main_window.py`

- [ ] **Step 1: Write the failing edit tests**

```python
def test_history_page_can_toggle_detail_fields_into_edit_mode(qtbot):
    page = HistoryPage()
    qtbot.addWidget(page)
    page.load_rows([...])

    page.edit_button.click()

    assert page.detail_recipient_edit.isReadOnly() is False
    assert page.save_edit_button.isVisible() is True


def test_main_window_persists_history_edits(qtbot, tmp_path):
    ...
    window.history_page.edit_button.click()
    window.history_page.detail_recipient_edit.setText("新名字")
    window.history_page.save_edit_button.click()

    assert history_store.list_items()[0]["order_snapshot"]["recipient_name"] == "新名字"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen python3 -m pytest tests/ui/test_history_page.py tests/ui/test_main_window.py -q`
Expected: FAIL because detail fields are currently display-only.

- [ ] **Step 3: Write minimal editable detail implementation**

```python
class HistoryPage(QWidget):
    save_edit_requested = Signal(str, object)

    def _set_edit_mode(self, enabled: bool) -> None:
        self.detail_recipient_edit.setReadOnly(not enabled)
        self.detail_phone_edit.setReadOnly(not enabled)
        self.detail_address_edit.setReadOnly(not enabled)
        ...

    def _emit_save_edit(self) -> None:
        self.save_edit_requested.emit(
            self._current_record_id,
            {
                "order_snapshot": {
                    "recipient_name": self.detail_recipient_edit.text().strip(),
                    "phone_number": self.detail_phone_edit.text().strip(),
                    "address": self.detail_address_edit.toPlainText().strip(),
                }
            },
        )
```

Wire the signal in `MainWindow` to `HistoryStore.update(...)`, then reload the page selection after save.

- [ ] **Step 4: Run test to verify it passes**

Run: `QT_QPA_PLATFORM=offscreen python3 -m pytest tests/ui/test_history_page.py tests/ui/test_main_window.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/strawberry_order_management/ui/pages/history_page.py src/strawberry_order_management/ui/main_window.py tests/ui/test_history_page.py tests/ui/test_main_window.py
git commit -m "feat: support editing history records"
```

### Task 7: Final Regression

**Files:**
- Modify: none unless regression fixes are required
- Test: `tests/test_history_store.py`
- Test: `tests/ui/test_history_page.py`
- Test: `tests/ui/test_intake_page.py`
- Test: `tests/ui/test_main_window.py`
- Test: `tests -q`

- [ ] **Step 1: Run focused history and intake regression**

Run:

```bash
cd /Users/gd/Desktop/d/.worktrees/strawberry-order-management-v1
QT_QPA_PLATFORM=offscreen python3 -m pytest \
  tests/test_history_store.py \
  tests/ui/test_history_page.py \
  tests/ui/test_intake_page.py \
  tests/ui/test_main_window.py -q
```

Expected: PASS

- [ ] **Step 2: Run full suite**

Run:

```bash
cd /Users/gd/Desktop/d/.worktrees/strawberry-order-management-v1
QT_QPA_PLATFORM=offscreen python3 -m pytest tests -q
```

Expected: PASS

- [ ] **Step 3: Run smoke test**

Run:

```bash
cd /Users/gd/Desktop/d/.worktrees/strawberry-order-management-v1
PYTHONPATH=src QT_QPA_PLATFORM=offscreen python3 - <<'PY'
from PySide6.QtWidgets import QApplication
from strawberry_order_management.ui.main_window import MainWindow

app = QApplication([])
window = MainWindow()
print("smoke ok", window.nav.count(), window.stack.count())
window.close()
app.quit()
PY
```

Expected: output includes `smoke ok`

- [ ] **Step 4: Commit final integration**

```bash
git add -A
git commit -m "feat: upgrade intake layout and history workbench"
```

---

## Self-Review

- Spec coverage:
  - Intake layout refinement: covered by Task 3
  - Rich history snapshots for both save modes: covered by Task 1 and Task 4
  - History detail view: covered by Task 2
  - Delete and re-submit: covered by Task 5
  - Edit support: covered by Task 6
- Placeholder scan:
  - No `TODO`/`TBD` markers remain
  - Each task includes concrete files, commands, and minimal code direction
- Type consistency:
  - `order_snapshot`, `address_snapshot`, `sync_source`, `feishu_result` are used consistently across store, UI, and main-window tasks
