from strawberry_order_management.ui.main_window import MainWindow
from strawberry_order_management.ui.pages.history_page import HistoryPage
from strawberry_order_management.ui.pages.settings_page import SettingsPage


def test_settings_page_collects_api_configuration(qtbot):
    page = SettingsPage()
    qtbot.addWidget(page)

    page.ocr_base_url_edit.setText("https://ocr.example.com")
    page.ocr_api_key_edit.setText("ocr-key")
    page.helper_base_url_edit.setText("https://helper.example.com")
    page.helper_api_key_edit.setText("helper-key")
    page.feishu_app_id_edit.setText("cli_xxx")
    page.feishu_app_secret_edit.setText("secret_xxx")
    page.feishu_table_id_edit.setText("tbl_xxx")
    page.feishu_table_name_edit.setText("草莓订单表")

    payload = page.to_payload()

    assert payload["ocr_base_url"] == "https://ocr.example.com"
    assert payload["ocr_api_key"] == "ocr-key"
    assert payload["helper_base_url"] == "https://helper.example.com"
    assert payload["helper_api_key"] == "helper-key"
    assert payload["feishu_app_id"] == "cli_xxx"
    assert payload["feishu_app_secret"] == "secret_xxx"
    assert payload["feishu_table_id"] == "tbl_xxx"
    assert payload["feishu_table_name"] == "草莓订单表"


def test_settings_page_load_payload_and_save_requested(qtbot):
    page = SettingsPage()
    qtbot.addWidget(page)

    payload = {
        "ocr_base_url": " https://ocr.example.com ",
        "ocr_api_key": " ocr-key ",
        "helper_base_url": " https://helper.example.com ",
        "helper_api_key": " helper-key ",
        "feishu_app_id": " cli_xxx ",
        "feishu_app_secret": " secret_xxx ",
        "feishu_table_id": " tbl_xxx ",
        "feishu_table_name": " 草莓订单表 ",
    }

    emitted = []
    page.save_requested.connect(emitted.append)

    page.load_payload(payload)
    page.save_button.click()

    assert page.ocr_base_url_edit.text() == "https://ocr.example.com"
    assert page.ocr_api_key_edit.text() == "ocr-key"
    assert page.helper_base_url_edit.text() == "https://helper.example.com"
    assert page.helper_api_key_edit.text() == "helper-key"
    assert page.feishu_app_id_edit.text() == "cli_xxx"
    assert page.feishu_app_secret_edit.text() == "secret_xxx"
    assert page.feishu_table_id_edit.text() == "tbl_xxx"
    assert page.feishu_table_name_edit.text() == "草莓订单表"
    assert emitted == [page.to_payload()]


def test_history_page_load_rows_shows_summary_and_items(qtbot):
    page = HistoryPage()
    qtbot.addWidget(page)

    page.load_rows(
        [
            {
                "recipient_name": "何女士",
                "status": "已写入",
                "order_id": "6952003434324366473",
            },
            {
                "recipient_name": "彭柏棋",
                "status": "待重试",
                "order_id": "6952003434324366474",
            },
        ]
    )

    assert page.summary_label.text() == "共 2 条记录"
    assert page.list_widget.count() == 2
    assert page.list_widget.item(0).text() == "何女士 · 已写入 · 6952003434324366473"
    assert page.list_widget.item(1).text() == "彭柏棋 · 待重试 · 6952003434324366474"


def test_history_page_renders_none_as_dash(qtbot):
    page = HistoryPage()
    qtbot.addWidget(page)

    page.load_rows(
        [
            {
                "recipient_name": None,
                "status": None,
                "order_id": None,
            }
        ]
    )

    assert page.list_widget.count() == 1
    assert page.list_widget.item(0).text() == "- · - · -"


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
        }
    )
    window = MainWindow(config_store=store)
    qtbot.addWidget(window)

    assert window.settings_page.helper_base_url_edit.text() == "https://api.minimaxi.com/v1"
    assert window.settings_page.helper_api_key_edit.text() == "minimax-secret"


def test_main_window_saves_settings_into_config_store(qtbot):
    store = MemoryConfigStore()
    window = MainWindow(config_store=store)
    qtbot.addWidget(window)

    window.settings_page.helper_base_url_edit.setText("https://api.minimaxi.com/v1")
    window.settings_page.helper_api_key_edit.setText("minimax-secret")
    window.settings_page.save_button.click()

    assert store.saved_payloads == [window.settings_page.to_payload()]
