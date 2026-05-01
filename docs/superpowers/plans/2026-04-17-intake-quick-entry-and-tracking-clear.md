# 录单页快速填写与快递单号清空 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 调整录单页主表单顺序与概览排布，并为录单页和历史订单页的采购快递单号增加单格清空按钮，同时保持现有业务逻辑与数据结构不变。

**Architecture:** 复用现有 `OrderCardWidget` 和 `HistoryPage` 的输入控件与信号流，只修改 UI 结构与局部交互。先用 UI 测试锁定区块顺序、同排字段和清空行为，再做最小实现，避免影响采购模板、财务联动和历史保存逻辑。

**Tech Stack:** Python 3, PySide6, pytest, pytest-qt

---

### Task 1: 锁定录单页新布局与采购清空交互

**Files:**
- Modify: `tests/ui/test_intake_page.py`
- Test: `tests/ui/test_intake_page.py`

- [ ] **Step 1: 写出录单页布局与清空按钮的失败测试**

```python
def test_order_card_prioritizes_procurement_and_finance_sections(qtbot):
    page = IntakePage(use_background_thread=False)
    qtbot.addWidget(page)

    section_titles = [
        label.text()
        for label in page.order_card_widget.findChildren(QLabel)
        if label.objectName() == "SectionTitle"
    ]

    assert section_titles[:4] == ["采购信息", "财务信息", "订单概览", "收件信息"]


def test_order_card_places_income_next_to_quantity_and_order_amount(qtbot):
    page = IntakePage(use_background_thread=False)
    qtbot.addWidget(page)

    assert page.order_card_widget.income_amount_edit.parentWidget() is not None
    assert page.order_card_widget.quantity_edit.parentWidget() is not None
    assert page.order_card_widget.order_amount_edit.parentWidget() is not None


def test_order_card_clear_tracking_button_only_clears_current_slot(qtbot):
    page = IntakePage(use_background_thread=False)
    qtbot.addWidget(page)

    page.order_card_widget.procurement_tracking_number_1_edit.setText("YT99887766")
    page.order_card_widget.procurement_tracking_number_2_edit.setText("SF55667788")
    page.order_card_widget.procurement_clear_tracking_1_button.click()

    assert page.order_card_widget.procurement_tracking_number_1_edit.text() == ""
    assert page.order_card_widget.procurement_tracking_number_2_edit.text() == "SF55667788"
```

- [ ] **Step 2: 运行测试并确认当前失败**

Run: `python3 -m pytest tests/ui/test_intake_page.py -q`
Expected: 新增断言失败，说明区块顺序、同排布局或清空按钮尚未实现。

- [ ] **Step 3: 以最小改动实现录单页布局重排与清空按钮**

```python
layout.addWidget(
    self._build_section_card("采购信息", "ProcurementSectionCard", self._build_procurement_body())
)
layout.addWidget(
    self._build_section_card("财务信息", "FinancialSectionCard", self._build_financial_body())
)
layout.addWidget(
    self._build_section_card("订单概览", "OrderSummaryCard", self._build_overview_body())
)
layout.addWidget(
    self._build_section_card("收件信息", "OrderShippingCard", self._build_shipping_body())
)
```

```python
grid.addWidget(self._field_block("数量", self.quantity_edit), 1, 0)
grid.addWidget(self._field_block("商家收入", self.income_amount_edit), 1, 1)
grid.addWidget(self._field_block("订单金额", self.order_amount_edit), 1, 2)
```

```python
clear_button = QPushButton("清空")
clear_button.setObjectName("SecondaryActionButton")
clear_button.setMaximumWidth(68)
clear_button.clicked.connect(tracking_edit.clear)
```

- [ ] **Step 4: 重新运行录单页测试**

Run: `python3 -m pytest tests/ui/test_intake_page.py -q`
Expected: 新增测试与原有录单页测试全部通过。

- [ ] **Step 5: 提交这一批改动前暂不 commit，继续历史页任务**

```bash
git status --short
```

### Task 2: 锁定历史订单页快递单号清空交互

**Files:**
- Modify: `tests/ui/test_history_page.py`
- Test: `tests/ui/test_history_page.py`

- [ ] **Step 1: 写出历史订单页清空按钮的失败测试**

```python
def test_history_page_clear_tracking_button_only_clears_current_slot(qtbot):
    page = HistoryPage()
    qtbot.addWidget(page)
    page.load_rows([build_history_row()])
    page.list_widget.setCurrentRow(0)

    page.procurement_tracking_1_value.setText("YT99887766")
    page.procurement_tracking_2_value.setText("SF55667788")
    page.procurement_clear_tracking_1_button.click()

    assert page.procurement_tracking_1_value.text() == ""
    assert page.procurement_tracking_2_value.text() == "SF55667788"
```

- [ ] **Step 2: 运行测试并确认当前失败**

Run: `python3 -m pytest tests/ui/test_history_page.py -q`
Expected: 因为历史页当前没有清空按钮或属性不存在而失败。

- [ ] **Step 3: 以最小改动实现历史页采购快递单号清空按钮**

```python
self.procurement_clear_tracking_1_button = QPushButton("清空")
self.procurement_clear_tracking_1_button.clicked.connect(self.procurement_tracking_1_value.clear)
```

```python
procurement_form.addRow(
    "采购 1 快递单号",
    self._with_inline_actions(self.procurement_tracking_1_value, self.procurement_clear_tracking_1_button),
)
```

- [ ] **Step 4: 重新运行历史页测试**

Run: `python3 -m pytest tests/ui/test_history_page.py -q`
Expected: 新增清空行为测试与原有历史页测试全部通过。

### Task 3: 做一次聚合回归验证

**Files:**
- Test: `tests/ui/test_intake_page.py`
- Test: `tests/ui/test_history_page.py`
- Test: `tests/ui/test_main_window.py`

- [ ] **Step 1: 跑受影响的 UI 测试集合**

Run: `python3 -m pytest tests/ui/test_intake_page.py tests/ui/test_history_page.py tests/ui/test_main_window.py -q`
Expected: 所有相关 UI 测试通过，证明录单页、历史页和主窗口联动没有回归。

- [ ] **Step 2: 若失败，按失败信息做最小修正后重跑同一命令**

```bash
python3 -m pytest tests/ui/test_intake_page.py tests/ui/test_history_page.py tests/ui/test_main_window.py -q
```

- [ ] **Step 3: 核对需求覆盖**

```text
- 录单页顺序：采购 -> 财务 -> 概览 -> 收件
- 概览第二行：数量 / 商家收入 / 订单金额
- 录单页每条采购快递单号可单独清空
- 历史页每条采购快递单号可单独清空
- 现有保存、模板、财务联动测试仍通过
```
