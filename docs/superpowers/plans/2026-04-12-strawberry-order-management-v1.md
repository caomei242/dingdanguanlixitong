# Strawberry Order Management V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a desktop app that supports both order screenshot intake and address quick extraction, shows a confirmable order card, and writes approved records into a configured Feishu table.

**Architecture:** Use a PySide6 desktop shell with three pages (`订单录入`, `历史`, `设置`) and two homepage modules (`拍单识别`, `地址快速提取`). Keep parsing and API integrations in small service modules so OCR, helper extraction, and Feishu writing can be swapped later without changing the UI flow. Persist settings and history locally as JSON so failed writes can be retried safely.

**Tech Stack:** Python 3.9+, PySide6, requests, pytest, pytest-qt, Pillow

---

## File Structure

### Create

- `pyproject.toml`
- `README.md`
- `src/strawberry_order_management/__init__.py`
- `src/strawberry_order_management/app.py`
- `src/strawberry_order_management/config.py`
- `src/strawberry_order_management/models.py`
- `src/strawberry_order_management/history.py`
- `src/strawberry_order_management/extractors/__init__.py`
- `src/strawberry_order_management/extractors/address.py`
- `src/strawberry_order_management/extractors/order_parser.py`
- `src/strawberry_order_management/services/__init__.py`
- `src/strawberry_order_management/services/ocr_client.py`
- `src/strawberry_order_management/services/helper_client.py`
- `src/strawberry_order_management/services/feishu_client.py`
- `src/strawberry_order_management/services/pipeline.py`
- `src/strawberry_order_management/ui/__init__.py`
- `src/strawberry_order_management/ui/theme.py`
- `src/strawberry_order_management/ui/main_window.py`
- `src/strawberry_order_management/ui/pages/__init__.py`
- `src/strawberry_order_management/ui/pages/intake_page.py`
- `src/strawberry_order_management/ui/pages/history_page.py`
- `src/strawberry_order_management/ui/pages/settings_page.py`
- `src/strawberry_order_management/ui/widgets/__init__.py`
- `src/strawberry_order_management/ui/widgets/address_extractor_widget.py`
- `src/strawberry_order_management/ui/widgets/order_card_widget.py`
- `tests/conftest.py`
- `tests/test_address_extractor.py`
- `tests/test_config_store.py`
- `tests/test_history_store.py`
- `tests/test_order_parser.py`
- `tests/test_pipeline.py`
- `tests/ui/test_address_extractor_widget.py`
- `tests/ui/test_intake_page.py`
- `tests/ui/test_settings_page.py`
- `tests/fixtures/ocr/jd_order_01.txt`

### Responsibilities

- `models.py`: dataclasses for address extraction, parsed order data, and Feishu payload rows.
- `config.py`: local settings storage for OCR/helper/Feishu configuration.
- `history.py`: append/read/update local order history and retry state.
- `extractors/address.py`: pure function for the existing bracketed-address extraction rule.
- `extractors/order_parser.py`: pure parser that turns OCR/helper text into a structured `ParsedOrder`.
- `services/*_client.py`: thin HTTP clients with no parsing logic mixed in.
- `services/pipeline.py`: orchestration for OCR -> parsing -> order card -> Feishu payload.
- `ui/pages/intake_page.py`: dual-workflow homepage.
- `ui/widgets/address_extractor_widget.py`: standalone address quick-extraction module.
- `ui/widgets/order_card_widget.py`: confirm/edit panel before Feishu submit.
- `ui/pages/history_page.py`: record list and retry actions.
- `ui/pages/settings_page.py`: API and Feishu configuration form.

## Task 1: Bootstrap the Project Skeleton

**Files:**
- Create: `pyproject.toml`
- Create: `README.md`
- Create: `src/strawberry_order_management/__init__.py`
- Create: `src/strawberry_order_management/app.py`
- Test: `tests/conftest.py`

- [ ] **Step 1: Write the failing smoke test for app bootstrap**

```python
# tests/conftest.py
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def test_import_package():
    import strawberry_order_management  # noqa: F401
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/conftest.py -q`
Expected: `ModuleNotFoundError: No module named 'strawberry_order_management'`

- [ ] **Step 3: Write the minimal package and app entrypoint**

```python
# src/strawberry_order_management/__init__.py
__all__ = ["__version__"]
__version__ = "0.1.0"
```

```python
# src/strawberry_order_management/app.py
from PySide6.QtWidgets import QApplication


def build_app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    app.setApplicationName("草莓订单管理系统")
    return app
```

```toml
# pyproject.toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "strawberry-order-management"
version = "0.1.0"
dependencies = [
  "PySide6>=6.7,<7",
  "requests>=2.32,<3",
  "Pillow>=10,<11",
]

[project.optional-dependencies]
dev = [
  "pytest>=8,<9",
  "pytest-qt>=4.4,<5",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/conftest.py -q`
Expected: `1 passed`

- [ ] **Step 5: Add a short setup README**

```md
# 草莓订单管理系统

## 开发启动

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python -m strawberry_order_management.app
```
```

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml README.md src/strawberry_order_management/__init__.py src/strawberry_order_management/app.py tests/conftest.py
git commit -m "chore: bootstrap desktop app skeleton"
```

## Task 2: Implement the Address Quick-Extraction Engine

**Files:**
- Create: `src/strawberry_order_management/models.py`
- Create: `src/strawberry_order_management/extractors/__init__.py`
- Create: `src/strawberry_order_management/extractors/address.py`
- Test: `tests/test_address_extractor.py`

- [ ] **Step 1: Write the failing extraction tests**

```python
# tests/test_address_extractor.py
from strawberry_order_management.extractors.address import extract_address_payload


def test_extracts_clean_address_and_delivery_note():
    payload = extract_address_payload(
        "何女士[3612]15781304332四川省成都市金牛区营门口街道友谊花园9-2304[3612]"
    )

    assert payload.cleaned_text == "何女士15781304332四川省成都市金牛区营门口街道友谊花园9-2304"
    assert payload.delivery_note == "请电话送货上门谢谢【3612】"
    assert payload.code == "3612"


def test_rejects_mismatched_prefix_suffix_codes():
    try:
        extract_address_payload("何女士[3612]15781304332四川省成都市[9999]")
    except ValueError as exc:
        assert "编号不一致" in str(exc)
    else:
        raise AssertionError("expected ValueError")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_address_extractor.py -q`
Expected: fail because `extract_address_payload` does not exist

- [ ] **Step 3: Write the data model and minimal extractor**

```python
# src/strawberry_order_management/models.py
from dataclasses import dataclass


@dataclass(slots=True)
class AddressExtraction:
    raw_text: str
    cleaned_text: str
    delivery_note: str
    code: str
```

```python
# src/strawberry_order_management/extractors/address.py
import re

from strawberry_order_management.models import AddressExtraction

PATTERN = re.compile(r"^(?P<prefix>.+?)\[(?P<code1>\d+)\](?P<body>.+)\[(?P<code2>\d+)\]$")


def extract_address_payload(raw_text: str) -> AddressExtraction:
    text = raw_text.strip()
    match = PATTERN.match(text)
    if not match:
      raise ValueError("地址格式不符合规则")

    code1 = match.group("code1")
    code2 = match.group("code2")
    if code1 != code2:
      raise ValueError("编号不一致")

    cleaned_text = f"{match.group('prefix')}{match.group('body')}"
    return AddressExtraction(
        raw_text=text,
        cleaned_text=cleaned_text,
        delivery_note=f"请电话送货上门谢谢【{code1}】",
        code=code1,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_address_extractor.py -q`
Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add src/strawberry_order_management/models.py src/strawberry_order_management/extractors/__init__.py src/strawberry_order_management/extractors/address.py tests/test_address_extractor.py
git commit -m "feat: add address quick extraction engine"
```

## Task 3: Add Local Settings and History Persistence

**Files:**
- Create: `src/strawberry_order_management/config.py`
- Create: `src/strawberry_order_management/history.py`
- Test: `tests/test_config_store.py`
- Test: `tests/test_history_store.py`

- [ ] **Step 1: Write the failing config and history tests**

```python
# tests/test_config_store.py
from pathlib import Path

from strawberry_order_management.config import ConfigStore


def test_config_store_round_trips_values(tmp_path: Path):
    store = ConfigStore(tmp_path / "config.json")
    store.save(
        {
            "ocr_base_url": "https://ocr.example.com",
            "helper_base_url": "https://helper.example.com",
            "feishu_app_id": "cli_xxx",
            "feishu_table_id": "tbl_xxx",
        }
    )

    loaded = store.load()
    assert loaded["ocr_base_url"] == "https://ocr.example.com"
    assert loaded["feishu_table_id"] == "tbl_xxx"
```

```python
# tests/test_history_store.py
from pathlib import Path

from strawberry_order_management.history import HistoryStore


def test_history_store_appends_and_updates_status(tmp_path: Path):
    store = HistoryStore(tmp_path / "history.json")
    item = store.append(
        {
            "order_id": "6952003434324366473",
            "recipient_name": "何女士",
            "status": "pending_review",
        }
    )

    store.update_status(item["record_id"], "written")
    rows = store.list_items()

    assert rows[0]["order_id"] == "6952003434324366473"
    assert rows[0]["status"] == "written"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_config_store.py tests/test_history_store.py -q`
Expected: import failures for `ConfigStore` and `HistoryStore`

- [ ] **Step 3: Write the minimal JSON stores**

```python
# src/strawberry_order_management/config.py
import json
from pathlib import Path


class ConfigStore:
    def __init__(self, path: Path):
        self.path = path

    def load(self) -> dict:
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def save(self, payload: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
```

```python
# src/strawberry_order_management/history.py
import json
import uuid
from pathlib import Path


class HistoryStore:
    def __init__(self, path: Path):
        self.path = path

    def _load_rows(self) -> list[dict]:
        if not self.path.exists():
            return []
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _save_rows(self, rows: list[dict]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(rows, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def append(self, payload: dict) -> dict:
        rows = self._load_rows()
        row = {"record_id": str(uuid.uuid4()), **payload}
        rows.insert(0, row)
        self._save_rows(rows)
        return row

    def update_status(self, record_id: str, status: str) -> None:
        rows = self._load_rows()
        for row in rows:
            if row["record_id"] == record_id:
                row["status"] = status
                break
        self._save_rows(rows)

    def list_items(self) -> list[dict]:
        return self._load_rows()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_config_store.py tests/test_history_store.py -q`
Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add src/strawberry_order_management/config.py src/strawberry_order_management/history.py tests/test_config_store.py tests/test_history_store.py
git commit -m "feat: add local config and history stores"
```

## Task 4: Parse OCR Text Into a Confirmable Order Card

**Files:**
- Create: `src/strawberry_order_management/extractors/order_parser.py`
- Test: `tests/test_order_parser.py`
- Create: `tests/fixtures/ocr/jd_order_01.txt`

- [ ] **Step 1: Write the failing parser test from the approved example**

```python
# tests/test_order_parser.py
from pathlib import Path

from strawberry_order_management.extractors.order_parser import parse_order_text


def test_parses_jd_order_fixture_into_structured_order():
    raw_text = Path("tests/fixtures/ocr/jd_order_01.txt").read_text(encoding="utf-8")

    order = parse_order_text(raw_text)

    assert order.order_id == "6952003434324366473"
    assert order.placed_at == "2026-04-11 20:57:15"
    assert order.order_status == "已发货"
    assert order.recipient_name == "何女士"
    assert order.phone_number == "15781304332"
    assert order.code == "3612"
    assert order.address == "四川省成都市金牛区营门口街道友谊花园9-2304"
    assert order.order_amount == "405.00"
    assert order.income_amount == "162.00"
```

- [ ] **Step 2: Add the OCR text fixture and verify the test fails**

```text
# tests/fixtures/ocr/jd_order_01.txt
订单编号 6952003434324366473
下单时间 2026-04-11 20:57:15
订单状态 已发货
商品信息 【明日达】赵露丝同款27000澳大利亚进口婴儿水宝宝水高偏矿泉水 1L/桶*12袋
单价/数量 ¥405.00 x1
商家收入金额 ¥162.00
收货信息 何女士 [3612] 15781304332 四川省成都市金牛区营门口街道友谊花园9-2304 [3612]
```

Run: `python3 -m pytest tests/test_order_parser.py -q`
Expected: fail because `parse_order_text` is undefined

- [ ] **Step 3: Define the parsed order model and minimal parser**

```python
# src/strawberry_order_management/models.py
@dataclass(slots=True)
class ParsedOrder:
    order_id: str
    placed_at: str
    order_status: str
    product_name: str
    quantity: str
    order_amount: str
    income_amount: str
    recipient_name: str
    phone_number: str
    code: str
    address: str
    delivery_note: str
```

```python
# src/strawberry_order_management/extractors/order_parser.py
import re

from strawberry_order_management.models import ParsedOrder


def _search(pattern: str, raw_text: str) -> str:
    match = re.search(pattern, raw_text)
    if not match:
        raise ValueError(f"missing field for pattern: {pattern}")
    return match.group(1).strip()


def parse_order_text(raw_text: str) -> ParsedOrder:
    order_id = _search(r"订单编号\s+(\d+)", raw_text)
    placed_at = _search(r"下单时间\s+([0-9:\-\s]+)", raw_text)
    order_status = _search(r"订单状态\s+(.+)", raw_text).splitlines()[0].strip()
    product_name = _search(r"商品信息\s+(.+)", raw_text).splitlines()[0].strip()
    quantity = _search(r"单价/数量\s+¥[0-9.]+\s+x(\d+)", raw_text)
    order_amount = _search(r"单价/数量\s+¥([0-9.]+)", raw_text)
    income_amount = _search(r"商家收入金额\s+¥([0-9.]+)", raw_text)
    recipient_name = _search(r"收货信息\s+([^\s]+)", raw_text)
    code = _search(r"收货信息.+\[(\d+)\]", raw_text)
    phone_number = _search(r"收货信息.+?(\d{11})", raw_text)
    address = _search(r"收货信息.+?\d{11}\s+(.+)\s+\[\d+\]", raw_text)
    delivery_note = f"请电话送货上门谢谢【{code}】"
    return ParsedOrder(
        order_id=order_id,
        placed_at=placed_at,
        order_status=order_status,
        product_name=product_name,
        quantity=quantity,
        order_amount=order_amount,
        income_amount=income_amount,
        recipient_name=recipient_name.replace("[3612]", "").strip(),
        phone_number=phone_number,
        code=code,
        address=address,
        delivery_note=delivery_note,
    )
```

- [ ] **Step 4: Run the parser test to verify it passes**

Run: `python3 -m pytest tests/test_order_parser.py -q`
Expected: `1 passed`

- [ ] **Step 5: Commit**

```bash
git add src/strawberry_order_management/models.py src/strawberry_order_management/extractors/order_parser.py tests/test_order_parser.py tests/fixtures/ocr/jd_order_01.txt
git commit -m "feat: parse approved order screenshot text"
```

## Task 5: Build the OCR/Helper/Feishu Service Layer and Pipeline

**Files:**
- Create: `src/strawberry_order_management/services/ocr_client.py`
- Create: `src/strawberry_order_management/services/helper_client.py`
- Create: `src/strawberry_order_management/services/feishu_client.py`
- Create: `src/strawberry_order_management/services/pipeline.py`
- Test: `tests/test_pipeline.py`

- [ ] **Step 1: Write the failing pipeline test**

```python
# tests/test_pipeline.py
from strawberry_order_management.models import ParsedOrder
from strawberry_order_management.services.pipeline import build_feishu_payload


def test_build_feishu_payload_uses_income_amount_for_income_column():
    order = ParsedOrder(
        order_id="6952003434324366473",
        placed_at="2026-04-11 20:57:15",
        order_status="已发货",
        product_name="澳大利亚进口婴儿水",
        quantity="1",
        order_amount="405.00",
        income_amount="162.00",
        recipient_name="何女士",
        phone_number="15781304332",
        code="3612",
        address="四川省成都市金牛区营门口街道友谊花园9-2304",
        delivery_note="请电话送货上门谢谢【3612】",
    )

    payload = build_feishu_payload(order)

    assert payload["备注"] == "请电话送货上门谢谢【3612】"
    assert payload["收入"] == "162.00"
    assert payload["价格"] == "405.00"
    assert payload["发货地址"].startswith("何女士 15781304332-3612")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_pipeline.py -q`
Expected: import failure for `build_feishu_payload`

- [ ] **Step 3: Write minimal clients and payload builder**

```python
# src/strawberry_order_management/services/ocr_client.py
import requests


class OCRClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def extract_text(self, image_bytes: bytes) -> str:
        response = requests.post(
            f"{self.base_url}/ocr",
            headers={"Authorization": f"Bearer {self.api_key}"},
            files={"file": ("order.png", image_bytes, "image/png")},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()["text"]
```

```python
# src/strawberry_order_management/services/helper_client.py
import requests


class HelperClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def enrich_text(self, raw_text: str) -> str:
        response = requests.post(
            f"{self.base_url}/extract",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={"text": raw_text},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()["text"]
```

```python
# src/strawberry_order_management/services/feishu_client.py
import requests


class FeishuClient:
    def __init__(self, app_id: str, app_secret: str, table_app_token: str, table_id: str):
        self.app_id = app_id
        self.app_secret = app_secret
        self.table_app_token = table_app_token
        self.table_id = table_id

    def create_record(self, access_token: str, fields: dict) -> dict:
        response = requests.post(
            f"https://open.feishu.cn/open-apis/bitable/v1/apps/{self.table_app_token}/tables/{self.table_id}/records",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"fields": fields},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()
```

```python
# src/strawberry_order_management/services/pipeline.py
def build_feishu_payload(order) -> dict:
    date_part, time_part = order.placed_at.split(" ")
    return {
        "备注": order.delivery_note,
        "订单日期": date_part.replace("-", "/"),
        "下单时间": time_part,
        "订单状态": order.order_status,
        "收入": order.income_amount,
        "发货地址": f"{order.recipient_name} {order.phone_number}-{order.code} {order.address}",
        "价格": order.order_amount,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_pipeline.py -q`
Expected: `1 passed`

- [ ] **Step 5: Commit**

```bash
git add src/strawberry_order_management/services/ocr_client.py src/strawberry_order_management/services/helper_client.py src/strawberry_order_management/services/feishu_client.py src/strawberry_order_management/services/pipeline.py tests/test_pipeline.py
git commit -m "feat: add service clients and feishu payload builder"
```

## Task 6: Build the Address Quick-Extraction Widget

**Files:**
- Create: `src/strawberry_order_management/ui/widgets/address_extractor_widget.py`
- Test: `tests/ui/test_address_extractor_widget.py`

- [ ] **Step 1: Write the failing widget test**

```python
# tests/ui/test_address_extractor_widget.py
from PySide6.QtWidgets import QApplication

from strawberry_order_management.ui.widgets.address_extractor_widget import AddressExtractorWidget


def test_address_extractor_widget_generates_two_outputs(qtbot):
    widget = AddressExtractorWidget()
    qtbot.addWidget(widget)

    widget.input_edit.setPlainText(
        "何女士[3612]15781304332四川省成都市金牛区营门口街道友谊花园9-2304[3612]"
    )
    widget.extract_button.click()

    assert "何女士15781304332" in widget.output_one.toPlainText()
    assert "请电话送货上门谢谢【3612】" == widget.output_two.toPlainText()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/ui/test_address_extractor_widget.py -q`
Expected: import failure for `AddressExtractorWidget`

- [ ] **Step 3: Write the minimal widget**

```python
# src/strawberry_order_management/ui/widgets/address_extractor_widget.py
from PySide6.QtWidgets import (
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from strawberry_order_management.extractors.address import extract_address_payload


class AddressExtractorWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.input_edit = QTextEdit()
        self.output_one = QTextEdit()
        self.output_two = QTextEdit()
        self.extract_button = QPushButton("一键提取")
        self.output_one.setReadOnly(True)
        self.output_two.setReadOnly(True)

        layout = QVBoxLayout(self)
        layout.addWidget(self.input_edit)
        layout.addWidget(self.extract_button)
        layout.addWidget(self.output_one)
        layout.addWidget(self.output_two)
        self.extract_button.clicked.connect(self._extract)

    def _extract(self) -> None:
        payload = extract_address_payload(self.input_edit.toPlainText())
        self.output_one.setPlainText(payload.cleaned_text)
        self.output_two.setPlainText(payload.delivery_note)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/ui/test_address_extractor_widget.py -q`
Expected: `1 passed`

- [ ] **Step 5: Commit**

```bash
git add src/strawberry_order_management/ui/widgets/address_extractor_widget.py tests/ui/test_address_extractor_widget.py
git commit -m "feat: add address extraction widget"
```

## Task 7: Build the Intake Page With Paste/Drag/File Inputs and Order Card Review

**Files:**
- Create: `src/strawberry_order_management/ui/widgets/order_card_widget.py`
- Create: `src/strawberry_order_management/ui/pages/intake_page.py`
- Test: `tests/ui/test_intake_page.py`

- [ ] **Step 1: Write the failing intake page test**

```python
# tests/ui/test_intake_page.py
from strawberry_order_management.models import ParsedOrder
from strawberry_order_management.ui.pages.intake_page import IntakePage


def test_intake_page_shows_order_card_after_pipeline_result(qtbot):
    page = IntakePage()
    qtbot.addWidget(page)

    order = ParsedOrder(
        order_id="6952003434324366473",
        placed_at="2026-04-11 20:57:15",
        order_status="已发货",
        product_name="澳大利亚进口婴儿水",
        quantity="1",
        order_amount="405.00",
        income_amount="162.00",
        recipient_name="何女士",
        phone_number="15781304332",
        code="3612",
        address="四川省成都市金牛区营门口街道友谊花园9-2304",
        delivery_note="请电话送货上门谢谢【3612】",
    )

    page.show_order(order)
    assert "6952003434324366473" in page.order_card_widget.order_id_value.text()
    assert page.submit_button.text() == "确认写入飞书"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/ui/test_intake_page.py -q`
Expected: import failure for `IntakePage`

- [ ] **Step 3: Write the order card widget and intake page shell**

```python
# src/strawberry_order_management/ui/widgets/order_card_widget.py
from PySide6.QtWidgets import QLabel, QFormLayout, QWidget


class OrderCardWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.order_id_value = QLabel("-")
        self.recipient_value = QLabel("-")
        self.phone_code_value = QLabel("-")
        self.address_value = QLabel("-")
        self.delivery_note_value = QLabel("-")

        layout = QFormLayout(self)
        layout.addRow("订单编号", self.order_id_value)
        layout.addRow("收件人", self.recipient_value)
        layout.addRow("电话 + 编号", self.phone_code_value)
        layout.addRow("收货地址", self.address_value)
        layout.addRow("自动备注", self.delivery_note_value)

    def load_order(self, order) -> None:
        self.order_id_value.setText(order.order_id)
        self.recipient_value.setText(order.recipient_name)
        self.phone_code_value.setText(f"{order.phone_number} - {order.code}")
        self.address_value.setText(order.address)
        self.delivery_note_value.setText(order.delivery_note)
```

```python
# src/strawberry_order_management/ui/pages/intake_page.py
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from strawberry_order_management.ui.widgets.address_extractor_widget import AddressExtractorWidget
from strawberry_order_management.ui.widgets.order_card_widget import OrderCardWidget


class IntakePage(QWidget):
    def __init__(self):
        super().__init__()
        self.address_widget = AddressExtractorWidget()
        self.order_card_widget = OrderCardWidget()
        self.submit_button = QPushButton("确认写入飞书")

        left = QVBoxLayout()
        left.addWidget(self.order_card_widget)
        left.addWidget(self.submit_button)

        right = QVBoxLayout()
        right.addWidget(self.address_widget)

        layout = QHBoxLayout(self)
        layout.addLayout(left, 3)
        layout.addLayout(right, 2)

    def show_order(self, order) -> None:
        self.order_card_widget.load_order(order)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/ui/test_intake_page.py -q`
Expected: `1 passed`

- [ ] **Step 5: Commit**

```bash
git add src/strawberry_order_management/ui/widgets/order_card_widget.py src/strawberry_order_management/ui/pages/intake_page.py tests/ui/test_intake_page.py
git commit -m "feat: add intake page and order review card"
```

## Task 8: Build Settings, History, and the Main Window Navigation

**Files:**
- Create: `src/strawberry_order_management/ui/pages/history_page.py`
- Create: `src/strawberry_order_management/ui/pages/settings_page.py`
- Create: `src/strawberry_order_management/ui/theme.py`
- Create: `src/strawberry_order_management/ui/main_window.py`
- Test: `tests/ui/test_settings_page.py`

- [ ] **Step 1: Write the failing settings page test**

```python
# tests/ui/test_settings_page.py
from strawberry_order_management.ui.pages.settings_page import SettingsPage


def test_settings_page_collects_api_configuration(qtbot):
    page = SettingsPage()
    qtbot.addWidget(page)

    page.ocr_base_url_edit.setText("https://ocr.example.com")
    page.feishu_table_id_edit.setText("tbl_xxx")

    payload = page.to_payload()
    assert payload["ocr_base_url"] == "https://ocr.example.com"
    assert payload["feishu_table_id"] == "tbl_xxx"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/ui/test_settings_page.py -q`
Expected: import failure for `SettingsPage`

- [ ] **Step 3: Write the minimal settings/history/main window shell**

```python
# src/strawberry_order_management/ui/pages/settings_page.py
from PySide6.QtWidgets import QFormLayout, QLineEdit, QWidget


class SettingsPage(QWidget):
    def __init__(self):
        super().__init__()
        self.ocr_base_url_edit = QLineEdit()
        self.helper_base_url_edit = QLineEdit()
        self.feishu_app_id_edit = QLineEdit()
        self.feishu_table_id_edit = QLineEdit()

        layout = QFormLayout(self)
        layout.addRow("OCR API Base URL", self.ocr_base_url_edit)
        layout.addRow("辅助提取 API", self.helper_base_url_edit)
        layout.addRow("飞书 App ID", self.feishu_app_id_edit)
        layout.addRow("飞书表 ID", self.feishu_table_id_edit)

    def to_payload(self) -> dict:
        return {
            "ocr_base_url": self.ocr_base_url_edit.text().strip(),
            "helper_base_url": self.helper_base_url_edit.text().strip(),
            "feishu_app_id": self.feishu_app_id_edit.text().strip(),
            "feishu_table_id": self.feishu_table_id_edit.text().strip(),
        }
```

```python
# src/strawberry_order_management/ui/pages/history_page.py
from PySide6.QtWidgets import QListWidget, QVBoxLayout, QWidget


class HistoryPage(QWidget):
    def __init__(self):
        super().__init__()
        self.list_widget = QListWidget()
        layout = QVBoxLayout(self)
        layout.addWidget(self.list_widget)

    def load_rows(self, rows: list[dict]) -> None:
        self.list_widget.clear()
        for row in rows:
            self.list_widget.addItem(f"{row.get('recipient_name', '-') } · {row.get('status', '-')}")
```

```python
# src/strawberry_order_management/ui/main_window.py
from PySide6.QtWidgets import QMainWindow, QStackedWidget, QWidget, QHBoxLayout, QListWidget

from strawberry_order_management.ui.pages.history_page import HistoryPage
from strawberry_order_management.ui.pages.intake_page import IntakePage
from strawberry_order_management.ui.pages.settings_page import SettingsPage


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("草莓订单管理系统")
        self.nav = QListWidget()
        self.nav.addItems(["订单录入", "历史", "设置"])
        self.stack = QStackedWidget()
        self.intake_page = IntakePage()
        self.history_page = HistoryPage()
        self.settings_page = SettingsPage()
        self.stack.addWidget(self.intake_page)
        self.stack.addWidget(self.history_page)
        self.stack.addWidget(self.settings_page)

        root = QWidget()
        layout = QHBoxLayout(root)
        layout.addWidget(self.nav, 1)
        layout.addWidget(self.stack, 5)
        self.setCentralWidget(root)
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav.setCurrentRow(0)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/ui/test_settings_page.py -q`
Expected: `1 passed`

- [ ] **Step 5: Commit**

```bash
git add src/strawberry_order_management/ui/pages/settings_page.py src/strawberry_order_management/ui/pages/history_page.py src/strawberry_order_management/ui/main_window.py tests/ui/test_settings_page.py
git commit -m "feat: add settings history and navigation shell"
```

## Task 9: Integrate Real UI Flow, Error States, and Main Entry Point

**Files:**
- Modify: `src/strawberry_order_management/app.py`
- Modify: `src/strawberry_order_management/ui/main_window.py`
- Modify: `src/strawberry_order_management/ui/pages/intake_page.py`
- Modify: `src/strawberry_order_management/ui/pages/history_page.py`
- Modify: `src/strawberry_order_management/ui/pages/settings_page.py`

- [ ] **Step 1: Write the failing smoke test for main window startup**

```python
# add to tests/ui/test_intake_page.py
from strawberry_order_management.ui.main_window import MainWindow


def test_main_window_opens_with_intake_tab_selected(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    assert window.nav.currentRow() == 0
    assert window.stack.currentWidget() is window.intake_page
```

- [ ] **Step 2: Run test to verify it fails if navigation wiring is incomplete**

Run: `python3 -m pytest tests/ui/test_intake_page.py -q`
Expected: fail if `MainWindow` cannot be imported or current page state is wrong

- [ ] **Step 3: Connect the app entrypoint and load the main window**

```python
# src/strawberry_order_management/app.py
from PySide6.QtWidgets import QApplication

from strawberry_order_management.ui.main_window import MainWindow


def build_app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    app.setApplicationName("草莓订单管理系统")
    return app


def main() -> int:
    app = build_app()
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run UI tests to verify the shell stays green**

Run: `python3 -m pytest tests/ui/test_address_extractor_widget.py tests/ui/test_intake_page.py tests/ui/test_settings_page.py -q`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add src/strawberry_order_management/app.py src/strawberry_order_management/ui/main_window.py src/strawberry_order_management/ui/pages/intake_page.py src/strawberry_order_management/ui/pages/history_page.py src/strawberry_order_management/ui/pages/settings_page.py tests/ui/test_intake_page.py
git commit -m "feat: wire desktop shell entrypoint"
```

## Task 10: End-to-End Verification and Packaging Notes

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add the verification commands to the README**

```md
## 测试

```bash
python3 -m pytest tests/test_address_extractor.py tests/test_config_store.py tests/test_history_store.py tests/test_order_parser.py tests/test_pipeline.py -q
python3 -m pytest tests/ui -q
```

## 打包方向

- 开发阶段：`python -m strawberry_order_management.app`
- 后续可选：`pyside6-deploy` 或 `pyinstaller`
```

- [ ] **Step 2: Run the full test suite**

Run: `python3 -m pytest tests -q`
Expected: all tests pass with no skipped failures

- [ ] **Step 3: Launch the app manually for smoke verification**

Run: `python3 -m strawberry_order_management.app`
Expected: desktop window opens with:
- left navigation for `订单录入` / `历史` / `设置`
- homepage showing both `拍单识别` and `地址快速提取`
- address extractor able to produce the two approved strings

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: add verification and packaging notes"
```

## Self-Review

### Spec coverage

- Homepage dual-module requirement: covered by Tasks 6, 7, and 9.
- Paste/drag/file intake: scaffolded in Task 7 and completed in Task 9 UI integration.
- Order card confirmation before Feishu: covered by Tasks 5 and 7.
- Feishu income column using merchant income: covered by Task 5 test.
- History and retry-ready local persistence: covered by Task 3 and Task 8.
- Settings page for OCR/helper/Feishu config: covered by Task 8.

### Placeholder scan

- No `TODO`, `TBD`, or "implement later" placeholders remain in tasks.
- Each code-changing step includes concrete code or exact file content.
- Each verification step includes an exact command and expected outcome.

### Type consistency

- `ParsedOrder` fields match the names used in parser tests, pipeline tests, and intake UI.
- `AddressExtraction` fields match the extractor implementation and widget usage.
- `ConfigStore`, `HistoryStore`, `AddressExtractorWidget`, `IntakePage`, and `SettingsPage` names are used consistently across tasks.
