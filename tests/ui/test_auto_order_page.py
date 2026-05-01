from datetime import date, timedelta
from typing import Optional

from PySide6.QtWidgets import QMessageBox

from strawberry_order_management.ui.pages import auto_order_page as auto_order_page_module
from strawberry_order_management.ui.pages.auto_order_page import AutoOrderPage


def _row(
    record_id: str,
    shop_name: str,
    recipient_name: str,
    placed_at: str,
    auto_order_status: str,
    procurement_items: list[dict],
    auto_order_debug: Optional[dict] = None,
):
    return {
        "record_id": record_id,
        "shop_name": shop_name,
        "auto_order_status": auto_order_status,
        "auto_order_message": "",
        "auto_order_last_run_at": "",
        "auto_order_debug": auto_order_debug or {},
        "order_snapshot": {
            "order_id": f"order-{record_id}",
            "placed_at": placed_at,
            "recipient_name": recipient_name,
            "procurement_items": procurement_items,
        },
    }


def test_auto_order_page_only_shows_orders_with_procurement_and_hides_empty_slots(qtbot):
    page = AutoOrderPage()
    qtbot.addWidget(page)

    today = f"{date.today().isoformat()} 10:00:00"
    page.load_rows(
        [
            _row(
                "record-1",
                "乐宝零食店",
                "张可可",
                today,
                "",
                [
                    {"product_name": "27000-赵露思款", "quantity": "1", "cost": "89"},
                    {"product_name": "", "quantity": "", "cost": ""},
                    {"product_name": "赠品补发件", "quantity": "1", "cost": "0"},
                ],
            ),
            _row(
                "record-2",
                "欢宝零食店",
                "丽",
                today,
                "",
                [
                    {"product_name": "", "quantity": "", "cost": ""},
                    {"product_name": "", "quantity": "", "cost": ""},
                    {"product_name": "", "quantity": "", "cost": ""},
                ],
            ),
        ]
    )

    assert len(page.order_group_widgets) == 1
    assert page.order_group_widgets[0].record_id == "record-1"
    assert page.order_group_widgets[0].header_status_badge.text() == "待处理"
    assert page.order_group_widgets[0].history_jump_button.text() == "跳转历史"
    assert page.order_group_widgets[0].primary_action_button.text() == "开始拍单"
    assert [row.slot_name_label.text() for row in page.order_group_widgets[0].slot_rows] == [
        "采购1",
        "采购3",
    ]


def test_auto_order_page_filters_by_quick_range_shop_status_and_keyword(qtbot):
    page = AutoOrderPage()
    qtbot.addWidget(page)

    today = date.today()
    yesterday = today - timedelta(days=1)
    page.load_rows(
        [
            _row(
                "record-today",
                "乐宝零食店",
                "张可可",
                f"{today.isoformat()} 09:30:00",
                "失败",
                [{"product_name": "27000-赵露思款", "quantity": "1", "cost": "89"}],
            ),
            _row(
                "record-yesterday",
                "欢宝零食店",
                "李仙女",
                f"{yesterday.isoformat()} 18:20:00",
                "",
                [{"product_name": "瓶盖粉色配件", "quantity": "1", "cost": "13.8"}],
            ),
        ]
    )

    page.quick_filter_buttons["今天"].click()
    assert [widget.record_id for widget in page.order_group_widgets] == ["record-today"]

    page.shop_filter_combo.setCurrentText("乐宝零食店")
    page.status_filter_combo.setCurrentText("失败")
    page.keyword_filter_edit.setText("张可可")
    page.apply_filters_button.click()
    assert [widget.record_id for widget in page.order_group_widgets] == ["record-today"]

    page.clear_filters_button.click()
    assert {widget.record_id for widget in page.order_group_widgets} == {
        "record-today",
        "record-yesterday",
    }


def test_auto_order_page_can_open_latest_process_dialog(qtbot):
    page = AutoOrderPage()
    qtbot.addWidget(page)

    today = f"{date.today().isoformat()} 10:00:00"
    page.load_rows(
        [
            _row(
                "record-1",
                "乐宝零食店",
                "张可可",
                today,
                "失败",
                [{"product_name": "27000-赵露思款", "quantity": "1", "cost": "89"}],
                auto_order_debug={
                    "stage": "地址粘贴识别失败",
                    "summary": "地址粘贴识别失败",
                    "updated_at": "2026-04-17 12:00:05",
                    "screenshot_path": "/tmp/auto-order-failure.png",
                    "steps": [
                        {"at": "2026-04-17 12:00:01", "text": "选中账号环境：京东账号A"},
                        {"at": "2026-04-17 12:00:03", "text": "粘贴结果一"},
                    ],
                },
            )
        ]
    )

    page.order_group_widgets[0].view_process_button.click()

    qtbot.waitUntil(lambda: page._process_dialog is not None and page._process_dialog.isVisible())

    assert page._process_dialog.status_value_label.text() == "失败"
    assert "地址粘贴识别失败" in page._process_dialog.summary_value_label.text()
    assert "选中账号环境：京东账号A" in page._process_dialog.steps_text.toPlainText()
    assert page._process_dialog.screenshot_path_label.text() == "/tmp/auto-order-failure.png"


def test_auto_order_page_ready_to_pay_shows_relaunch_buttons(qtbot):
    page = AutoOrderPage()
    qtbot.addWidget(page)

    today = f"{date.today().isoformat()} 10:00:00"
    page.load_rows(
        [
            _row(
                "record-1",
                "乐宝零食店",
                "鲁世豪",
                today,
                "已到待付款",
                [
                    {
                        "product_name": "27000-澳洲版-1升装",
                        "quantity": "2",
                        "cost": "109",
                        "jd_status": "待付款",
                        "jd_order_id": "3472490012576671",
                    }
                ],
            )
        ]
    )

    group = page.order_group_widgets[0]
    assert group.primary_action_button.text() == "重新发起订单"
    assert group.slot_rows[0].action_button.text() == "重新发起"


def test_auto_order_page_relaunch_buttons_require_confirmation(qtbot, monkeypatch):
    page = AutoOrderPage()
    qtbot.addWidget(page)

    today = f"{date.today().isoformat()} 10:00:00"
    page.load_rows(
        [
            _row(
                "record-1",
                "乐宝零食店",
                "鲁世豪",
                today,
                "已到待付款",
                [
                    {
                        "product_name": "27000-澳洲版-1升装",
                        "quantity": "2",
                        "cost": "109",
                        "jd_status": "待付款",
                        "jd_order_id": "3472490012576671",
                    }
                ],
            )
        ]
    )
    emitted = []
    page.auto_order_requested.connect(lambda record_id, indices: emitted.append((record_id, tuple(indices))))
    monkeypatch.setattr(auto_order_page_module.QMessageBox, "question", lambda *args, **kwargs: QMessageBox.StandardButton.No)

    group = page.order_group_widgets[0]
    group.primary_action_button.click()
    group.slot_rows[0].action_button.click()

    assert emitted == []


def test_auto_order_page_relaunch_buttons_emit_after_confirmation(qtbot, monkeypatch):
    page = AutoOrderPage()
    qtbot.addWidget(page)

    today = f"{date.today().isoformat()} 10:00:00"
    page.load_rows(
        [
            _row(
                "record-1",
                "乐宝零食店",
                "鲁世豪",
                today,
                "已到待付款",
                [
                    {
                        "product_name": "27000-澳洲版-1升装",
                        "quantity": "2",
                        "cost": "109",
                        "jd_status": "待付款",
                        "jd_order_id": "3472490012576671",
                    }
                ],
            )
        ]
    )
    emitted = []
    page.auto_order_requested.connect(lambda record_id, indices: emitted.append((record_id, tuple(indices))))
    monkeypatch.setattr(auto_order_page_module.QMessageBox, "question", lambda *args, **kwargs: QMessageBox.StandardButton.Yes)

    group = page.order_group_widgets[0]
    group.primary_action_button.click()
    group.slot_rows[0].action_button.click()

    assert emitted == [
        ("record-1", (0,)),
        ("record-1", (0,)),
    ]
