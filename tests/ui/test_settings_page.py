from PySide6.QtWidgets import QFrame, QScrollArea

from strawberry_order_management.ui.main_window import MainWindow
from strawberry_order_management.ui.pages.history_page import HistoryPage
from strawberry_order_management.ui.pages.settings_page import SettingsPage
from strawberry_order_management.models import ParsedOrder


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
    page.shop_name_edit.setText("草莓店")
    page.shop_wiki_url_edit.setText(
        "https://my.feishu.cn/wiki/QTXMwCDpQi9n6VkfDxJc5mNTnjh?table=tbl_xxx"
    )
    page.shop_app_token_edit.setText("app_token_1")
    page.shop_table_id_edit.setText("tbl_xxx")
    page.shop_table_name_edit.setText("草莓订单表")
    page.save_shop_button.click()

    payload = page.to_payload()

    assert payload["ocr_use_mcp"] is True
    assert payload["ocr_mcp_command"] == "uvx minimax-coding-plan-mcp -y"
    assert payload["ocr_base_url"] == "https://ocr.example.com"
    assert payload["ocr_api_key"] == "ocr-key"
    assert payload["helper_base_url"] == "https://helper.example.com"
    assert payload["helper_api_key"] == "helper-key"
    assert payload["feishu_app_id"] == "cli_xxx"
    assert payload["feishu_app_secret"] == "secret_xxx"
    assert payload["shops"] == [
        {
            "name": "草莓店",
            "wiki_url": "https://my.feishu.cn/wiki/QTXMwCDpQi9n6VkfDxJc5mNTnjh?table=tbl_xxx",
            "app_token": "app_token_1",
            "table_id": "tbl_xxx",
            "table_name": "草莓订单表",
        }
    ]
    assert payload["selected_shop_name"] == "草莓店"


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
        "shops": [
            {
                "name": "草莓店",
                "wiki_url": " https://my.feishu.cn/wiki/QTXMwCDpQi9n6VkfDxJc5mNTnjh?table=tbl_xxx ",
                "app_token": " app_token_1 ",
                "table_id": " tbl_xxx ",
                "table_name": " 草莓订单表 ",
            }
        ],
        "selected_shop_name": "草莓店",
    }

    emitted = []
    page.save_requested.connect(emitted.append)

    page.load_payload(payload)
    page.save_button.click()

    assert page.ocr_use_mcp_checkbox.isChecked() is True
    assert page.ocr_mcp_command_edit.text() == "uvx minimax-coding-plan-mcp -y"
    assert page.ocr_base_url_edit.text() == "https://ocr.example.com"
    assert page.ocr_api_key_edit.text() == "ocr-key"
    assert page.helper_base_url_edit.text() == "https://helper.example.com"
    assert page.helper_api_key_edit.text() == "helper-key"
    assert page.feishu_app_id_edit.text() == "cli_xxx"
    assert page.feishu_app_secret_edit.text() == "secret_xxx"
    assert page.shop_selector.count() == 1
    assert page.shop_selector.currentText() == "草莓店"
    assert page.shop_wiki_url_edit.text() == "https://my.feishu.cn/wiki/QTXMwCDpQi9n6VkfDxJc5mNTnjh?table=tbl_xxx"
    assert page.shop_app_token_edit.text() == "app_token_1"
    assert page.shop_table_id_edit.text() == "tbl_xxx"
    assert page.shop_table_name_edit.text() == "草莓订单表"
    assert emitted == [page.to_payload()]


def test_settings_page_resolves_shop_tokens_from_wiki_url(qtbot):
    captured = []

    def resolver(wiki_url: str):
        captured.append(wiki_url)
        return {
            "app_token": "basc1234567890",
            "table_id": "tblWZDrx4gqXpc5M",
        }

    page = SettingsPage(on_resolve_shop_link=resolver)
    qtbot.addWidget(page)

    page.shop_name_edit.setText("乐宝零食店")
    page.shop_wiki_url_edit.setText(
        "https://my.feishu.cn/wiki/QTXMwCDpQi9n6VkfDxJc5mNTnjh?table=tblWZDrx4gqXpc5M&view=vew5lZdMQj"
    )

    page.save_shop_button.click()

    assert captured == [
        "https://my.feishu.cn/wiki/QTXMwCDpQi9n6VkfDxJc5mNTnjh?table=tblWZDrx4gqXpc5M&view=vew5lZdMQj"
    ]
    assert page.shop_app_token_edit.text() == "basc1234567890"
    assert page.shop_table_id_edit.text() == "tblWZDrx4gqXpc5M"
    assert page.status_label.text() == "已从飞书链接解析表格信息"


def test_history_page_load_rows_shows_summary_and_items(qtbot):
    page = HistoryPage()
    qtbot.addWidget(page)

    page.load_rows(
        [
            {
                "shop_name": "草莓店",
                "recipient_name": "何女士",
                "status": "已写入",
                "order_id": "6952003434324366473",
            },
            {
                "shop_name": "蓝莓店",
                "recipient_name": "彭柏棋",
                "status": "待重试",
                "order_id": "6952003434324366474",
            },
        ]
    )

    assert page.summary_label.text() == "共 2 条记录"
    assert page.list_widget.count() == 2
    assert page.list_widget.item(0).text() == "草莓店 · 何女士 · 已写入 · 6952003434324366473"
    assert page.list_widget.item(1).text() == "蓝莓店 · 彭柏棋 · 待重试 · 6952003434324366474"


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
                    "name": "草莓店",
                    "app_token": "app_token_1",
                    "table_id": "tbl_1",
                    "table_name": "草莓订单表",
                }
            ],
            "selected_shop_name": "草莓店",
        }
    )
    window = MainWindow(config_store=store)
    qtbot.addWidget(window)

    assert window.settings_page.helper_base_url_edit.text() == "https://api.minimaxi.com/v1"
    assert window.settings_page.helper_api_key_edit.text() == "minimax-secret"
    assert window.intake_page.shop_selector.currentText() == "草莓店"


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
                        "name": "草莓店",
                        "app_token": "app_token_1",
                        "table_id": "tbl_1",
                        "table_name": "草莓订单表",
                    }
                ],
                "selected_shop_name": "草莓店",
            }
        ),
        order_pipeline_factory=pipeline_factory,
    )
    qtbot.addWidget(window)
    window.intake_page._use_background_thread = False

    window.intake_page.process_image_bytes(b"image-bytes", "剪贴板截图")

    assert captured_payloads == [window.settings_page.to_payload()]
    assert window.intake_page.order_card_widget.order_id_edit.text() == "6952003434324366473"


def test_main_window_uses_default_mcp_command_when_enabled(qtbot):
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

    assert captured_payloads[0]["ocr_mcp_command"] == "uvx minimax-coding-plan-mcp -y"
