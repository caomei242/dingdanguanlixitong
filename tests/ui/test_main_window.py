import time
from typing import Optional

from strawberry_order_management.config import ConfigStore
from strawberry_order_management.history import HistoryStore
from strawberry_order_management.models import ParsedOrder, ProcurementItem
from strawberry_order_management.ui.main_window import MainWindow


def _sample_order() -> ParsedOrder:
    return ParsedOrder(
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
        procurement_items=(
            ProcurementItem("", "1", ""),
            ProcurementItem("", "1", ""),
            ProcurementItem("", "1", ""),
        ),
    )


def _settings_payload() -> dict:
    return {
        "ocr_base_url": "https://api.minimaxi.com/v1",
        "ocr_api_key": "ocr_key",
        "helper_base_url": "https://api.minimaxi.com/v1",
        "helper_api_key": "helper_key",
        "feishu_app_id": "cli_app_123",
        "feishu_app_secret": "secret_456",
        "product_presets": [{"name": "澳洲婴儿水", "default_cost": "18.50"}],
        "shops": [
            {
                "name": "草莓店",
                "app_token": "app_token_strawberry",
                "table_id": "tbl_strawberry",
                "table_name": "草莓订单",
                "field_mapping": {
                    "备注": "备注",
                    "订单日期": "订单日期",
                    "下单时间": "下单时间",
                    "订单状态": "订单状态",
                    "收入": "收入金额",
                    "发货地址": "发货地址",
                    "价格": "",
                    "采购商品1": "采购商品1",
                    "采购数量1": "采购数量1",
                    "采购成本1": "采购成本1",
                    "采购商品2": "",
                    "采购数量2": "",
                    "采购成本2": "",
                    "采购商品3": "",
                    "采购数量3": "",
                    "采购成本3": "",
                },
            }
        ],
        "selected_shop_name": "草莓店",
    }


def _assert_rich_history_snapshot(
    record: dict,
    order: ParsedOrder,
    expected_sync_source: str,
    expected_status: str,
    expected_message: str,
    expected_procurement_items: Optional[dict[int, tuple[str, str, str]]] = None,
) -> None:
    assert record["shop_name"] == "草莓店"
    assert record["sync_source"] == expected_sync_source
    assert record["status"] == expected_status
    assert record["message"] == expected_message
    assert isinstance(record["created_at"], str) and record["created_at"]

    order_snapshot = record["order_snapshot"]
    assert order_snapshot["order_id"] == order.order_id
    assert order_snapshot["placed_at"] == order.placed_at
    assert order_snapshot["order_status"] == order.order_status
    assert order_snapshot["product_name"] == order.product_name
    assert order_snapshot["quantity"] == order.quantity
    assert order_snapshot["order_amount"] == order.order_amount
    assert order_snapshot["income_amount"] == order.income_amount
    assert order_snapshot["recipient_name"] == order.recipient_name
    assert order_snapshot["phone_number"] == order.phone_number
    assert order_snapshot["code"] == order.code
    assert order_snapshot["address"] == order.address
    assert order_snapshot["delivery_note"] == order.delivery_note
    if expected_procurement_items is not None:
        for index, (product_name, quantity, cost) in expected_procurement_items.items():
            assert order_snapshot["procurement_items"][index]["product_name"] == product_name
            assert order_snapshot["procurement_items"][index]["quantity"] == quantity
            assert order_snapshot["procurement_items"][index]["cost"] == cost

    address_snapshot = record["address_snapshot"]
    assert address_snapshot["output_one"].strip()
    assert address_snapshot["output_two"].strip()


def test_main_window_submits_order_to_selected_shop_sheet(qtbot, tmp_path, monkeypatch):
    config_store = ConfigStore(tmp_path / "config.json")
    history_store = HistoryStore(tmp_path / "history.json")
    config_store.save(_settings_payload())

    captured: dict[str, object] = {}

    class FakeFeishuClient:
        def __init__(self, app_id: str, app_secret: str, table_app_token: str, table_id: str):
            captured["init"] = (app_id, app_secret, table_app_token, table_id)

        def get_tenant_access_token(self) -> str:
            captured["token_called"] = True
            return "tenant_token_123"

        def create_record(self, access_token: str, fields: dict) -> dict:
            captured["create"] = (access_token, fields)
            return {"data": {"record_id": "rec_123"}}

    monkeypatch.setattr("strawberry_order_management.ui.main_window.FeishuClient", FakeFeishuClient)

    window = MainWindow(config_store=config_store, history_store=history_store)
    qtbot.addWidget(window)

    window.intake_page.show_order(_sample_order())
    window.intake_page.shop_selector.setCurrentText("草莓店")
    window.intake_page.order_card_widget.procurement_product_1_combo.setCurrentText("澳洲婴儿水")
    window.intake_page.order_card_widget.procurement_quantity_1_edit.setText("2")
    window.intake_page.order_card_widget.procurement_cost_1_edit.setText("19.00")

    window.intake_page.submit_button.click()

    qtbot.waitUntil(
        lambda: window.intake_page.capture_widget.status_label.text() == "已写入飞书：草莓店",
        timeout=3000,
    )

    assert captured["init"] == (
        "cli_app_123",
        "secret_456",
        "app_token_strawberry",
        "tbl_strawberry",
    )
    assert captured["token_called"] is True
    assert captured["create"][0] == "tenant_token_123"
    assert captured["create"][1]["收入金额"] == "162.00"
    assert captured["create"][1]["发货地址"].startswith("何女士 15781304332-3612")
    assert captured["create"][1]["采购商品1"] == "澳洲婴儿水"
    assert captured["create"][1]["采购数量1"] == "2"
    assert captured["create"][1]["采购成本1"] == "19.00"
    assert "价格" not in captured["create"][1]
    assert len(history_store.list_items()) == 1
    record = history_store.list_items()[0]
    _assert_rich_history_snapshot(
        record,
        _sample_order(),
        "确认写入飞书",
        "已写入飞书",
        "写入成功",
        {0: ("澳洲婴儿水", "2", "19.00")},
    )
    assert record["status"] == "已写入飞书"
    assert record["sync_source"] == "确认写入飞书"
    assert record["feishu_result"] == {"data": {"record_id": "rec_123"}}
    assert window.intake_page.capture_widget.status_label.text() == "已写入飞书：草莓店"
    assert any(
        item["name"] == "澳洲婴儿水" and item["default_cost"] == "19.00"
        for item in config_store.load()["product_presets"]
    )


def test_main_window_records_failure_when_feishu_submit_errors(qtbot, tmp_path, monkeypatch):
    config_store = ConfigStore(tmp_path / "config.json")
    history_store = HistoryStore(tmp_path / "history.json")
    config_store.save(_settings_payload())

    class FakeFeishuClient:
        def __init__(self, app_id: str, app_secret: str, table_app_token: str, table_id: str):
            pass

        def get_tenant_access_token(self) -> str:
            return "tenant_token_123"

        def create_record(self, access_token: str, fields: dict) -> dict:
            raise ValueError("飞书写入失败：无权限编辑该表")

    monkeypatch.setattr("strawberry_order_management.ui.main_window.FeishuClient", FakeFeishuClient)

    window = MainWindow(config_store=config_store, history_store=history_store)
    qtbot.addWidget(window)

    window.intake_page.show_order(_sample_order())
    window.intake_page.shop_selector.setCurrentText("草莓店")

    window.intake_page.submit_button.click()

    qtbot.waitUntil(
        lambda: window.intake_page.capture_widget.status_label.text() == "飞书写入失败：无权限编辑该表",
        timeout=3000,
    )

    assert len(history_store.list_items()) == 1
    record = history_store.list_items()[0]
    _assert_rich_history_snapshot(
        record,
        _sample_order(),
        "确认写入飞书",
        "写入失败",
        "飞书写入失败：无权限编辑该表",
    )
    assert record["status"] == "写入失败"
    assert record["sync_source"] == "确认写入飞书"
    assert record["message"] == "飞书写入失败：无权限编辑该表"
    assert window.intake_page.capture_widget.status_label.text() == "飞书写入失败：无权限编辑该表"


def test_main_window_submits_to_feishu_in_background(qtbot, tmp_path, monkeypatch):
    config_store = ConfigStore(tmp_path / "config.json")
    history_store = HistoryStore(tmp_path / "history.json")
    config_store.save(_settings_payload())

    class SlowFeishuClient:
        def __init__(self, app_id: str, app_secret: str, table_app_token: str, table_id: str):
            pass

        def get_tenant_access_token(self) -> str:
            time.sleep(0.05)
            return "tenant_token_123"

        def create_record(self, access_token: str, fields: dict) -> dict:
            time.sleep(0.05)
            return {"data": {"record_id": "rec_123"}}

    monkeypatch.setattr("strawberry_order_management.ui.main_window.FeishuClient", SlowFeishuClient)

    window = MainWindow(config_store=config_store, history_store=history_store)
    qtbot.addWidget(window)

    window.intake_page.show_order(_sample_order())
    window.intake_page.shop_selector.setCurrentText("草莓店")

    window.intake_page.submit_button.click()

    assert window.intake_page.capture_widget.status_label.text() == "写入飞书中..."
    assert len(history_store.list_items()) == 1
    pending_row = history_store.list_items()[0]
    assert pending_row["status"] == "写入中"
    assert pending_row["sync_source"] == "确认写入飞书"
    assert window.nav.isEnabled() is True
    assert window.intake_page.address_widget.isEnabled() is True

    qtbot.waitUntil(
        lambda: window.intake_page.capture_widget.status_label.text() == "已写入飞书：草莓店",
        timeout=3000,
    )
    qtbot.waitUntil(lambda: window._submit_thread is None, timeout=3000)
    assert len(history_store.list_items()) == 1
    completed_row = history_store.list_items()[0]
    assert completed_row["record_id"] == pending_row["record_id"]
    assert completed_row["status"] == "已写入飞书"
    assert completed_row["message"] == "写入成功"
    assert completed_row["feishu_result"] == {"data": {"record_id": "rec_123"}}


def test_main_window_persists_submit_failure_before_worker_start(qtbot, tmp_path, monkeypatch):
    config_store = ConfigStore(tmp_path / "config.json")
    history_store = HistoryStore(tmp_path / "history.json")
    config_store.save(_settings_payload())

    window = MainWindow(config_store=config_store, history_store=history_store)
    qtbot.addWidget(window)

    window.intake_page.show_order(_sample_order())
    window.intake_page.shop_selector.setCurrentText("草莓店")

    start_called = {"value": False}

    def fake_start_submit_job(task: dict) -> None:
        start_called["value"] = True

    def fake_build_task(payload: dict) -> dict:
        raise ValueError("店铺“草莓店”缺少：Table ID")

    monkeypatch.setattr(window, "_start_submit_job", fake_start_submit_job)
    monkeypatch.setattr(window, "_build_feishu_submission_task", fake_build_task)

    window.intake_page.submit_button.click()

    assert start_called["value"] is False
    assert window.intake_page.capture_widget.status_label.text() == "店铺“草莓店”缺少：Table ID"
    assert len(history_store.list_items()) == 1
    record = history_store.list_items()[0]
    assert record["status"] == "写入失败"
    assert record["sync_source"] == "确认写入飞书"
    assert record["message"] == "店铺“草莓店”缺少：Table ID"
    assert record["order_snapshot"]["order_id"] == _sample_order().order_id


def test_main_window_ignores_missing_history_row_during_async_completion(qtbot, tmp_path):
    config_store = ConfigStore(tmp_path / "config.json")
    history_store = HistoryStore(tmp_path / "history.json")
    config_store.save(_settings_payload())

    window = MainWindow(config_store=config_store, history_store=history_store)
    qtbot.addWidget(window)

    window.intake_page.show_order(_sample_order())
    window.intake_page.shop_selector.setCurrentText("草莓店")

    snapshot = window._build_history_snapshot(
        {"shop_name": "草莓店", "order": _sample_order()},
        "确认写入飞书",
        "写入中",
    )
    saved_row = history_store.append(snapshot)
    history_store.delete(saved_row["record_id"])

    window._handle_submit_success(
        {
            "payload": {"shop_name": "草莓店", "order": _sample_order()},
            "shop_name": "草莓店",
            "response": {"data": {"record_id": "rec_123"}},
            "history_record_id": saved_row["record_id"],
        }
    )

    assert history_store.list_items() == []
    assert window.intake_page.capture_widget.status_label.text() == "已写入飞书：草莓店"


def test_main_window_can_save_manual_product_into_global_library(qtbot, tmp_path):
    config_store = ConfigStore(tmp_path / "config.json")
    history_store = HistoryStore(tmp_path / "history.json")
    config_store.save(_settings_payload())

    window = MainWindow(config_store=config_store, history_store=history_store)
    qtbot.addWidget(window)
    window.intake_page.show_order(_sample_order())

    window.intake_page.order_card_widget.procurement_product_1_combo.setEditText("临时采购品")
    window.intake_page.order_card_widget.procurement_cost_1_edit.setText("11.80")
    window.intake_page.order_card_widget.procurement_save_1_button.click()

    saved_payload = config_store.load()
    assert any(
        item["name"] == "临时采购品" and item["default_cost"] == "11.80"
        for item in saved_payload["product_presets"]
    )
    assert window.intake_page.capture_widget.status_label.text() == "已加入商品库：临时采购品"


def test_main_window_auto_persists_manual_products_when_saving_history(qtbot, tmp_path):
    config_store = ConfigStore(tmp_path / "config.json")
    history_store = HistoryStore(tmp_path / "history.json")
    config_store.save(_settings_payload())

    window = MainWindow(config_store=config_store, history_store=history_store)
    qtbot.addWidget(window)

    window.intake_page.show_order(_sample_order())
    window.intake_page.shop_selector.setCurrentText("草莓店")
    window.intake_page.order_card_widget.procurement_product_2_combo.setEditText("补录商品")
    window.intake_page.order_card_widget.procurement_cost_2_edit.setText("7.50")

    window.intake_page.save_history_button.click()

    assert len(history_store.list_items()) == 1
    record = history_store.list_items()[0]
    _assert_rich_history_snapshot(
        record,
        _sample_order(),
        "仅存历史",
        "仅存历史",
        "",
        {1: ("补录商品", "1", "7.50")},
    )
    assert record["status"] == "仅存历史"
    assert record["sync_source"] == "仅存历史"
    assert record["message"] == ""
    assert any(
        item["name"] == "补录商品" and item["default_cost"] == "7.50"
        for item in config_store.load()["product_presets"]
    )
