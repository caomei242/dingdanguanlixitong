from PySide6.QtWidgets import QFrame, QScrollArea, QTabWidget

from strawberry_order_management.ui.main_window import MainWindow
from strawberry_order_management.ui.pages.history_page import HistoryPage
from strawberry_order_management.ui.pages.settings_page import SettingsPage, _preferred_mcp_command
from strawberry_order_management.models import ParsedOrder


def test_settings_page_load_payload_preserves_global_product_library_and_total_table_mapping(qtbot):
    page = SettingsPage()
    qtbot.addWidget(page)

    page.load_payload(
        {
            "global_product_library": [
                {"name": "澳大利亚进口婴儿水", "default_cost": "12.50"},
                {"name": "草莓", "default_cost": "8.20"},
            ],
            "feishu_table_wiki_url": "https://my.feishu.cn/wiki/QTXMwCDpQi9n6VkfDxJc5mNTnjh?table=tbl_total",
            "feishu_table_app_token": "app_token_total",
            "feishu_table_id": "tbl_total",
            "feishu_table_name": "订单总表",
            "feishu_field_mapping": {
                "店铺": "店铺列",
                "备注": "备注列",
                "订单日期": "订单日期列",
            },
            "shops": [
                {
                    "name": "乐宝零食店",
                    "wiki_url": "https://my.feishu.cn/wiki/QTXMwCDpQi9n6VkfDxJc5mNTnjh?table=tbl_xxx",
                    "app_token": "app_token_1",
                    "table_id": "tbl_xxx",
                    "table_name": "草莓订单表",
                    "field_mapping": {
                        "备注": "备注列",
                        "订单日期": "订单日期列",
                        "下单时间": "下单时间列",
                        "订单状态": "订单状态列",
                        "收入": "收入列",
                        "发货地址": "发货地址列",
                        "价格": "价格列",
                        "采购商品1": "采购商品1列",
                        "采购商品2": "采购商品2列",
                        "采购商品3": "采购商品3列",
                        "采购数量1": "采购数量1列",
                        "采购数量2": "采购数量2列",
                        "采购数量3": "采购数量3列",
                        "采购成本1": "采购成本1列",
                        "采购成本2": "采购成本2列",
                        "采购成本3": "采购成本3列",
                    },
                }
            ],
            "selected_shop_name": "乐宝零食店",
        }
    )

    assert page.product_selector.count() == 2
    assert page.product_name_edit.text() == "澳大利亚进口婴儿水"
    assert page.product_default_cost_edit.text() == "12.50"
    assert page.shop_selector.currentText() == "乐宝零食店"
    assert page.shop_wiki_url_edit.text() == "https://my.feishu.cn/wiki/QTXMwCDpQi9n6VkfDxJc5mNTnjh?table=tbl_total"
    assert page.shop_app_token_edit.text() == "app_token_total"
    assert page.shop_table_id_edit.text() == "tbl_total"
    assert page.shop_table_name_edit.text() == "订单总表"
    assert page.shop_mapping_edits["shop_name"].text() == "店铺列"
    assert page.shop_mapping_edits["platform"].text() == "平台"
    assert page.shop_mapping_edits["remark"].text() == "备注列"
    assert page.shop_mapping_edits["order_date"].text() == "订单日期列"
    assert page.shop_mapping_edits["order_time"].text() == "下单时间"
    assert page.shop_mapping_edits["order_status"].text() == "订单状态"
    assert page.shop_mapping_edits["income"].text() == "收入"
    assert page.shop_mapping_edits["shipping_address"].text() == "发货地址"
    assert page.shop_mapping_edits["price"].text() == ""
    assert page.shop_mapping_edits["purchase_item_1"].text() == "采购商品1"
    assert page.shop_mapping_edits["purchase_item_2"].text() == "采购商品2"
    assert page.shop_mapping_edits["purchase_item_3"].text() == "采购商品3"
    assert page.shop_mapping_edits["purchase_quantity_1"].text() == "采购数量1"
    assert page.shop_mapping_edits["purchase_quantity_2"].text() == "采购数量2"
    assert page.shop_mapping_edits["purchase_quantity_3"].text() == "采购数量3"
    assert page.shop_mapping_edits["purchase_cost_1"].text() == "采购成本1"
    assert page.shop_mapping_edits["purchase_cost_2"].text() == "采购成本2"
    assert page.shop_mapping_edits["purchase_cost_3"].text() == "采购成本3"


def test_settings_page_upgrades_legacy_uvx_command_to_local_mcp_binary(qtbot, monkeypatch):
    monkeypatch.setattr(
        "strawberry_order_management.ui.pages.settings_page._preferred_mcp_command",
        lambda: "/tmp/minimax-coding-plan-mcp",
    )
    page = SettingsPage()
    qtbot.addWidget(page)

    page.load_payload({"ocr_mcp_command": "uvx minimax-coding-plan-mcp -y"})

    assert page.ocr_mcp_command_edit.text() == "/tmp/minimax-coding-plan-mcp"


def test_settings_page_to_payload_persists_global_product_library_and_total_table_mapping(qtbot):
    page = SettingsPage()
    qtbot.addWidget(page)

    page.product_name_edit.setText("澳大利亚进口婴儿水")
    page.product_default_cost_edit.setText("12.50")
    page.save_product_button.click()
    page.product_name_edit.setText("草莓")
    page.product_default_cost_edit.setText("8.20")
    page.save_product_button.click()

    page.shop_wiki_url_edit.setText("https://my.feishu.cn/wiki/QTXMwCDpQi9n6VkfDxJc5mNTnjh?table=tbl_total")
    page.shop_app_token_edit.setText("app_token_total")
    page.shop_table_id_edit.setText("tbl_total")
    page.shop_table_name_edit.setText("订单总表")
    page.shop_mapping_edits["shop_name"].setText("店铺列")
    page.shop_mapping_edits["platform"].setText("平台列")
    page.shop_name_edit.setText("乐宝零食店")
    page.shop_mapping_edits["remark"].setText("备注列")
    page.shop_mapping_edits["order_date"].setText("订单日期列")
    page.shop_mapping_edits["order_time"].setText("下单时间列")
    page.shop_mapping_edits["order_status"].setText("订单状态列")
    page.shop_mapping_edits["income"].setText("收入列")
    page.shop_mapping_edits["shipping_address"].setText("发货地址列")
    page.shop_mapping_edits["price"].setText("价格列")
    page.shop_mapping_edits["purchase_item_1"].setText("采购商品1列")
    page.shop_mapping_edits["purchase_item_2"].setText("采购商品2列")
    page.shop_mapping_edits["purchase_item_3"].setText("采购商品3列")
    page.shop_mapping_edits["purchase_quantity_1"].setText("采购数量1列")
    page.shop_mapping_edits["purchase_quantity_2"].setText("采购数量2列")
    page.shop_mapping_edits["purchase_quantity_3"].setText("采购数量3列")
    page.shop_mapping_edits["purchase_cost_1"].setText("采购成本1列")
    page.shop_mapping_edits["purchase_cost_2"].setText("采购成本2列")
    page.shop_mapping_edits["purchase_cost_3"].setText("采购成本3列")
    page.save_shop_button.click()

    payload = page.to_payload()

    assert payload["global_product_library"] == [
        {"name": "澳大利亚进口婴儿水", "default_cost": "12.50"},
        {"name": "草莓", "default_cost": "8.20"},
    ]
    assert payload["feishu_table_wiki_url"] == "https://my.feishu.cn/wiki/QTXMwCDpQi9n6VkfDxJc5mNTnjh?table=tbl_total"
    assert payload["feishu_table_app_token"] == "app_token_total"
    assert payload["feishu_table_id"] == "tbl_total"
    assert payload["feishu_table_name"] == "订单总表"
    assert payload["feishu_field_mapping"]["店铺"] == "店铺列"
    assert payload["feishu_field_mapping"]["平台"] == "平台列"
    assert [shop["name"] for shop in payload["shops"]] == [
        "乐宝零食店",
        "欢宝零食店",
        "灵宝零食店",
        "君宝零食店",
        "珍宝零食店",
        "悦宝零食店",
    ]


def test_settings_page_collects_api_configuration(qtbot):
    page = SettingsPage()
    qtbot.addWidget(page)

    page.ocr_use_mcp_checkbox.setChecked(True)
    page.ocr_mcp_command_edit.setText("uvx minimax-coding-plan-mcp -y")
    page.ocr_base_url_edit.setText("https://ocr.example.com")
    page.ocr_api_key_edit.setText("ocr-key")
    page.helper_base_url_edit.setText("https://helper.example.com")
    page.helper_api_key_edit.setText("helper-key")
    page.feishu_app_id_edit.setText("cli_xxx")
    page.feishu_app_secret_edit.setText("secret_xxx")
    page.shop_wiki_url_edit.setText(
        "https://my.feishu.cn/wiki/QTXMwCDpQi9n6VkfDxJc5mNTnjh?table=tbl_xxx"
    )
    page.shop_app_token_edit.setText("app_token_1")
    page.shop_table_id_edit.setText("tbl_xxx")
    page.shop_table_name_edit.setText("订单总表")
    page.shop_name_edit.setText("乐宝零食店")
    page.save_shop_button.click()

    payload = page.to_payload()

    assert payload["ocr_use_mcp"] is True
    assert payload["ocr_mcp_command"] == _preferred_mcp_command()
    assert payload["ocr_base_url"] == "https://ocr.example.com"
    assert payload["ocr_api_key"] == "ocr-key"
    assert payload["helper_base_url"] == "https://helper.example.com"
    assert payload["helper_api_key"] == "helper-key"
    assert payload["feishu_app_id"] == "cli_xxx"
    assert payload["feishu_app_secret"] == "secret_xxx"
    assert payload["feishu_table_wiki_url"] == "https://my.feishu.cn/wiki/QTXMwCDpQi9n6VkfDxJc5mNTnjh?table=tbl_xxx"
    assert payload["feishu_table_app_token"] == "app_token_1"
    assert payload["feishu_table_id"] == "tbl_xxx"
    assert payload["feishu_table_name"] == "订单总表"
    assert [shop["name"] for shop in payload["shops"]] == [
        "乐宝零食店",
        "欢宝零食店",
        "灵宝零食店",
        "君宝零食店",
        "珍宝零食店",
        "悦宝零食店",
    ]
    assert payload["selected_shop_name"] == "乐宝零食店"


def test_settings_page_load_payload_and_save_requested(qtbot):
    page = SettingsPage()
    qtbot.addWidget(page)

    payload = {
        "ocr_use_mcp": True,
        "ocr_mcp_command": " uvx minimax-coding-plan-mcp -y ",
        "ocr_base_url": " https://ocr.example.com ",
        "ocr_api_key": " ocr-key ",
        "helper_base_url": " https://helper.example.com ",
        "helper_api_key": " helper-key ",
        "feishu_app_id": " cli_xxx ",
        "feishu_app_secret": " secret_xxx ",
        "feishu_table_wiki_url": " https://my.feishu.cn/wiki/QTXMwCDpQi9n6VkfDxJc5mNTnjh?table=tbl_xxx ",
        "feishu_table_app_token": " app_token_1 ",
        "feishu_table_id": " tbl_xxx ",
        "feishu_table_name": " 订单总表 ",
        "shops": [{"name": "乐宝零食店"}],
        "selected_shop_name": "乐宝零食店",
    }

    emitted = []
    page.save_requested.connect(emitted.append)

    page.load_payload(payload)
    page.save_button.click()

    assert page.ocr_use_mcp_checkbox.isChecked() is True
    assert page.ocr_mcp_command_edit.text() == _preferred_mcp_command()
    assert page.ocr_base_url_edit.text() == "https://ocr.example.com"
    assert page.ocr_api_key_edit.text() == "ocr-key"
    assert page.helper_base_url_edit.text() == "https://helper.example.com"
    assert page.helper_api_key_edit.text() == "helper-key"
    assert page.feishu_app_id_edit.text() == "cli_xxx"
    assert page.feishu_app_secret_edit.text() == "secret_xxx"
    assert page.shop_selector.count() == 6
    assert page.shop_selector.currentText() == "乐宝零食店"
    assert page.shop_wiki_url_edit.text() == "https://my.feishu.cn/wiki/QTXMwCDpQi9n6VkfDxJc5mNTnjh?table=tbl_xxx"
    assert page.shop_app_token_edit.text() == "app_token_1"
    assert page.shop_table_id_edit.text() == "tbl_xxx"
    assert page.shop_table_name_edit.text() == "订单总表"
    assert emitted == [page.to_payload()]


def test_settings_page_resolves_total_table_tokens_from_wiki_url(qtbot):
    captured = []

    def resolver(wiki_url: str):
        captured.append(wiki_url)
        return {
            "app_token": "basc1234567890",
            "table_id": "tblWZDrx4gqXpc5M",
        }

    page = SettingsPage(on_resolve_shop_link=resolver)
    qtbot.addWidget(page)

    page.shop_wiki_url_edit.setText(
        "https://my.feishu.cn/wiki/QTXMwCDpQi9n6VkfDxJc5mNTnjh?table=tblWZDrx4gqXpc5M&view=vew5lZdMQj"
    )
    page.shop_name_edit.setText("乐宝零食店")
    page.shop_mapping_edits["remark"].setText("备注列")
    page.shop_mapping_edits["order_date"].setText("订单日期列")
    page.save_shop_button.click()

    page.save_button.click()

    assert captured == [
        "https://my.feishu.cn/wiki/QTXMwCDpQi9n6VkfDxJc5mNTnjh?table=tblWZDrx4gqXpc5M&view=vew5lZdMQj"
    ]
    assert page.shop_app_token_edit.text() == "basc1234567890"
    assert page.shop_table_id_edit.text() == "tblWZDrx4gqXpc5M"
    assert page.status_label.text() == "已从飞书链接解析表格信息"
    assert page.to_payload()["feishu_table_app_token"] == "basc1234567890"
    assert page.to_payload()["feishu_table_id"] == "tblWZDrx4gqXpc5M"
    assert [shop["name"] for shop in page.to_payload()["shops"]] == [
        "乐宝零食店",
        "欢宝零食店",
        "灵宝零食店",
        "君宝零食店",
        "珍宝零食店",
        "悦宝零食店",
    ]


def test_settings_page_shows_error_when_wiki_resolution_fails(qtbot):
    def resolver(wiki_url: str):
        raise ValueError("请先填写飞书 App ID 和 App Secret")

    page = SettingsPage(on_resolve_shop_link=resolver)
    qtbot.addWidget(page)

    page.shop_wiki_url_edit.setText(
        "https://my.feishu.cn/wiki/QTXMwCDpQi9n6VkfDxJc5mNTnjh?table=tblWZDrx4gqXpc5M&view=vew5lZdMQj"
    )
    page.shop_name_edit.setText("乐宝零食店")

    page.save_button.click()

    assert page.status_label.text() == "请先填写飞书 App ID 和 App Secret"
    assert page.shop_selector.count() == 6
    assert page.shop_selector.currentText() == "乐宝零食店"


def test_history_page_load_rows_shows_summary_and_items(qtbot):
    page = HistoryPage()
    qtbot.addWidget(page)

    page.load_rows(
        [
            {
                "shop_name": "乐宝零食店",
                "recipient_name": "何女士",
                "status": "已写入",
                "order_id": "6952003434324366473",
            },
            {
                "shop_name": "欢宝零食店",
                "recipient_name": "彭柏棋",
                "status": "待重试",
                "order_id": "6952003434324366474",
            },
        ]
    )

    assert page.summary_label.text() == "共 2 条记录"
    assert page.list_widget.count() == 2
    assert page.list_widget.item(0).text() == "乐宝零食店 · 何女士 · 已写入 · 6952003434324366473"
    assert page.list_widget.item(1).text() == "欢宝零食店 · 彭柏棋 · 待重试 · 6952003434324366474"


def test_history_page_renders_none_as_dash(qtbot):
    page = HistoryPage()
    qtbot.addWidget(page)

    page.load_rows(
        [
            {
                "shop_name": None,
                "recipient_name": None,
                "status": None,
                "order_id": None,
            }
        ]
    )

    assert page.list_widget.count() == 1
    assert page.list_widget.item(0).text() == "- · - · - · -"


def test_history_page_wraps_content_in_scroll_area(qtbot):
    page = HistoryPage()
    qtbot.addWidget(page)

    scroll_area = page.findChild(QScrollArea)

    assert scroll_area is not None
    assert scroll_area.widgetResizable() is True
    assert scroll_area.frameShape() == QFrame.Shape.NoFrame
    assert scroll_area.widget().objectName() == "PageContent"


def test_settings_page_wraps_content_in_scroll_area(qtbot):
    page = SettingsPage()
    qtbot.addWidget(page)

    scroll_area = page.findChild(QScrollArea)

    assert scroll_area is not None
    assert scroll_area.widgetResizable() is True
    assert scroll_area.frameShape() == QFrame.Shape.NoFrame
    assert scroll_area.widget().objectName() == "PageContent"


def test_settings_page_groups_forms_into_tabs(qtbot):
    page = SettingsPage()
    qtbot.addWidget(page)

    tabs = page.findChild(QTabWidget)

    assert tabs is not None
    assert tabs.count() == 3
    assert [tabs.tabText(index) for index in range(tabs.count())] == [
        "接口配置",
        "商品库",
        "店铺映射",
    ]


def test_settings_page_prefills_recommended_mapping_for_new_shop(qtbot):
    page = SettingsPage()
    qtbot.addWidget(page)

    page._handle_add_shop()

    assert page.shop_mapping_edits["shop_name"].text() == "店铺"
    assert page.shop_mapping_edits["platform"].text() == "平台"
    assert page.shop_mapping_edits["order_id"].text() == "订单编号"
    assert page.shop_mapping_edits["remark"].text() == "备注"
    assert page.shop_mapping_edits["order_date"].text() == "订单日期"
    assert page.shop_mapping_edits["order_time"].text() == "下单时间"
    assert page.shop_mapping_edits["order_status"].text() == "订单状态"
    assert page.shop_mapping_edits["product_name"].text() == "商品名称"
    assert page.shop_mapping_edits["quantity"].text() == "数量"
    assert page.shop_mapping_edits["recipient_name"].text() == "收件人"
    assert page.shop_mapping_edits["phone_number"].text() == "手机号"
    assert page.shop_mapping_edits["code"].text() == "编号"
    assert page.shop_mapping_edits["income"].text() == "收入"
    assert page.shop_mapping_edits["shipping_address"].text() == "发货地址"
    assert page.shop_mapping_edits["price"].text() == ""
    assert page.shop_mapping_edits["sync_source"].text() == "同步方式"
    assert page.shop_mapping_edits["sync_status"].text() == "同步状态"
    assert page.shop_mapping_edits["sync_message"].text() == "同步说明"
    assert page.shop_mapping_edits["recorded_at"].text() == "录入时间"
    assert page.shop_mapping_edits["purchase_item_1"].text() == "采购商品1"
    assert page.shop_mapping_edits["purchase_quantity_1"].text() == "采购数量1"
    assert page.shop_mapping_edits["purchase_cost_1"].text() == "采购成本1"
    assert page.shop_mapping_edits["purchase_item_2"].text() == "采购商品2"
    assert page.shop_mapping_edits["purchase_quantity_2"].text() == "采购数量2"
    assert page.shop_mapping_edits["purchase_cost_2"].text() == "采购成本2"
    assert page.shop_mapping_edits["purchase_item_3"].text() == "采购商品3"
    assert page.shop_mapping_edits["purchase_quantity_3"].text() == "采购数量3"
    assert page.shop_mapping_edits["purchase_cost_3"].text() == "采购成本3"


def test_settings_page_checks_total_table_fields_and_highlights_missing(qtbot):
    def inspect_fields(payload: dict):
        assert payload["feishu_table_app_token"] == "app_token_total"
        return {"店铺", "订单编号", "收入"}

    page = SettingsPage(on_inspect_table_fields=inspect_fields)
    qtbot.addWidget(page)
    page.shop_app_token_edit.setText("app_token_total")
    page.shop_table_id_edit.setText("tbl_total")
    page.check_table_fields_button.click()

    assert "总表缺少字段" in page.status_label.text()
    assert "平台" in page.status_label.text()
    assert "发货地址" in page.status_label.text()
    assert "border: 1px solid #ff6b6b" in page.shop_mapping_edits["platform"].styleSheet()
    assert page.shop_mapping_edits["shop_name"].styleSheet() == ""


def test_settings_page_uses_default_shop_presets_and_default_selection(qtbot):
    page = SettingsPage()
    qtbot.addWidget(page)

    payload = page.to_payload()

    assert [shop["name"] for shop in payload["shops"]] == [
        "乐宝零食店",
        "欢宝零食店",
        "灵宝零食店",
        "君宝零食店",
        "珍宝零食店",
        "悦宝零食店",
    ]
    assert payload["selected_shop_name"] == "乐宝零食店"
    assert "草莓店" not in [shop["name"] for shop in payload["shops"]]


def test_settings_page_persists_custom_cost_labels(qtbot):
    page = SettingsPage()
    qtbot.addWidget(page)

    page.custom_cost_label_edits[0].setText("包装费")
    page.custom_cost_label_edits[1].setText("赠品")

    payload = page.to_payload()

    assert payload["custom_cost_labels"] == ["包装费", "赠品", ""]


def test_settings_page_can_filter_to_enabled_mappings(qtbot):
    page = SettingsPage()
    qtbot.addWidget(page)

    page.mapping_edits["平台"].setText("平台")
    page.mapping_edits["订单编号"].clear()
    page.show_enabled_only_checkbox.setChecked(True)

    assert page.mapping_row_widgets["订单编号"].isHidden()
    assert not page.mapping_row_widgets["平台"].isHidden()


def test_settings_page_custom_cost_labels_update_mapping_row_text_and_defaults(qtbot):
    page = SettingsPage()
    qtbot.addWidget(page)

    page.custom_cost_label_edits[0].setText("包装费")

    assert page.mapping_row_labels["自定义字段1"].text() == "包装费 映射"
    assert page.mapping_edits["自定义字段1"].text() == "包装费"


def test_settings_page_custom_cost_label_does_not_override_manual_mapping(qtbot):
    page = SettingsPage()
    qtbot.addWidget(page)

    page.mapping_edits["自定义字段1"].setText("费用A")
    page.custom_cost_label_edits[0].setText("包装费")

    assert page.mapping_row_labels["自定义字段1"].text() == "包装费 映射"
    assert page.mapping_edits["自定义字段1"].text() == "费用A"


def test_main_window_navigates_between_three_pages(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)

    assert window.nav.currentRow() == 0
    assert window.stack.currentWidget() is window.intake_page

    window.nav.setCurrentRow(1)
    assert window.stack.currentWidget() is window.history_page

    window.nav.setCurrentRow(2)
    assert window.stack.currentWidget() is window.settings_page

    window.nav.setCurrentRow(0)
    assert window.stack.currentWidget() is window.intake_page


def test_main_window_forwards_settings_save_requests(qtbot):
    saved = []
    window = MainWindow(on_settings_save=saved.append)
    qtbot.addWidget(window)

    window.settings_page.ocr_base_url_edit.setText("https://ocr.example.com")
    window.settings_page.save_button.click()

    assert saved == [window.settings_page.to_payload()]


class MemoryConfigStore:
    def __init__(self, initial_payload=None):
        self.initial_payload = initial_payload or {}
        self.saved_payloads = []

    def load(self):
        return self.initial_payload

    def save(self, payload):
        self.saved_payloads.append(payload)


def test_main_window_loads_initial_settings_from_config_store(qtbot):
    store = MemoryConfigStore(
        {
            "helper_base_url": "https://api.minimaxi.com/v1",
            "helper_api_key": "minimax-secret",
            "shops": [
                {
                    "name": "乐宝零食店",
                    "app_token": "app_token_1",
                    "table_id": "tbl_1",
                    "table_name": "草莓订单表",
                }
            ],
            "selected_shop_name": "乐宝零食店",
        }
    )
    window = MainWindow(config_store=store)
    qtbot.addWidget(window)

    assert window.settings_page.helper_base_url_edit.text() == "https://api.minimaxi.com/v1"
    assert window.settings_page.helper_api_key_edit.text() == "minimax-secret"
    assert [window.intake_page.shop_selector.itemText(index) for index in range(window.intake_page.shop_selector.count())] == [
        "乐宝零食店",
        "欢宝零食店",
        "灵宝零食店",
        "君宝零食店",
        "珍宝零食店",
        "悦宝零食店",
    ]
    assert window.intake_page.shop_selector.currentText() == "乐宝零食店"


def test_main_window_uses_default_shop_presets_when_config_is_empty(qtbot):
    window = MainWindow(config_store=MemoryConfigStore({}))
    qtbot.addWidget(window)

    assert [window.intake_page.shop_selector.itemText(index) for index in range(window.intake_page.shop_selector.count())] == [
        "乐宝零食店",
        "欢宝零食店",
        "灵宝零食店",
        "君宝零食店",
        "珍宝零食店",
        "悦宝零食店",
    ]
    assert window.intake_page.shop_selector.currentText() == "乐宝零食店"


def test_main_window_saves_settings_into_config_store(qtbot):
    store = MemoryConfigStore()
    window = MainWindow(config_store=store)
    qtbot.addWidget(window)

    window.settings_page.helper_base_url_edit.setText("https://api.minimaxi.com/v1")
    window.settings_page.helper_api_key_edit.setText("minimax-secret")
    window.settings_page.save_button.click()

    assert store.saved_payloads == [window.settings_page.to_payload()]


def test_main_window_uses_current_settings_to_process_images(qtbot):
    captured_payloads = []

    def pipeline_factory(payload):
        captured_payloads.append(payload)

        class StubPipeline:
            def extract_order(self, image_bytes):
                assert image_bytes == b"image-bytes"
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
                )

        return StubPipeline()

    window = MainWindow(
        config_store=MemoryConfigStore(
            {
                "ocr_use_mcp": True,
                "ocr_mcp_command": "uvx minimax-coding-plan-mcp -y",
                "ocr_base_url": "https://api.minimaxi.com/v1",
                "ocr_api_key": "ocr-secret",
                "helper_base_url": "https://api.minimaxi.com/v1",
                "helper_api_key": "helper-secret",
                "shops": [
                    {
                        "name": "乐宝零食店",
                        "app_token": "app_token_1",
                        "table_id": "tbl_1",
                        "table_name": "草莓订单表",
                    }
                ],
                "selected_shop_name": "乐宝零食店",
            }
        ),
        order_pipeline_factory=pipeline_factory,
    )
    qtbot.addWidget(window)
    window.intake_page._use_background_thread = False

    window.intake_page.process_image_bytes(b"image-bytes", "剪贴板截图")

    assert captured_payloads == [window.settings_page.to_payload()]
    assert window.intake_page.order_card_widget.order_id_edit.text() == "6952003434324366473"


def test_main_window_uses_default_mcp_command_when_enabled(qtbot, monkeypatch):
    monkeypatch.setattr(
        "strawberry_order_management.ui.pages.settings_page._preferred_mcp_command",
        lambda: "/tmp/minimax-coding-plan-mcp",
    )
    captured_payloads = []

    def pipeline_factory(payload):
        captured_payloads.append(payload)

        class StubPipeline:
            def extract_order(self, image_bytes):
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
                )

        return StubPipeline()

    window = MainWindow(
        config_store=MemoryConfigStore(
            {
                "ocr_use_mcp": True,
                "ocr_mcp_command": "",
                "ocr_base_url": "https://api.minimaxi.com/v1",
                "ocr_api_key": "ocr-secret",
                "helper_base_url": "https://api.minimaxi.com/v1",
                "helper_api_key": "helper-secret",
            }
        ),
        order_pipeline_factory=pipeline_factory,
    )
    qtbot.addWidget(window)
    window.intake_page._use_background_thread = False

    window.intake_page.process_image_bytes(b"image-bytes", "剪贴板截图")

    assert captured_payloads[0]["ocr_mcp_command"] == "/tmp/minimax-coding-plan-mcp"
