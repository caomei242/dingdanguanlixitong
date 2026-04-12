import time

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
    assert history_store.list_items()[0]["status"] == "已写入飞书"
    assert history_store.list_items()[0]["shop_name"] == "草莓店"
    assert window.intake_page.capture_widget.status_label.text() == "已写入飞书：草莓店"


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

    assert history_store.list_items()[0]["status"] == "写入失败"
    assert history_store.list_items()[0]["shop_name"] == "草莓店"
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
    assert window.nav.isEnabled() is True
    assert window.intake_page.address_widget.isEnabled() is True

    qtbot.waitUntil(
        lambda: window.intake_page.capture_widget.status_label.text() == "已写入飞书：草莓店",
        timeout=3000,
    )
    qtbot.waitUntil(lambda: window._submit_thread is None, timeout=3000)
    assert history_store.list_items()[0]["status"] == "已写入飞书"
