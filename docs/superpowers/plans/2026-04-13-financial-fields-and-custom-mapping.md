# 财务字段与可选映射 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为录单页、历史页和飞书映射增加可停用字段、固定财务字段、3 个自定义成本字段以及自动毛利润计算。

**Architecture:** 先扩展订单数据模型与飞书字段映射，再让录单页和历史页消费同一套财务字段，最后补设置页上的映射显隐与自定义字段配置。计算逻辑集中在模型/小型辅助函数里，避免 UI 各自手算导致不一致。

**Tech Stack:** Python, PySide6, pytest

---

## File Map

- Modify: `src/strawberry_order_management/models.py`
  - 为订单补充财务字段与自定义成本字段结构
- Modify: `src/strawberry_order_management/services/pipeline.py`
  - 扩展默认飞书映射与 payload 构造
- Modify: `src/strawberry_order_management/ui/widgets/order_card_widget.py`
  - 新增财务区块、自定义成本字段、自动计算逻辑
- Modify: `src/strawberry_order_management/ui/pages/intake_page.py`
  - 将自定义字段配置注入订单卡并保持提交结构
- Modify: `src/strawberry_order_management/ui/pages/history_page.py`
  - 展示/编辑财务字段与自定义字段
- Modify: `src/strawberry_order_management/ui/pages/settings_page.py`
  - 增加自定义字段名称配置、映射停用/仅显示启用项
- Test: `tests/test_pipeline.py`
- Test: `tests/ui/test_intake_page.py`
- Test: `tests/ui/test_history_page.py`
- Test: `tests/ui/test_settings_page.py`
- Test: `tests/ui/test_main_window.py`

### Task 1: 扩展模型与飞书 payload

**Files:**
- Modify: `src/strawberry_order_management/models.py`
- Modify: `src/strawberry_order_management/services/pipeline.py`
- Test: `tests/test_pipeline.py`

- [ ] **Step 1: Write the failing test**

```python
def test_build_feishu_payload_includes_financial_fields_and_custom_costs():
    order = ParsedOrder(
        order_id="1",
        placed_at="2026-04-13 12:00:00",
        order_status="已发货",
        product_name="测试商品",
        quantity="1",
        order_amount="100",
        income_amount="80",
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
        gross_profit="40",
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
    assert payload["采购总成本"] == "30"
    assert payload["毛利润"] == "40"
    assert payload["包装费"] == "1.5"
    assert payload["赠品"] == "2.5"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen python3 -m pytest tests/test_pipeline.py::test_build_feishu_payload_includes_financial_fields_and_custom_costs -q`

Expected: FAIL with `ParsedOrder` missing new fields or payload missing expected keys.

- [ ] **Step 3: Write minimal implementation**

```python
@dataclass(frozen=True)
class ParsedOrder:
    ...
    platform_fee_rate: str = ""
    platform_fee_amount: str = ""
    other_cost: str = ""
    procurement_total_cost: str = ""
    gross_profit: str = ""
    custom_cost_labels: tuple[str, str, str] = ("", "", "")
    custom_cost_values: tuple[str, str, str] = ("", "", "")
```

```python
DEFAULT_FEISHU_FIELD_MAPPING.update(
    {
        "平台扣点比例": "",
        "平台扣点金额": "",
        "其他成本": "",
        "采购总成本": "",
        "毛利润": "",
        "自定义字段1": "",
        "自定义字段2": "",
        "自定义字段3": "",
    }
)
```

```python
source_fields.update(
    {
        "平台扣点比例": order.platform_fee_rate,
        "平台扣点金额": order.platform_fee_amount,
        "其他成本": order.other_cost,
        "采购总成本": order.procurement_total_cost,
        "毛利润": order.gross_profit,
        "自定义字段1": order.custom_cost_values[0],
        "自定义字段2": order.custom_cost_values[1],
        "自定义字段3": order.custom_cost_values[2],
    }
)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `QT_QPA_PLATFORM=offscreen python3 -m pytest tests/test_pipeline.py::test_build_feishu_payload_includes_financial_fields_and_custom_costs -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_pipeline.py src/strawberry_order_management/models.py src/strawberry_order_management/services/pipeline.py
git commit -m "feat: add financial fields to order payload"
```

### Task 2: 录单页新增财务字段与自动毛利润计算

**Files:**
- Modify: `src/strawberry_order_management/ui/widgets/order_card_widget.py`
- Modify: `src/strawberry_order_management/ui/pages/intake_page.py`
- Test: `tests/ui/test_intake_page.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_order_card_computes_fee_total_cost_and_gross_profit(qtbot):
    widget = OrderCardWidget()
    qtbot.addWidget(widget)
    widget.income_amount_edit.setText("100")
    widget.platform_fee_rate_edit.setText("10")
    widget.procurement_cost_1_edit.setText("20")
    widget.procurement_quantity_1_edit.setText("2")
    widget.other_cost_edit.setText("5")
    widget.custom_cost_value_edits[0].setText("3")

    assert widget.platform_fee_amount_edit.text() == "10.00"
    assert widget.procurement_total_cost_edit.text() == "40.00"
    assert widget.gross_profit_edit.text() == "42.00"
```

```python
def test_intake_page_submits_financial_fields_and_custom_costs(qtbot):
    page = IntakePage(use_background_thread=False)
    qtbot.addWidget(page)
    page.order_card_widget.income_amount_edit.setText("100")
    page.order_card_widget.platform_fee_rate_edit.setText("10")
    payload = page._build_submission_payload()
    assert payload["order"].platform_fee_rate == "10"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `QT_QPA_PLATFORM=offscreen python3 -m pytest tests/ui/test_intake_page.py -k "financial_fields or custom_costs" -q`

Expected: FAIL with missing widget attributes and missing order fields.

- [ ] **Step 3: Write minimal implementation**

```python
self.platform_fee_rate_edit = self._build_line_edit()
self.platform_fee_amount_edit = self._build_line_edit()
self.other_cost_edit = self._build_line_edit()
self.procurement_total_cost_edit = self._build_line_edit(read_only=True)
self.gross_profit_edit = self._build_line_edit(read_only=True)
self.custom_cost_label_edits = [QLabel(), QLabel(), QLabel()]
self.custom_cost_value_edits = [self._build_line_edit() for _ in range(3)]
```

```python
def _recalculate_financials(self) -> None:
    income = self._to_decimal(self.income_amount_edit.text())
    rate = self._to_decimal(self.platform_fee_rate_edit.text())
    fee = self._manual_or_rate_fee(income, rate)
    procurement_total = self._sum_procurement_costs()
    custom_total = sum(self._to_decimal(edit.text()) for edit in self.custom_cost_value_edits)
    other_cost = self._to_decimal(self.other_cost_edit.text())
    gross = income - fee - procurement_total - custom_total - other_cost
```

```python
return ParsedOrder(
    ...,
    platform_fee_rate=self.platform_fee_rate_edit.text().strip(),
    platform_fee_amount=self.platform_fee_amount_edit.text().strip(),
    other_cost=self.other_cost_edit.text().strip(),
    procurement_total_cost=self.procurement_total_cost_edit.text().strip(),
    gross_profit=self.gross_profit_edit.text().strip(),
    custom_cost_labels=tuple(label.text().strip() for label in self.custom_cost_label_edits),
    custom_cost_values=tuple(edit.text().strip() for edit in self.custom_cost_value_edits),
)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `QT_QPA_PLATFORM=offscreen python3 -m pytest tests/ui/test_intake_page.py -k "financial_fields or custom_costs" -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/ui/test_intake_page.py src/strawberry_order_management/ui/widgets/order_card_widget.py src/strawberry_order_management/ui/pages/intake_page.py
git commit -m "feat: add intake financial fields and gross profit"
```

### Task 3: 设置页支持自定义字段名称与可停用映射

**Files:**
- Modify: `src/strawberry_order_management/ui/pages/settings_page.py`
- Test: `tests/ui/test_settings_page.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_settings_page_persists_custom_cost_labels(qtbot):
    page = SettingsPage()
    qtbot.addWidget(page)
    page.custom_cost_label_edits[0].setText("包装费")
    payload = page.to_payload()
    assert payload["custom_cost_labels"] == ["包装费", "", ""]
```

```python
def test_settings_page_can_filter_to_enabled_mappings(qtbot):
    page = SettingsPage()
    qtbot.addWidget(page)
    page.mapping_edits["平台"].setText("平台")
    page.mapping_edits["订单编号"].clear()
    page.show_enabled_only_checkbox.setChecked(True)
    assert not page.mapping_row_widgets["订单编号"].isVisible()
    assert page.mapping_row_widgets["平台"].isVisible()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `QT_QPA_PLATFORM=offscreen python3 -m pytest tests/ui/test_settings_page.py -k "custom_cost_labels or enabled_mappings" -q`

Expected: FAIL with missing controls or payload keys.

- [ ] **Step 3: Write minimal implementation**

```python
self.custom_cost_label_edits = [QLineEdit() for _ in range(3)]
self.show_enabled_only_checkbox = QCheckBox("仅显示启用字段")
self.mapping_row_widgets: dict[str, QWidget] = {}
```

```python
def _update_mapping_visibility(self) -> None:
    enabled_only = self.show_enabled_only_checkbox.isChecked()
    for key, row_widget in self.mapping_row_widgets.items():
        has_value = bool(self.mapping_edits[key].text().strip())
        row_widget.setVisible((not enabled_only) or has_value)
```

```python
def to_payload(self) -> dict:
    payload.update(
        {
            "custom_cost_labels": [edit.text().strip() for edit in self.custom_cost_label_edits],
            "show_only_enabled_mappings": self.show_enabled_only_checkbox.isChecked(),
        }
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `QT_QPA_PLATFORM=offscreen python3 -m pytest tests/ui/test_settings_page.py -k "custom_cost_labels or enabled_mappings" -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/ui/test_settings_page.py src/strawberry_order_management/ui/pages/settings_page.py
git commit -m "feat: add custom cost labels and mapping filters"
```

### Task 4: 历史页承接财务字段并支持重写飞书

**Files:**
- Modify: `src/strawberry_order_management/ui/pages/history_page.py`
- Modify: `src/strawberry_order_management/ui/pages/intake_page.py`
- Modify: `src/strawberry_order_management/ui/widgets/order_card_widget.py`
- Modify: `src/strawberry_order_management/ui/main_window.py`
- Test: `tests/ui/test_history_page.py`
- Test: `tests/ui/test_main_window.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_history_page_loads_and_saves_financial_fields(qtbot):
    page = HistoryPage()
    qtbot.addWidget(page)
    row = _row(
        order_snapshot={
            "platform_fee_rate": "10",
            "platform_fee_amount": "8",
            "other_cost": "2",
            "procurement_total_cost": "30",
            "gross_profit": "40",
            "custom_cost_labels": ["包装费", "", ""],
            "custom_cost_values": ["1.5", "", ""],
        }
    )
    page.load_rows([row])
    page.list_widget.setCurrentRow(0)
    assert page.platform_fee_rate_edit.text() == "10"
```

```python
def test_main_window_rewrites_feishu_with_financial_fields(qtbot):
    ...
    assert captured["fields"]["毛利润"] == "40.00"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `QT_QPA_PLATFORM=offscreen python3 -m pytest tests/ui/test_history_page.py tests/ui/test_main_window.py -k "financial" -q`

Expected: FAIL with missing snapshot keys or missing field propagation.

- [ ] **Step 3: Write minimal implementation**

```python
ORDER_SNAPSHOT_KEYS += (
    "platform_fee_rate",
    "platform_fee_amount",
    "other_cost",
    "procurement_total_cost",
    "gross_profit",
    "custom_cost_labels",
    "custom_cost_values",
)
```

```python
order = ParsedOrder(
    ...,
    platform_fee_rate=snapshot.get("platform_fee_rate", ""),
    platform_fee_amount=snapshot.get("platform_fee_amount", ""),
    other_cost=snapshot.get("other_cost", ""),
    procurement_total_cost=snapshot.get("procurement_total_cost", ""),
    gross_profit=snapshot.get("gross_profit", ""),
    custom_cost_labels=tuple(snapshot.get("custom_cost_labels", ["", "", ""])),
    custom_cost_values=tuple(snapshot.get("custom_cost_values", ["", "", ""])),
)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `QT_QPA_PLATFORM=offscreen python3 -m pytest tests/ui/test_history_page.py tests/ui/test_main_window.py -k "financial" -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/ui/test_history_page.py tests/ui/test_main_window.py src/strawberry_order_management/ui/pages/history_page.py src/strawberry_order_management/ui/main_window.py
git commit -m "feat: persist financial fields in history and sync"
```

### Task 5: Full regression verification

**Files:**
- Test: `tests/test_pipeline.py`
- Test: `tests/ui/test_intake_page.py`
- Test: `tests/ui/test_settings_page.py`
- Test: `tests/ui/test_history_page.py`
- Test: `tests/ui/test_main_window.py`

- [ ] **Step 1: Run non-UI regression**

Run: `QT_QPA_PLATFORM=offscreen python3 -m pytest tests/test_*.py -q`

Expected: PASS

- [ ] **Step 2: Run intake/settings UI regression**

Run: `QT_QPA_PLATFORM=offscreen python3 -m pytest tests/ui/test_intake_page.py tests/ui/test_settings_page.py -q`

Expected: PASS

- [ ] **Step 3: Run history/main-window UI regression**

Run: `QT_QPA_PLATFORM=offscreen python3 -m pytest tests/ui/test_history_page.py tests/ui/test_main_window.py -q`

Expected: PASS

- [ ] **Step 4: Run offscreen smoke check**

Run: `QT_QPA_PLATFORM=offscreen PYTHONPATH=src python3 - <<'PY'\nfrom PySide6.QtWidgets import QApplication\nfrom strawberry_order_management.ui.main_window import MainWindow\napp = QApplication([])\nwindow = MainWindow()\nprint(window.intake_page.platform_selector.currentText())\nprint(window.settings_page.show_enabled_only_checkbox.isChecked())\nwindow.close()\nPY`

Expected:

```text
抖店
False
```

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "test: verify financial fields workflow"
```
