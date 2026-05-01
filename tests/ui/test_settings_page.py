from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QScrollArea, QStackedWidget

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
                    "platform": "微信小店",
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
    assert page.intake_default_shop_selector.currentText() == "乐宝零食店"
    assert page.shop_platform_selector.currentText() == "微信小店"
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
    page.product_jd_link_edit.setText("https://item.jd.com/1001.html")
    page.save_product_button.click()
    page.product_name_edit.setText("草莓")
    page.product_default_cost_edit.setText("8.20")
    page.product_jd_link_edit.setText("https://item.jd.com/1002.html")
    page.save_product_button.click()

    page.shop_wiki_url_edit.setText("https://my.feishu.cn/wiki/QTXMwCDpQi9n6VkfDxJc5mNTnjh?table=tbl_total")
    page.shop_app_token_edit.setText("app_token_total")
    page.shop_table_id_edit.setText("tbl_total")
    page.shop_table_name_edit.setText("订单总表")
    page.shop_mapping_edits["shop_name"].setText("店铺列")
    page.shop_mapping_edits["platform"].setText("平台列")
    page.shop_name_edit.setText("乐宝零食店")
    page.shop_platform_selector.setCurrentText("微信小店")
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
        {
            "name": "澳大利亚进口婴儿水",
            "default_cost": "12.50",
            "jd_link": "https://item.jd.com/1001.html",
        },
        {
            "name": "草莓",
            "default_cost": "8.20",
            "jd_link": "https://item.jd.com/1002.html",
        },
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
    assert payload["shops"][0]["platform"] == "微信小店"


def test_settings_page_preserves_procurement_templates_in_payload(qtbot):
    page = SettingsPage()
    qtbot.addWidget(page)

    page.load_payload(
        {
            "procurement_templates": [
                {
                    "specification": "1L/桶*12袋(赵露思同款 澳洲版)",
                    "procurement_items": [
                        {"product_name": "27000-澳洲版-1升装", "quantity": "2", "cost": "109"},
                        {"product_name": "康兴-瓶盖-粉色", "quantity": "1", "cost": "13.8"},
                        {"product_name": "", "quantity": "1", "cost": ""},
                    ],
                }
            ]
        }
    )

    payload = page.to_payload()

    assert payload["procurement_templates"] == [
        {
            "specification": "1L/桶*12袋(赵露思同款 澳洲版)",
            "procurement_items": [
                {"product_name": "27000-澳洲版-1升装", "quantity": "2", "cost": "109"},
                {"product_name": "康兴-瓶盖-粉色", "quantity": "1", "cost": "13.8"},
                {"product_name": "", "quantity": "", "cost": ""},
            ],
        }
    ]


def test_settings_page_load_payload_preserves_jd_links_and_accounts(qtbot):
    page = SettingsPage()
    qtbot.addWidget(page)

    page.load_payload(
        {
            "product_presets": [
                {
                    "name": "27000-澳洲版-1升装",
                    "default_cost": "89",
                    "jd_link": "https://item.jd.com/27000.html",
                }
            ],
            "jd_accounts": [
                {
                    "name": "京东账号A",
                    "environment": "/Users/gd/.jd/account-a",
                    "enabled": True,
                    "priority": 1,
                },
                {
                    "name": "京东账号B",
                    "environment": "profile-b",
                    "enabled": False,
                    "priority": 2,
                },
            ],
        }
    )

    assert page.product_selector.currentText() == "27000-澳洲版-1升装"
    assert page.product_default_cost_edit.text() == "89"
    assert page.product_jd_link_edit.text() == "https://item.jd.com/27000.html"
    assert page.jd_account_selector.count() == 2
    assert page.jd_account_name_edit.text() == "京东账号A"
    assert page.jd_account_environment_edit.text() == "/Users/gd/.jd/account-a"
    assert page.jd_account_enabled_checkbox.isChecked() is True
    assert page.jd_account_priority_edit.text() == "1"


def test_settings_page_to_payload_persists_jd_accounts(qtbot):
    page = SettingsPage()
    qtbot.addWidget(page)

    page.jd_account_name_edit.setText("京东账号A")
    page.jd_account_environment_edit.setText("/Users/gd/.jd/account-a")
    page.jd_account_enabled_checkbox.setChecked(True)
    page.jd_account_address_slot_verified_checkbox.setChecked(True)
    page.jd_account_priority_edit.setText("1")
    page.save_jd_account_button.click()

    payload = page.to_payload()

    assert payload["jd_accounts"] == [
        {
            "name": "京东账号A",
            "environment": "/Users/gd/.jd/account-a",
            "enabled": True,
            "address_slot_verified": True,
            "priority": 1,
        }
    ]


def test_settings_page_load_payload_preserves_address_slot_verified(qtbot):
    page = SettingsPage()
    qtbot.addWidget(page)

    page.load_payload(
        {
            "jd_accounts": [
                {
                    "name": "京东账号A",
                    "environment": "/Users/gd/.jd/account-a",
                    "enabled": True,
                    "address_slot_verified": True,
                    "priority": 1,
                },
                {
                    "name": "京东账号B",
                    "environment": "/Users/gd/.jd/account-b",
                    "enabled": True,
                    "address_slot_verified": False,
                    "priority": 2,
                },
            ]
        }
    )

    assert page.jd_account_selector.currentText() == "京东账号A"
    assert page.jd_account_address_slot_verified_checkbox.isChecked() is True

    page.jd_account_selector.setCurrentText("京东账号B")

    assert page.jd_account_address_slot_verified_checkbox.isChecked() is False


def test_settings_page_emits_auto_order_check_request_with_current_payload(qtbot):
    page = SettingsPage()
    qtbot.addWidget(page)

    page.auto_order_bridge_enabled_checkbox.setChecked(True)
    page.auto_order_bridge_base_url_edit.setText("http://127.0.0.1:9000")
    page.auto_order_bridge_api_key_edit.setText("bridge-key")
    page.jd_account_name_edit.setText("京东账号A")
    page.jd_account_environment_edit.setText("/Users/gd/.jd/account-a")
    page.jd_account_enabled_checkbox.setChecked(True)
    page.jd_account_address_slot_verified_checkbox.setChecked(True)
    page.jd_account_priority_edit.setText("1")
    page.save_jd_account_button.click()

    with qtbot.waitSignal(page.auto_order_check_requested, timeout=1000) as blocker:
        page.run_auto_order_check_button.click()

    payload = blocker.args[0]
    assert payload["auto_order_bridge_enabled"] is True
    assert payload["auto_order_bridge_base_url"] == "http://127.0.0.1:9000"
    assert payload["jd_accounts"][0]["address_slot_verified"] is True


def test_settings_page_emits_auto_order_service_restart_request_with_current_payload(qtbot):
    page = SettingsPage()
    qtbot.addWidget(page)

    page.auto_order_bridge_enabled_checkbox.setChecked(True)
    page.auto_order_bridge_base_url_edit.setText("http://127.0.0.1:9010")
    page.auto_order_bridge_api_key_edit.setText("bridge-key")

    with qtbot.waitSignal(page.auto_order_service_restart_requested, timeout=1000) as blocker:
        page.restart_auto_order_service_button.click()

    payload = blocker.args[0]
    assert payload["auto_order_bridge_enabled"] is True
    assert payload["auto_order_bridge_base_url"] == "http://127.0.0.1:9010"
    assert payload["auto_order_bridge_api_key"] == "bridge-key"


def test_settings_page_load_and_save_auto_order_http_bridge_config(qtbot):
    page = SettingsPage()
    qtbot.addWidget(page)

    page.load_payload(
        {
            "auto_order_bridge_enabled": True,
            "auto_order_bridge_base_url": "http://127.0.0.1:9000",
            "auto_order_bridge_api_key": "bridge-key",
            "auto_order_bridge_submit_path": "/auto-order/tasks",
            "auto_order_bridge_poll_path_template": "/auto-order/tasks/{task_id}",
            "auto_order_bridge_poll_interval_seconds": 5,
            "auto_order_bridge_timeout_seconds": 1800,
        }
    )

    assert page.auto_order_bridge_enabled_checkbox.isChecked() is True
    assert page.auto_order_bridge_base_url_edit.text() == "http://127.0.0.1:9000"
    assert page.auto_order_bridge_api_key_edit.text() == "bridge-key"
    assert page.auto_order_bridge_submit_path_edit.text() == "/auto-order/tasks"
    assert page.auto_order_bridge_poll_path_template_edit.text() == "/auto-order/tasks/{task_id}"
    assert page.auto_order_bridge_poll_interval_seconds_edit.text() == "5"
    assert page.auto_order_bridge_timeout_seconds_edit.text() == "1800"

    payload = page.to_payload()

    assert payload["auto_order_bridge_enabled"] is True
    assert payload["auto_order_bridge_base_url"] == "http://127.0.0.1:9000"
    assert payload["auto_order_bridge_api_key"] == "bridge-key"
    assert payload["auto_order_bridge_submit_path"] == "/auto-order/tasks"
    assert payload["auto_order_bridge_poll_path_template"] == "/auto-order/tasks/{task_id}"
    assert payload["auto_order_bridge_poll_interval_seconds"] == 5
    assert payload["auto_order_bridge_timeout_seconds"] == 1800


def test_settings_page_load_and_save_mobile_order_entry_config(qtbot):
    page = SettingsPage()
    qtbot.addWidget(page)

    page.load_payload(
        {
            "mobile_order_entry_enabled": True,
            "mobile_order_entry_host": "0.0.0.0",
            "mobile_order_entry_port": 9021,
            "mobile_order_entry_api_key": "mobile-key",
        }
    )

    assert page.mobile_order_entry_enabled_checkbox.isChecked() is True
    assert page.mobile_order_entry_host_edit.text() == "0.0.0.0"
    assert page.mobile_order_entry_port_edit.text() == "9021"
    assert page.mobile_order_entry_api_key_edit.text() == "mobile-key"
    assert page.mobile_order_entry_url_label.text() == "http://0.0.0.0:9021/mobile"

    payload = page.to_payload()

    assert payload["mobile_order_entry_enabled"] is True
    assert payload["mobile_order_entry_host"] == "0.0.0.0"
    assert payload["mobile_order_entry_port"] == 9021
    assert payload["mobile_order_entry_api_key"] == "mobile-key"


def test_settings_page_load_and_save_wechat_mp_config(qtbot):
    page = SettingsPage()
    qtbot.addWidget(page)

    page.load_payload(
        {
            "wechat_mp_enabled": True,
            "wechat_mp_token": "wechat-token",
            "wechat_mp_encoding_aes_key": "abcdefghijklmnopqrstuvwxyz123456789ABCDEFG",
            "wechat_mp_app_id": "wx1234567890",
            "wechat_mp_app_secret": "secret-123",
            "wechat_mp_tunnel_public_url": "https://orders.example.com/",
            "wechat_mp_callback_path": "wechat/callback",
            "wechat_mp_connection_status": "等待联调",
        }
    )

    assert page.wechat_mp_enabled_checkbox.isChecked() is True
    assert page.wechat_mp_token_edit.text() == "wechat-token"
    assert (
        page.wechat_mp_encoding_aes_key_edit.text()
        == "abcdefghijklmnopqrstuvwxyz123456789ABCDEFG"
    )
    assert page.wechat_mp_app_id_edit.text() == "wx1234567890"
    assert page.wechat_mp_app_secret_edit.text() == "secret-123"
    assert page.wechat_mp_tunnel_public_url_edit.text() == "https://orders.example.com"
    assert page.wechat_mp_callback_path_edit.text() == "/wechat/callback"
    assert page.wechat_mp_callback_url_label.text() == "https://orders.example.com/wechat/callback"
    assert page.wechat_mp_connection_status_label.text() == "等待联调"

    payload = page.to_payload()

    assert payload["wechat_mp_enabled"] is True
    assert payload["wechat_mp_token"] == "wechat-token"
    assert (
        payload["wechat_mp_encoding_aes_key"]
        == "abcdefghijklmnopqrstuvwxyz123456789ABCDEFG"
    )
    assert payload["wechat_mp_app_id"] == "wx1234567890"
    assert payload["wechat_mp_app_secret"] == "secret-123"
    assert payload["wechat_mp_tunnel_public_url"] == "https://orders.example.com"
    assert payload["wechat_mp_callback_path"] == "/wechat/callback"
    assert payload["wechat_mp_connection_status"] == "等待联调"


def test_settings_page_updates_wechat_mp_callback_url_preview(qtbot):
    page = SettingsPage()
    qtbot.addWidget(page)

    assert page.wechat_mp_callback_path_edit.text() == "/wechat/callback"
    assert page.wechat_mp_callback_url_label.text() == "待填写 Cloudflare Tunnel 公网地址后生成"

    page.wechat_mp_tunnel_public_url_edit.setText("https://demo.trycloudflare.com/")
    page.wechat_mp_callback_path_edit.setText("wx/mp")

    assert page.wechat_mp_callback_path_edit.text() == "/wx/mp"
    assert page.wechat_mp_callback_url_label.text() == "https://demo.trycloudflare.com/wx/mp"


def test_settings_page_load_payload_preserves_update_logs(qtbot):
    page = SettingsPage()
    qtbot.addWidget(page)

    page.load_payload(
        {
            "update_logs_initialized": True,
            "update_logs": [
                {
                    "id": "log-2",
                    "created_at": "2026-04-14 12:00:00",
                    "updated_at": "2026-04-14 12:00:00",
                    "module": "利润计算",
                    "title": "新增利润页",
                    "content": "新增大盘和每日账目明细两个 tab。",
                },
                {
                    "id": "log-1",
                    "created_at": "2026-04-13 10:00:00",
                    "updated_at": "2026-04-13 10:00:00",
                    "module": "历史",
                    "title": "支持历史编辑",
                    "content": "支持直接在历史页改订单并同步飞书。",
                },
            ],
        }
    )

    assert page.update_log_list.count() == 2
    assert "新增利润页" in page.update_log_list.item(0).text()


def test_settings_page_hides_header_helper_copy(qtbot):
    page = SettingsPage()
    qtbot.addWidget(page)

    texts = [label.text() for label in page.findChildren(QLabel)]

    assert "配置 OCR、辅助提取和飞书写入参数" not in texts
    assert "把 OCR、辅助提取和飞书凭证放在同一块，方便集中排查。" not in texts
    assert "沉淀每次开发的改动内容，方便后续回看和追踪。" not in texts
    assert "开发更新日志" not in texts


def test_settings_page_to_payload_persists_update_logs(qtbot):
    page = SettingsPage()
    qtbot.addWidget(page)

    page.load_payload({"update_logs_initialized": True, "update_logs": []})
    page._handle_add_update_log()
    page.update_log_module_edit.setText("录单")
    page.update_log_title_edit.setText("支持规格模板")
    page.update_log_content_edit.setPlainText("相同规格自动预填采购明细。")
    page._handle_save_update_log()

    payload = page.to_payload()

    assert payload["update_logs_initialized"] is True
    assert len(payload["update_logs"]) == 1
    assert payload["update_logs"][0]["module"] == "录单"
    assert payload["update_logs"][0]["title"] == "支持规格模板"
    assert payload["update_logs"][0]["content"] == "相同规格自动预填采购明细。"
    assert payload["update_logs"][0]["id"]
    assert payload["update_logs"][0]["created_at"]
    assert payload["update_logs"][0]["updated_at"]


def test_settings_page_can_edit_and_delete_update_log(qtbot):
    page = SettingsPage()
    qtbot.addWidget(page)

    page.load_payload(
        {
            "update_logs_initialized": True,
            "update_logs": [
                {
                    "id": "log-1",
                    "created_at": "2026-04-13 10:00:00",
                    "updated_at": "2026-04-13 10:00:00",
                    "module": "飞书同步",
                    "title": "初始标题",
                    "content": "初始内容",
                }
            ],
        }
    )

    page.update_log_title_edit.setText("改后标题")
    page.update_log_content_edit.setPlainText("改后内容")
    page._handle_save_update_log()

    assert page.to_payload()["update_logs"][0]["title"] == "改后标题"
    assert page.to_payload()["update_logs"][0]["content"] == "改后内容"

    page._handle_remove_update_log()

    assert page.update_log_list.count() == 0
    assert page.to_payload()["update_logs"] == []


def test_settings_page_normalizes_future_known_update_log_timestamps(qtbot):
    page = SettingsPage()
    qtbot.addWidget(page)

    page.load_payload(
        {
            "update_logs_initialized": True,
            "update_logs": [
                {
                    "id": "log-future",
                    "created_at": "2099-04-15 00:10:00",
                    "updated_at": "2099-04-15 00:10:00",
                    "module": "UI重构",
                    "title": "补齐侧栏命名与财务大盘分层",
                    "content": "测试未来时间修正。",
                }
            ],
        }
    )

    payload = page.to_payload()

    assert payload["update_logs"][0]["created_at"] == "2026-04-14 22:10:00"
    assert payload["update_logs"][0]["updated_at"] == "2026-04-14 22:10:00"


def test_settings_page_backfills_update_logs_once_for_empty_legacy_payload(qtbot):
    page = SettingsPage()
    qtbot.addWidget(page)

    page.load_payload({})
    first_payload = page.to_payload()

    assert first_payload["update_logs_initialized"] is True
    assert len(first_payload["update_logs"]) > 0

    page.load_payload(
        {
            "update_logs_initialized": True,
            "update_logs": [],
        }
    )

    assert page.to_payload()["update_logs"] == []


def test_settings_page_append_update_log_adds_latest_entry_to_top(qtbot):
    page = SettingsPage()
    qtbot.addWidget(page)

    page.load_payload({"update_logs_initialized": True, "update_logs": []})

    assert page.append_update_log(
        "历史",
        "修复历史备注清空同步",
        "历史页保存修改并重新写入飞书时，允许用空备注覆盖飞书备注列。",
        created_at="2026-04-14 22:30:00",
    ) is True

    payload = page.to_payload()

    assert payload["update_logs"][0]["module"] == "历史"
    assert payload["update_logs"][0]["title"] == "修复历史备注清空同步"
    assert payload["update_logs"][0]["content"] == "历史页保存修改并重新写入飞书时，允许用空备注覆盖飞书备注列。"
    assert page.update_log_list.count() == 1
    assert "修复历史备注清空同步" in page.update_log_list.item(0).text()


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

    scroll_area = page.findChild(QScrollArea, "SettingsSectionScroll")

    assert scroll_area is not None
    assert scroll_area.widgetResizable() is True
    assert scroll_area.frameShape() == QFrame.Shape.NoFrame
    assert scroll_area.widget().objectName() == "PageContent"


def test_settings_page_uses_horizontal_section_nav_and_content_stack(qtbot):
    page = SettingsPage()
    qtbot.addWidget(page)

    nav = page.findChild(QFrame, "SettingsSectionNav")
    stack = page.findChild(QStackedWidget, "SettingsSectionStack")
    buttons = nav.findChildren(QPushButton, "SettingsSectionTab")

    assert nav is not None
    assert stack is not None
    assert len(buttons) == 5
    assert stack.count() == 5
    assert buttons == page.section_nav_buttons
    assert all(button.isCheckable() for button in buttons)
    assert page.section_button_group.exclusive() is True
    assert stack.currentIndex() == 0
    assert [button.isChecked() for button in buttons] == [True, False, False, False, False]
    assert [button.text() for button in buttons] == [
        "接口配置",
        "商品库",
        "店铺映射",
        "自动拍单服务",
        "更新日志",
    ]
    assert [button.text() for button in page.section_nav_buttons] == [
        "接口配置",
        "商品库",
        "店铺映射",
        "自动拍单服务",
        "更新日志",
    ]


def test_settings_page_switches_each_horizontal_section_to_matching_content(qtbot):
    page = SettingsPage()
    qtbot.addWidget(page)

    stack = page.findChild(QStackedWidget, "SettingsSectionStack")

    def assert_selected(index):
        assert stack.currentIndex() == index
        assert [button.isChecked() for button in page.section_nav_buttons] == [
            button_index == index for button_index in range(len(page.section_nav_buttons))
        ]

    def current_content():
        return stack.currentWidget().widget()

    page.section_nav_buttons[0].click()
    content = current_content()
    assert_selected(0)
    assert page.ocr_base_url_edit in content.findChildren(type(page.ocr_base_url_edit))
    assert page.helper_base_url_edit in content.findChildren(type(page.helper_base_url_edit))
    assert page.feishu_app_id_edit in content.findChildren(type(page.feishu_app_id_edit))

    page.section_nav_buttons[1].click()
    content = current_content()
    assert_selected(1)
    assert page.product_selector in content.findChildren(type(page.product_selector))
    assert page.product_name_edit in content.findChildren(type(page.product_name_edit))
    assert page.product_jd_link_edit in content.findChildren(type(page.product_jd_link_edit))
    assert page.custom_cost_label_edits[0] in content.findChildren(type(page.custom_cost_label_edits[0]))

    page.section_nav_buttons[2].click()
    content = current_content()
    assert stack.currentIndex() == 2
    assert page.section_nav_buttons[2].isChecked() is True
    assert page.shop_selector in content.findChildren(type(page.shop_selector))
    assert page.shop_wiki_url_edit in content.findChildren(type(page.shop_wiki_url_edit))
    assert page.show_enabled_only_checkbox in content.findChildren(type(page.show_enabled_only_checkbox))
    assert page.mapping_row_widgets["店铺"] in content.findChildren(type(page.mapping_row_widgets["店铺"]))

    page.section_nav_buttons[3].click()
    content = current_content()
    assert stack.currentIndex() == 3
    assert page.section_nav_buttons[3].isChecked() is True
    assert page.auto_order_bridge_enabled_checkbox in content.findChildren(
        type(page.auto_order_bridge_enabled_checkbox)
    )
    assert page.auto_order_bridge_base_url_edit in content.findChildren(
        type(page.auto_order_bridge_base_url_edit)
    )
    assert page.auto_order_bridge_submit_path_edit in content.findChildren(
        type(page.auto_order_bridge_submit_path_edit)
    )
    assert page.auto_order_bridge_poll_path_template_edit in content.findChildren(
        type(page.auto_order_bridge_poll_path_template_edit)
    )

    page.section_nav_buttons[4].click()
    content = current_content()
    assert_selected(4)
    assert page.update_log_list in content.findChildren(type(page.update_log_list))
    assert page.update_log_module_edit in content.findChildren(type(page.update_log_module_edit))
    assert page.update_log_title_edit in content.findChildren(type(page.update_log_title_edit))
    assert page.update_log_content_edit in content.findChildren(type(page.update_log_content_edit))


def test_settings_page_auto_order_service_is_independent_section_with_fields(qtbot):
    page = SettingsPage()
    qtbot.addWidget(page)

    stack = page.findChild(QStackedWidget, "SettingsSectionStack")
    auto_order_button = page.section_nav_buttons[3]

    auto_order_button.click()

    content = stack.currentWidget().widget()
    assert stack.currentIndex() == 3
    assert auto_order_button.isChecked() is True
    assert page.auto_order_bridge_enabled_checkbox in content.findChildren(
        type(page.auto_order_bridge_enabled_checkbox)
    )
    assert page.auto_order_bridge_base_url_edit in content.findChildren(
        type(page.auto_order_bridge_base_url_edit)
    )
    assert page.jd_account_selector in content.findChildren(type(page.jd_account_selector))
    assert page.jd_account_environment_edit in content.findChildren(
        type(page.jd_account_environment_edit)
    )


def test_settings_page_uses_three_column_mapping_grid(qtbot):
    page = SettingsPage()
    qtbot.addWidget(page)

    assert page.mapping_grid_layout.itemAtPosition(0, 0) is not None
    assert page.mapping_grid_layout.itemAtPosition(0, 1) is not None
    assert page.mapping_grid_layout.itemAtPosition(0, 2) is not None


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
    assert page.shop_mapping_edits["specification"].text() == "规格"
    assert page.shop_mapping_edits["sku"].text() == ""
    assert page.shop_mapping_edits["sku_image"].text() == "SKU图片"
    assert page.shop_mapping_edits["quantity"].text() == "数量"
    assert page.shop_mapping_edits["recipient_name"].text() == "收件人"
    assert page.shop_mapping_edits["phone_number"].text() == "手机号"
    assert page.shop_mapping_edits["code"].text() == "编号"
    assert page.shop_mapping_edits["income"].text() == "收入"
    assert page.shop_mapping_edits["shipping_address"].text() == "发货地址"
    assert page.mapping_edits["采购快递单号"].text() == "采购快递单号"
    assert page.mapping_edits["采购快递单号1"].text() == "采购快递单号1"
    assert page.mapping_edits["采购快递单号2"].text() == "采购快递单号2"
    assert page.mapping_edits["采购快递单号3"].text() == "采购快递单号3"
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


def test_settings_page_can_permanently_clear_missing_field_mappings(qtbot):
    def inspect_fields(_payload: dict):
        return {"店铺", "收入"}

    page = SettingsPage(on_inspect_table_fields=inspect_fields)
    qtbot.addWidget(page)

    page.check_table_fields_button.click()
    page.clear_missing_field_mappings_button.click()

    assert page.mapping_edits["店铺"].text() == "店铺"
    assert page.mapping_edits["收入"].text() == "收入"
    assert page.mapping_edits["平台"].text() == ""
    assert page.mapping_edits["订单编号"].text() == ""
    assert page.mapping_edits["采购商品1"].text() == ""

    payload = page.to_payload()
    reloaded = SettingsPage()
    qtbot.addWidget(reloaded)
    reloaded.load_payload(payload)

    assert reloaded.mapping_edits["平台"].text() == ""
    assert reloaded.mapping_edits["订单编号"].text() == ""


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
    assert payload["intake_default_platform"] == "抖店"
    assert payload["intake_default_shop_name_douyin"] == "乐宝零食店"
    assert payload["intake_default_shop_name_wechat"] == ""
    assert payload["intake_default_shop_name"] == "乐宝零食店"
    assert "草莓店" not in [shop["name"] for shop in payload["shops"]]


def test_settings_page_persists_platform_specific_intake_default_shops(qtbot):
    page = SettingsPage()
    qtbot.addWidget(page)

    page.shop_selector.setCurrentText("欢宝零食店")
    page._shops.append({"name": "乐宝零食店--微信", "platform": "微信小店"})
    page._shops = page._normalize_shops(page._shops)
    page._refresh_shop_selector("欢宝零食店")
    page._refresh_platform_default_shop_selectors("君宝零食店", "乐宝零食店--微信")
    page.intake_default_platform_selector.setCurrentText("微信小店")

    payload = page.to_payload()

    assert payload["selected_shop_name"] == "欢宝零食店"
    assert payload["intake_default_platform"] == "微信小店"
    assert payload["intake_default_shop_name_douyin"] == "君宝零食店"
    assert payload["intake_default_shop_name_wechat"] == "乐宝零食店--微信"
    assert payload["intake_default_shop_name"] == "乐宝零食店--微信"


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


def test_settings_page_hides_low_priority_mappings_by_default(qtbot):
    page = SettingsPage()
    qtbot.addWidget(page)

    assert not page.mapping_row_widgets["店铺"].isHidden()
    assert not page.mapping_row_widgets["规格"].isHidden()
    assert page.mapping_row_widgets["SKU"].isHidden()
    assert page.mapping_row_widgets["SKU 图片"].isHidden()
    assert page.mapping_row_widgets["订单编号"].isHidden()
    assert page.mapping_row_widgets["价格"].isHidden()
    assert page.mapping_row_widgets["采购快递单号"].isHidden()
    assert page.mapping_row_widgets["自定义字段1"].isHidden()
    assert page.mapping_row_widgets["同步状态"].isHidden()
    assert page.mapping_row_widgets["录入时间"].isHidden()


def test_settings_page_preserves_hidden_mapping_values_in_payload(qtbot):
    page = SettingsPage()
    qtbot.addWidget(page)

    page.load_payload(
        {
            "feishu_field_mapping": {
                "SKU": "SKU列",
                "SKU 图片": "图片列",
                "订单编号": "订单编号列",
                "价格": "价格列",
                "同步状态": "同步状态列",
            }
        }
    )

    payload = page.to_payload()

    assert payload["feishu_field_mapping"]["SKU"] == "SKU列"
    assert payload["feishu_field_mapping"]["SKU 图片"] == "图片列"
    assert payload["feishu_field_mapping"]["订单编号"] == "订单编号列"
    assert payload["feishu_field_mapping"]["价格"] == "价格列"
    assert payload["feishu_field_mapping"]["同步状态"] == "同步状态列"


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


def test_main_window_navigates_between_six_pages(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)

    assert window.nav.currentRow() == 0
    assert window.stack.currentWidget() is window.intake_page

    window.nav.setCurrentRow(1)
    assert window.stack.currentWidget() is window.history_page

    window.nav.setCurrentRow(2)
    assert window.stack.currentWidget() is window.auto_order_page

    window.nav.setCurrentRow(3)
    assert window.stack.currentWidget() is window.profit_page

    window.nav.setCurrentRow(4)
    assert window.stack.currentWidget() is window.expense_page

    window.nav.setCurrentRow(5)
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


def test_main_window_prefers_intake_default_shop_name_for_entry_page(qtbot):
    store = MemoryConfigStore(
        {
            "shops": [
                {"name": "乐宝零食店"},
                {"name": "欢宝零食店"},
                {"name": "君宝零食店"},
            ],
            "selected_shop_name": "欢宝零食店",
            "intake_default_shop_name": "君宝零食店",
        }
    )
    window = MainWindow(config_store=store)
    qtbot.addWidget(window)

    assert window.settings_page.shop_selector.currentText() == "欢宝零食店"
    assert window.settings_page.intake_default_douyin_shop_selector.currentText() == "君宝零食店"
    assert window.intake_page.shop_selector.currentText() == "君宝零食店"


def test_main_window_applies_platform_specific_shop_defaults_on_entry_page(qtbot):
    store = MemoryConfigStore(
        {
            "shops": [
                {"name": "乐宝零食店", "platform": "抖店"},
                {"name": "乐宝零食店—微信", "platform": "微信小店"},
            ],
            "selected_shop_name": "乐宝零食店",
            "intake_default_platform": "抖店",
            "intake_default_shop_name_douyin": "乐宝零食店",
            "intake_default_shop_name_wechat": "乐宝零食店—微信",
        }
    )

    window = MainWindow(config_store=store)
    qtbot.addWidget(window)

    assert window.intake_page.shop_selector.currentText() == "乐宝零食店"
    assert window.intake_page.platform_selector.currentText() == "抖店"

    window.intake_page.platform_selector.setCurrentText("微信小店")

    assert window.intake_page.shop_selector.currentText() == "乐宝零食店—微信"
    assert window.intake_page.platform_selector.currentText() == "微信小店"


def test_main_window_infers_wechat_platform_for_legacy_wechat_shop_names(qtbot):
    store = MemoryConfigStore(
        {
            "shops": [
                {"name": "乐宝零食店"},
                {"name": "乐宝零食店--微信"},
            ],
            "selected_shop_name": "乐宝零食店",
            "intake_default_shop_name": "乐宝零食店--微信",
        }
    )

    window = MainWindow(config_store=store)
    qtbot.addWidget(window)

    assert window.intake_page.shop_selector.currentText() == "乐宝零食店--微信"
    assert window.intake_page.platform_selector.currentText() == "微信小店"


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

    assert store.saved_payloads
    assert store.saved_payloads[-1] == window.settings_page.to_payload()


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
