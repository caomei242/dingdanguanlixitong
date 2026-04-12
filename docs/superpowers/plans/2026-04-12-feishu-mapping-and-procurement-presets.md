# Feishu Mapping And Procurement Presets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add per-shop Feishu field mapping plus a shared product preset library and three procurement slots in intake so the user can control what gets written to Feishu and quickly fill cost data.

**Architecture:** Keep OCR/order parsing unchanged, then extend the editable order payload with procurement slots and per-shop field mappings before Feishu submission. Store shared product presets globally in settings, store field mappings per shop, and route final Feishu payload generation through a mapping layer so required/optional columns are configurable without changing core parsing.

**Tech Stack:** Python, PySide6, pytest, pytest-qt, existing JSON config store, existing Feishu service layer.

---

## File Map

- Modify: `src/strawberry_order_management/models.py`
  Add dataclasses for procurement slots and optional mapping-friendly shop config.
- Modify: `src/strawberry_order_management/ui/widgets/order_card_widget.py`
  Add three procurement rows with product selector, quantity, and cost fields.
- Modify: `src/strawberry_order_management/ui/pages/intake_page.py`
  Wire shared product presets into the order card and include procurement data in submit/history payloads.
- Modify: `src/strawberry_order_management/ui/pages/settings_page.py`
  Add global product library UI and per-shop field mapping UI.
- Modify: `src/strawberry_order_management/ui/main_window.py`
  Sync shared product presets into intake and use field mapping when submitting to Feishu.
- Modify: `src/strawberry_order_management/services/pipeline.py`
  Replace fixed Feishu payload keys with a mapping-aware builder that can omit unchecked fields and drop `价格` by default.
- Modify: `src/strawberry_order_management/services/feishu_client.py`
  Improve field-name errors to mention likely mismatched mapping keys where possible.
- Modify: `tests/ui/test_settings_page.py`
  Cover product preset storage, field mapping storage, and mapping UI behavior.
- Modify: `tests/ui/test_intake_page.py`
  Cover procurement slot editing, default quantity, and preset autofill.
- Modify: `tests/ui/test_main_window.py`
  Cover mapped Feishu payload output and preset propagation from settings to intake.
- Modify: `tests/test_pipeline.py`
  Cover mapping-aware payload generation and optional field omission.

## Task 1: Add Data Models For Procurement Slots

**Files:**
- Modify: `src/strawberry_order_management/models.py`
- Test: `tests/test_pipeline.py`

- [ ] **Step 1: Write the failing test**

```python
def test_build_feishu_payload_omits_unmapped_fields_and_includes_procurement_slots():
    order = ParsedOrder(
        order_id="1",
        placed_at="2026-04-11 20:57:15",
        order_status="待发货",
        product_name="原始商品",
        quantity="1",
        order_amount="355.00",
        income_amount="142.00",
        recipient_name="田宝山",
        phone_number="15784081541",
        code="5842",
        address="山东省德州市齐河县晏城街道玫瑰园4号楼(西北门超市)",
        delivery_note="请电话送货上门谢谢【5842】",
        procurement_items=[
            ProcurementItem(product_name="矿泉水", quantity="2", cost="18.50"),
            ProcurementItem(product_name="气泡水", quantity="1", cost="9.00"),
            ProcurementItem(product_name="", quantity="1", cost=""),
        ],
    )

    mapping = {
        "备注": "备注",
        "收入": "收入",
        "采购商品1": "采购商品1",
        "采购数量1": "采购数量1",
        "采购成本1": "采购成本1",
        "采购商品2": "采购商品2",
        "采购数量2": "采购数量2",
        "采购成本2": "采购成本2",
    }

    payload = build_feishu_payload(order, mapping)

    assert payload == {
        "备注": "请电话送货上门谢谢【5842】",
        "收入": "142.00",
        "采购商品1": "矿泉水",
        "采购数量1": "2",
        "采购成本1": "18.50",
        "采购商品2": "气泡水",
        "采购数量2": "1",
        "采购成本2": "9.00",
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_pipeline.py::test_build_feishu_payload_omits_unmapped_fields_and_includes_procurement_slots -q`
Expected: FAIL because `ProcurementItem` and mapping-aware `build_feishu_payload` do not exist yet.

- [ ] **Step 3: Write minimal implementation**

```python
@dataclass(frozen=True)
class ProcurementItem:
    product_name: str
    quantity: str
    cost: str


@dataclass(frozen=True)
class ParsedOrder:
    ...
    procurement_items: tuple[ProcurementItem, ProcurementItem, ProcurementItem] = (
        ProcurementItem("", "1", ""),
        ProcurementItem("", "1", ""),
        ProcurementItem("", "1", ""),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_pipeline.py::test_build_feishu_payload_omits_unmapped_fields_and_includes_procurement_slots -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/strawberry_order_management/models.py tests/test_pipeline.py
git commit -m "feat: add procurement item model"
```

## Task 2: Make Feishu Payload Builder Mapping-Aware

**Files:**
- Modify: `src/strawberry_order_management/services/pipeline.py`
- Test: `tests/test_pipeline.py`

- [ ] **Step 1: Write the failing test**

```python
def test_build_feishu_payload_uses_mapping_and_skips_blank_targets():
    order = ParsedOrder(
        order_id="1",
        placed_at="2026-04-11 20:57:15",
        order_status="待发货",
        product_name="商品",
        quantity="1",
        order_amount="355.00",
        income_amount="142.00",
        recipient_name="田宝山",
        phone_number="15784081541",
        code="5842",
        address="山东省德州市齐河县晏城街道玫瑰园4号楼(西北门超市)",
        delivery_note="请电话送货上门谢谢【5842】",
    )

    payload = build_feishu_payload(
        order,
        {
            "备注": "备注列",
            "订单日期": "日期列",
            "价格": "",
            "收入": "收入列",
        },
    )

    assert payload == {
        "备注列": "请电话送货上门谢谢【5842】",
        "日期列": "2026/04/11",
        "收入列": "142.00",
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_pipeline.py::test_build_feishu_payload_uses_mapping_and_skips_blank_targets -q`
Expected: FAIL because builder still emits fixed field names and includes `价格`.

- [ ] **Step 3: Write minimal implementation**

```python
DEFAULT_FEISHU_FIELD_MAPPING = {
    "备注": "备注",
    "订单日期": "订单日期",
    "下单时间": "下单时间",
    "订单状态": "订单状态",
    "收入": "收入",
    "发货地址": "发货地址",
    "价格": "",
    "采购商品1": "",
    "采购数量1": "",
    "采购成本1": "",
    "采购商品2": "",
    "采购数量2": "",
    "采购成本2": "",
    "采购商品3": "",
    "采购数量3": "",
    "采购成本3": "",
}
```

- [ ] **Step 4: Run focused tests**

Run: `python3 -m pytest tests/test_pipeline.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/strawberry_order_management/services/pipeline.py tests/test_pipeline.py
git commit -m "feat: support configurable feishu field mapping"
```

## Task 3: Add Shared Product Library In Settings

**Files:**
- Modify: `src/strawberry_order_management/ui/pages/settings_page.py`
- Test: `tests/ui/test_settings_page.py`

- [ ] **Step 1: Write the failing test**

```python
def test_settings_page_collects_shared_product_presets(qtbot):
    page = SettingsPage()
    qtbot.addWidget(page)

    page.product_name_edit.setText("澳洲婴儿水")
    page.product_cost_edit.setText("18.50")
    page.save_product_button.click()

    payload = page.to_payload()

    assert payload["product_presets"] == [
        {"name": "澳洲婴儿水", "default_cost": "18.50"}
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen python3 -m pytest tests/ui/test_settings_page.py::test_settings_page_collects_shared_product_presets -q`
Expected: FAIL because product preset UI and payload fields do not exist.

- [ ] **Step 3: Write minimal implementation**

```python
self.product_selector = QComboBox()
self.product_name_edit = QLineEdit()
self.product_cost_edit = QLineEdit()
self.add_product_button = QPushButton("新增商品")
self.save_product_button = QPushButton("保存商品")
self.remove_product_button = QPushButton("删除商品")
```

- [ ] **Step 4: Run settings page tests**

Run: `QT_QPA_PLATFORM=offscreen python3 -m pytest tests/ui/test_settings_page.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/strawberry_order_management/ui/pages/settings_page.py tests/ui/test_settings_page.py
git commit -m "feat: add shared product preset settings"
```

## Task 4: Add Per-Shop Field Mapping UI

**Files:**
- Modify: `src/strawberry_order_management/ui/pages/settings_page.py`
- Test: `tests/ui/test_settings_page.py`

- [ ] **Step 1: Write the failing test**

```python
def test_settings_page_saves_per_shop_feishu_field_mapping(qtbot):
    page = SettingsPage()
    qtbot.addWidget(page)

    page.shop_name_edit.setText("乐宝零食店")
    page.mapping_order_date_edit.setText("订单日期")
    page.mapping_income_edit.setText("收入金额")
    page.mapping_procurement_cost_1_edit.setText("采购成本1")
    page.save_shop_button.click()

    payload = page.to_payload()

    assert payload["shops"][0]["field_mapping"]["订单日期"] == "订单日期"
    assert payload["shops"][0]["field_mapping"]["收入"] == "收入金额"
    assert payload["shops"][0]["field_mapping"]["采购成本1"] == "采购成本1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen python3 -m pytest tests/ui/test_settings_page.py::test_settings_page_saves_per_shop_feishu_field_mapping -q`
Expected: FAIL because per-shop field mapping UI is missing.

- [ ] **Step 3: Write minimal implementation**

```python
self.mapping_order_date_edit = QLineEdit()
self.mapping_income_edit = QLineEdit()
self.mapping_price_edit = QLineEdit()
self.mapping_procurement_product_1_edit = QLineEdit()
self.mapping_procurement_quantity_1_edit = QLineEdit()
self.mapping_procurement_cost_1_edit = QLineEdit()
```

- [ ] **Step 4: Run settings page tests**

Run: `QT_QPA_PLATFORM=offscreen python3 -m pytest tests/ui/test_settings_page.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/strawberry_order_management/ui/pages/settings_page.py tests/ui/test_settings_page.py
git commit -m "feat: add per-shop feishu field mappings"
```

## Task 5: Add Three Procurement Slots To Intake

**Files:**
- Modify: `src/strawberry_order_management/ui/widgets/order_card_widget.py`
- Modify: `src/strawberry_order_management/ui/pages/intake_page.py`
- Test: `tests/ui/test_intake_page.py`

- [ ] **Step 1: Write the failing test**

```python
def test_order_card_autofills_procurement_cost_from_selected_preset(qtbot):
    page = IntakePage(use_background_thread=False)
    qtbot.addWidget(page)

    page.set_product_presets([{"name": "澳洲婴儿水", "default_cost": "18.50"}])
    page.show_order(sample_order())

    page.order_card_widget.procurement_product_1_combo.setCurrentText("澳洲婴儿水")

    assert page.order_card_widget.procurement_quantity_1_edit.text() == "1"
    assert page.order_card_widget.procurement_cost_1_edit.text() == "18.50"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen python3 -m pytest tests/ui/test_intake_page.py::test_order_card_autofills_procurement_cost_from_selected_preset -q`
Expected: FAIL because procurement controls do not exist yet.

- [ ] **Step 3: Write minimal implementation**

```python
for index in range(1, 4):
    layout.addRow(self._label(f"采购商品{index}"), product_combo)
    layout.addRow(self._label(f"采购数量{index}"), quantity_edit)
    layout.addRow(self._label(f"采购成本{index}"), cost_edit)
```

- [ ] **Step 4: Run intake page tests**

Run: `QT_QPA_PLATFORM=offscreen python3 -m pytest tests/ui/test_intake_page.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/strawberry_order_management/ui/widgets/order_card_widget.py src/strawberry_order_management/ui/pages/intake_page.py tests/ui/test_intake_page.py
git commit -m "feat: add procurement slots to intake"
```

## Task 6: Sync Presets And Mapping Through Main Window

**Files:**
- Modify: `src/strawberry_order_management/ui/main_window.py`
- Test: `tests/ui/test_main_window.py`

- [ ] **Step 1: Write the failing test**

```python
def test_main_window_uses_shop_mapping_and_procurement_fields_for_feishu_submit(qtbot, tmp_path, monkeypatch):
    config_store = ConfigStore(tmp_path / "config.json")
    history_store = HistoryStore(tmp_path / "history.json")
    config_store.save(
        {
            "feishu_app_id": "cli_app_123",
            "feishu_app_secret": "secret_456",
            "product_presets": [{"name": "澳洲婴儿水", "default_cost": "18.50"}],
            "shops": [
                {
                    "name": "乐宝零食店",
                    "app_token": "app_token",
                    "table_id": "tbl_1",
                    "table_name": "订单表",
                    "field_mapping": {
                        "收入": "收入金额",
                        "采购商品1": "采购商品1",
                        "采购数量1": "采购数量1",
                        "采购成本1": "采购成本1",
                    },
                }
            ],
            "selected_shop_name": "乐宝零食店",
        }
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen python3 -m pytest tests/ui/test_main_window.py::test_main_window_uses_shop_mapping_and_procurement_fields_for_feishu_submit -q`
Expected: FAIL because main window does not yet sync presets or mappings.

- [ ] **Step 3: Write minimal implementation**

```python
self.intake_page.set_product_presets(settings_payload.get("product_presets", []))
mapping = shop.get("field_mapping") or DEFAULT_FEISHU_FIELD_MAPPING
task["fields"] = build_feishu_payload(payload["order"], mapping)
```

- [ ] **Step 4: Run main window tests**

Run: `QT_QPA_PLATFORM=offscreen python3 -m pytest tests/ui/test_main_window.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/strawberry_order_management/ui/main_window.py tests/ui/test_main_window.py
git commit -m "feat: wire presets and field mapping into feishu submit"
```

## Task 7: Final Verification

**Files:**
- Modify: none expected unless verification exposes a gap
- Test: `tests/test_pipeline.py`, `tests/ui/test_settings_page.py`, `tests/ui/test_intake_page.py`, `tests/ui/test_main_window.py`

- [ ] **Step 1: Run the full test suite**

Run: `python3 -m pytest tests -q`
Expected: `PASS` with all tests green.

- [ ] **Step 2: Run an offscreen smoke check**

Run:

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src python3 - <<'PY'
from PySide6.QtWidgets import QApplication
from strawberry_order_management.ui.main_window import MainWindow
app = QApplication([])
window = MainWindow()
assert window.intake_page.submit_button.text() == "确认写入飞书"
assert window.intake_page.shop_selector.count() >= 0
print("smoke ok")
window.close()
app.quit()
PY
```

Expected: prints `smoke ok`

- [ ] **Step 3: Commit any last verification-driven fixes**

```bash
git add -A
git commit -m "test: finalize mapping and procurement workflow"
```

## Self-Review

- Spec coverage:
  - Shared global product presets: covered by Task 3 and Task 5.
  - Three procurement slots with default quantity `1`: covered by Task 5.
  - Keep order-level income, stop forcing `价格`: covered by Task 2 and Task 6.
  - User-controlled Feishu field input per shop: covered by Task 4 and Task 6.
- Placeholder scan: no `TODO`/`TBD` placeholders remain.
- Type consistency:
  - `ProcurementItem`
  - `field_mapping`
  - `product_presets`
  These names are used consistently across tasks.
