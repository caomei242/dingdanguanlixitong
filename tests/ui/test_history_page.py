from datetime import date, timedelta

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QScrollArea, QWidget

from strawberry_order_management.ui.pages.history_page import HistoryPage


def _row(
    record_id: str,
    shop_name: str,
    sync_source: str,
    status: str,
    order_id: str,
    recipient_name: str,
    address_one: str,
    address_two: str,
):
    return {
        "record_id": record_id,
        "shop_name": shop_name,
        "sync_source": sync_source,
        "status": status,
        "message": "写入成功" if status == "已写入飞书" else "写入失败：字段缺失",
        "order_snapshot": {
            "order_id": order_id,
            "placed_at": "2026-04-11 20:57:15",
            "platform": "抖店",
            "order_status": "已发货",
            "product_name": "澳大利亚进口婴儿水",
            "specification": "1L/桶*12袋(赵露思同款 澳洲版)",
            "sku": "27000-澳洲版-1升装",
            "quantity": "1",
            "order_amount": "405.00",
            "income_amount": "162.00",
            "recipient_name": recipient_name,
            "phone_number": "15781304332",
            "code": "3612",
            "address": "四川省成都市金牛区营门口街道友谊花园9-2304",
            "delivery_note": "请电话送货上门谢谢【3612】",
            "procurement_tracking_number": "",
            "platform_fee_rate": "10",
            "platform_fee_amount": "16.20",
            "other_cost": "5.00",
            "procurement_total_cost": "38.00",
            "gross_profit": "101.80",
            "custom_cost_labels": ["包装费", "", ""],
            "custom_cost_values": ["1.00", "", ""],
            "procurement_items": [
                {"product_name": "澳洲婴儿水", "quantity": "2", "cost": "19.00"},
                {"product_name": "", "quantity": "1", "cost": ""},
                {"product_name": "", "quantity": "1", "cost": ""},
            ],
        },
        "address_snapshot": {
            "output_one": address_one,
            "output_two": address_two,
        },
        "feishu_result": {"data": {"record_id": f"feishu-{record_id}"}},
    }


def test_history_page_loads_legacy_flat_rows(qtbot):
    page = HistoryPage()
    qtbot.addWidget(page)

    page.load_rows(
        [
            {
                "record_id": "legacy-1",
                "shop_name": "草莓店",
                "sync_source": "仅存历史",
                "status": "已写入飞书",
                "order_id": "6952003434324366473",
                "recipient_name": "何女士",
                "address": "四川省成都市金牛区营门口街道友谊花园9-2304",
                "output_one": "何女士15781304332四川省成都市金牛区营门口街道友谊花园9-2304",
                "output_two": "请电话送货上门谢谢【3612】",
            }
        ]
    )

    assert page.list_widget.count() == 1
    assert page.detail_title_label.text() == "草莓店"
    assert page.order_id_value.toPlainText() == "6952003434324366473"
    assert page.recipient_name_value.toPlainText() == "何女士"
    assert page.address_output_one.toPlainText() == (
        "何女士15781304332四川省成都市金牛区营门口街道友谊花园9-2304"
    )
    assert page.address_output_two.toPlainText() == "请电话送货上门谢谢【3612】"


def test_history_page_renders_list_and_loads_first_then_current_item(qtbot):
    page = HistoryPage()
    qtbot.addWidget(page)

    rows = [
        _row(
            "record-1",
            "乐宝零食店",
            "确认写入飞书",
            "已写入飞书",
            "6952003434324366473",
            "何女士",
            "何女士15781304332四川省成都市",
            "请电话送货上门谢谢【3612】",
        ),
        _row(
            "record-2",
            "欢宝零食店",
            "仅存历史",
            "写入失败",
            "6952003434324366111",
            "田宝山",
            "田宝山15784081541山东省德州市",
            "请放门口",
        ),
    ]

    page.load_rows(rows)

    assert page.list_widget.count() == 2
    assert page.list_widget.currentRow() == 0
    assert page.detail_title_label.text() == "乐宝零食店"
    assert page.order_id_value.toPlainText() == "6952003434324366473"
    assert page.recipient_name_value.toPlainText() == "何女士"
    assert page.address_output_one.toPlainText() == "何女士15781304332四川省成都市"
    assert page.address_output_two.toPlainText() == "请电话送货上门谢谢【3612】"

    page.list_widget.setCurrentRow(1)

    assert page.detail_title_label.text() == "欢宝零食店"
    assert page.order_id_value.toPlainText() == "6952003434324366111"
    assert page.recipient_name_value.toPlainText() == "田宝山"
    assert page.address_output_one.toPlainText() == "田宝山15784081541山东省德州市"
    assert page.address_output_two.toPlainText() == "请放门口"
    assert page.status_summary_buttons["全部订单"].value_label.text() == "2"
    assert page.status_summary_buttons["已发货"].value_label.text() == "2"
    assert page.status_summary_buttons["待发货"].value_label.text() == "0"
    assert page.header_actions_widget.isHidden() is False
    assert page.left_column_widget.layout().count() == 1
    assert page.detail_summary_card.isHidden() is False
    assert page.summary_recipient_label.text() == "收货人"
    assert page.summary_recipient_value.text() == "田宝山"
    assert page.summary_income_label.text() == "收入"
    assert page.summary_income_value.text() == "162.00"
    assert page.summary_placed_at_label.text() == "下单时间"
    assert page.summary_placed_at_value.text() == "2026-04-11 20:57:15"
    assert page.summary_status_label.text() == "订单状态"
    assert page.summary_status_value.currentText() == "已发货"
    assert page.order_id_value.minimumHeight() <= 40
    assert page.address_value.minimumHeight() <= 60


def test_history_page_summary_status_combo_stays_in_sync_with_detail_status(qtbot):
    page = HistoryPage()
    qtbot.addWidget(page)
    page.load_rows(
        [
            _row(
                "record-1",
                "乐宝零食店",
                "确认写入飞书",
                "已写入飞书",
                "6952003434324366473",
                "何女士",
                "何女士15781304332四川省成都市",
                "请电话送货上门谢谢【3612】",
            )
        ]
    )

    assert page.summary_status_value.currentText() == "已发货"
    assert page.order_status_value.currentText() == "已发货"

    page.summary_status_value.setCurrentText("待发货")
    assert page.order_status_value.currentText() == "待发货"

    page.order_status_value.setCurrentText("已拍单未发货")
    assert page.summary_status_value.currentText() == "已拍单未发货"


def test_history_page_uses_master_detail_workspace_shell(qtbot):
    page = HistoryPage()
    qtbot.addWidget(page)

    assert page.findChild(QFrame, "HistoryFilterCard") is not None
    assert page.findChild(QWidget, "HistoryStatsRow") is not None
    assert page.findChild(QFrame, "HistoryMasterPane") is not None
    assert page.findChild(QFrame, "HistoryDetailPane") is not None
    assert page.findChild(QFrame, "HistoryStickyActionBar") is not None
    assert page.findChild(QScrollArea, "HistoryDetailScroll") is not None


def test_history_page_hides_sku_field_but_keeps_sku_image(qtbot):
    page = HistoryPage()
    qtbot.addWidget(page)

    page.load_rows(
        [
            _row(
                "record-1",
                "乐宝零食店",
                "确认写入飞书",
                "已写入飞书",
                "6952003434324366473",
                "何女士",
                "何女士15781304332四川省成都市",
                "请电话送货上门谢谢【3612】",
            )
        ]
    )

    labels = [label.text() for label in page.findChildren(type(page.detail_title_label))]

    assert "SKU" not in labels
    assert "SKU 图片" in labels


def test_history_page_keeps_selected_record_when_rows_refresh(qtbot):
    page = HistoryPage()
    qtbot.addWidget(page)

    rows = [
        _row(
            "record-1",
            "乐宝零食店",
            "确认写入飞书",
            "已写入飞书",
            "6952003434324366473",
            "何女士",
            "何女士15781304332四川省成都市",
            "请电话送货上门谢谢【3612】",
        ),
        _row(
            "record-2",
            "欢宝零食店",
            "仅存历史",
            "写入失败",
            "6952003434324366111",
            "田宝山",
            "田宝山15784081541山东省德州市",
            "请放门口",
        ),
    ]

    page.load_rows(rows)
    page.list_widget.setCurrentRow(1)

    refreshed_rows = [
        dict(rows[0], status="已写入飞书"),
        dict(rows[1], status="写入失败"),
    ]
    page.load_rows(refreshed_rows)

    assert page.list_widget.currentRow() == 1
    assert page.detail_title_label.text() == "欢宝零食店"


def test_history_page_falls_back_to_adjacent_record_when_selected_row_is_deleted(qtbot):
    page = HistoryPage()
    qtbot.addWidget(page)

    rows = [
        _row(
            "record-1",
            "乐宝零食店",
            "确认写入飞书",
            "已写入飞书",
            "6952003434324366473",
            "何女士",
            "何女士15781304332四川省成都市",
            "请电话送货上门谢谢【3612】",
        ),
        _row(
            "record-2",
            "欢宝零食店",
            "仅存历史",
            "写入失败",
            "6952003434324366111",
            "田宝山",
            "田宝山15784081541山东省德州市",
            "请放门口",
        ),
        _row(
            "record-3",
            "灵宝零食店",
            "仅存历史",
            "已写入飞书",
            "6952003434324366999",
            "王先生",
            "王先生13900001111广东省深圳市",
            "请尽快发货",
        ),
    ]

    page.load_rows(rows)
    page.list_widget.setCurrentRow(1)

    page.load_rows([rows[0], rows[2]])

    assert page.list_widget.currentRow() == 1
    assert page.detail_title_label.text() == "灵宝零食店"


def test_history_page_emits_record_ids_for_actions(qtbot):
    page = HistoryPage()
    qtbot.addWidget(page)
    page.load_rows(
        [
            _row(
                "record-1",
                "乐宝零食店",
                "确认写入飞书",
                "已写入飞书",
                "6952003434324366473",
                "何女士",
                "何女士15781304332四川省成都市",
                "请电话送货上门谢谢【3612】",
            ),
            _row(
                "record-2",
                "欢宝零食店",
                "仅存历史",
                "写入失败",
                "6952003434324366111",
                "田宝山",
                "田宝山15784081541山东省德州市",
                "请放门口",
            ),
        ]
    )
    page.list_widget.setCurrentRow(1)

    emitted = {"delete": [], "save": [], "expense": []}
    page.delete_requested.connect(emitted["delete"].append)
    page.save_requested.connect(lambda record_id, patch: emitted["save"].append(record_id))
    page.expense_requested.connect(emitted["expense"].append)

    page.delete_button.click()
    page.save_button.click()
    page.expense_button.click()

    assert emitted == {
        "delete": ["record-2"],
        "save": ["record-2"],
        "expense": ["record-2"],
    }


def test_history_page_loads_and_saves_financial_fields(qtbot):
    page = HistoryPage()
    qtbot.addWidget(page)
    rows = [
        _row(
            "record-1",
            "乐宝零食店",
            "确认写入飞书",
            "已写入飞书",
            "6952003434324366473",
            "何女士",
            "何女士15781304332四川省成都市",
            "请电话送货上门谢谢【3612】",
        )
    ]

    page.load_rows(rows)
    emitted = []
    page.save_requested.connect(lambda record_id, patch: emitted.append((record_id, patch)))

    assert page.platform_fee_rate_value.text() == "10"
    assert page.platform_fee_amount_value.text() == "16.20"
    assert page.gross_profit_value.text() == "101.80"
    assert page.custom_cost_value_1.text() == "1.00"

    page.platform_fee_rate_value.setText("12")
    page.save_button.click()

    assert emitted[0][0] == "record-1"
    assert emitted[0][1]["order_snapshot"]["platform_fee_rate"] == "12"
    assert emitted[0][1]["order_snapshot"]["platform_fee_amount"] == "19.44"
    assert emitted[0][1]["order_snapshot"]["gross_profit"] == "98.56"
    assert emitted[0][1]["order_snapshot"]["custom_cost_values"] == ["1.00", "", ""]


def test_history_page_saves_after_sale_refund_and_recalculates_income_and_profit(qtbot):
    page = HistoryPage()
    qtbot.addWidget(page)
    rows = [
        _row(
            "record-1",
            "乐宝零食店",
            "确认写入飞书",
            "已写入飞书",
            "6952003434324366473",
            "何女士",
            "何女士15781304332四川省成都市",
            "请电话送货上门谢谢【3612】",
        )
    ]

    page.load_rows(rows)
    emitted = []
    page.save_requested.connect(lambda record_id, patch: emitted.append((record_id, patch)))

    page.after_sale_type_value.setCurrentText("仅退款")
    page.after_sale_status_value.setCurrentText("已退款")
    page.after_sale_amount_value.setText("10")
    page.after_sale_date_value.setText("2026-04-16")
    page.after_sale_goods_returned_value.setCurrentText("是")
    page.after_sale_resellable_value.setCurrentText("否")
    page.after_sale_note_value.setPlainText("客户退货退款 10 元")
    page.save_button.click()

    snapshot = emitted[0][1]["order_snapshot"]
    assert snapshot["after_sale_type"] == "仅退款"
    assert snapshot["after_sale_status"] == "已退款"
    assert snapshot["after_sale_amount"] == "10"
    assert snapshot["after_sale_date"] == "2026-04-16"
    assert snapshot["after_sale_goods_returned"] == "是"
    assert snapshot["after_sale_resellable"] == "否"
    assert snapshot["after_sale_note"] == "客户退货退款 10 元"
    assert snapshot["after_sale_base_income"] == "162.00"
    assert snapshot["income_amount"] == "152.00"
    assert snapshot["platform_fee_amount"] == "15.20"
    assert snapshot["gross_profit"] == "92.80"


def test_history_page_auto_fills_full_return_refund_and_zeroes_procurement_cost(qtbot):
    page = HistoryPage()
    qtbot.addWidget(page)
    rows = [
        _row(
            "record-1",
            "乐宝零食店",
            "确认写入飞书",
            "已写入飞书",
            "6952003434324366473",
            "何女士",
            "何女士15781304332四川省成都市",
            "请电话送货上门谢谢【3612】",
        )
    ]

    page.load_rows(rows)

    page.after_sale_type_value.setCurrentText("退货退款")

    assert page.after_sale_status_value.currentText() == "已退货"
    assert page.after_sale_amount_value.text() == "162.00"
    assert page.after_sale_goods_returned_value.currentText() == "是"
    assert page.procurement_total_cost_value.text() == "0.00"
    assert page.platform_fee_amount_value.text() == "0.00"
    assert page.gross_profit_value.text() == "-6.00"

    emitted = []
    page.save_requested.connect(lambda record_id, patch: emitted.append((record_id, patch)))
    page.save_button.click()

    snapshot = emitted[0][1]["order_snapshot"]
    assert snapshot["after_sale_type"] == "退货退款"
    assert snapshot["after_sale_status"] == "已退货"
    assert snapshot["after_sale_amount"] == "162.00"
    assert snapshot["after_sale_goods_returned"] == "是"
    assert snapshot["income_amount"] == "0.00"
    assert snapshot["platform_fee_amount"] == "0.00"
    assert snapshot["procurement_total_cost"] == "0.00"
    assert snapshot["gross_profit"] == "-6.00"


def test_history_page_keeps_procurement_cost_when_full_return_refund_goods_not_returned(qtbot):
    page = HistoryPage()
    qtbot.addWidget(page)
    rows = [
        _row(
            "record-1",
            "乐宝零食店",
            "确认写入飞书",
            "已写入飞书",
            "6952003434324366473",
            "何女士",
            "何女士15781304332四川省成都市",
            "请电话送货上门谢谢【3612】",
        )
    ]

    page.load_rows(rows)
    page.after_sale_type_value.setCurrentText("退货退款")
    page.after_sale_goods_returned_value.setCurrentText("否")

    assert page.after_sale_goods_returned_value.currentText() == "否"
    assert page.procurement_total_cost_value.text() == "38.00"
    assert page.platform_fee_amount_value.text() == "0.00"
    assert page.gross_profit_value.text() == "-44.00"


def test_history_page_treats_decimal_fee_rate_as_direct_multiplier(qtbot):
    page = HistoryPage()
    qtbot.addWidget(page)
    rows = [
        _row(
            "record-1",
            "乐宝零食店",
            "确认写入飞书",
            "已写入飞书",
            "6952003434324366473",
            "何女士",
            "何女士15781304332四川省成都市",
            "请电话送货上门谢谢【3612】",
        )
    ]
    rows[0]["order_snapshot"]["platform_fee_rate"] = "0.06"
    rows[0]["order_snapshot"]["platform_fee_amount"] = "9.72"
    rows[0]["order_snapshot"]["gross_profit"] = "108.28"

    page.load_rows(rows)
    emitted = []
    page.save_requested.connect(lambda record_id, patch: emitted.append((record_id, patch)))

    page.platform_fee_rate_value.setText("0.06")
    page.save_button.click()

    assert emitted[0][1]["order_snapshot"]["platform_fee_amount"] == "9.72"


def test_history_page_defaults_blank_fee_rate_to_point_zero_six(qtbot):
    page = HistoryPage()
    qtbot.addWidget(page)
    rows = [
        _row(
            "record-1",
            "乐宝零食店",
            "确认写入飞书",
            "已写入飞书",
            "6952003434324366473",
            "何女士",
            "何女士15781304332四川省成都市",
            "请电话送货上门谢谢【3612】",
        )
    ]
    rows[0]["order_snapshot"]["platform_fee_rate"] = ""
    rows[0]["order_snapshot"]["platform_fee_amount"] = ""

    page.load_rows(rows)

    assert page.platform_fee_rate_value.text() == "0.06"
    assert page.platform_fee_amount_value.text() == "9.72"


def test_history_page_directly_edits_fields_and_emits_save_patch(qtbot):
    page = HistoryPage()
    qtbot.addWidget(page)
    page.load_rows(
        [
            _row(
                "record-1",
                "乐宝零食店",
                "确认写入飞书",
                "已写入飞书",
                "6952003434324366473",
                "何女士",
                "何女士15781304332四川省成都市",
                "请电话送货上门谢谢【3612】",
            )
        ]
    )

    assert page.order_id_value.isReadOnly() is False
    assert page.platform_value.isReadOnly() is False
    assert page.product_name_value.isReadOnly() is False
    assert page.save_button.isEnabled() is True

    emitted = []
    page.save_requested.connect(lambda record_id, patch: emitted.append((record_id, patch)))

    page.product_name_value.setPlainText("改后商品")
    page.procurement_product_1_combo.setCurrentText("改后采购")
    page.procurement_quantity_1_value.setText("3")
    page.procurement_cost_1_value.setText("21.50")
    page.save_button.click()

    assert emitted[0][0] == "record-1"
    snapshot = emitted[0][1]["order_snapshot"]
    assert snapshot["product_name"] == "改后商品"
    assert snapshot["procurement_items"][0] == {
        "product_name": "改后采购",
        "quantity": "3",
        "cost": "21.50",
    }
    assert snapshot["platform_fee_rate"] == "10"
    assert snapshot["platform_fee_amount"] == "16.20"
    assert snapshot["procurement_total_cost"] == "64.50"
    assert snapshot["gross_profit"] == "75.30"


def test_history_page_save_button_stays_near_detail_header(qtbot):
    page = HistoryPage()
    qtbot.addWidget(page)
    page.load_rows(
        [
            _row(
                "record-1",
                "乐宝零食店",
                "确认写入飞书",
                "已写入飞书",
                "6952003434324366473",
                "何女士",
                "何女士15781304332四川省成都市",
                "请电话送货上门谢谢【3612】",
            )
        ]
    )

    assert page.header_actions_widget.isHidden() is False
    assert page.left_column_widget.layout().count() == 1
    assert page.save_button.text() == "保存修改并重新写入飞书"
    assert page.resubmit_button.isHidden() is True
    sticky_bar = page.findChild(QFrame, "HistoryStickyActionBar")
    detail_scroll = page.findChild(QScrollArea, "HistoryDetailScroll")
    assert sticky_bar is not None
    assert detail_scroll is not None
    assert sticky_bar.parent() is not detail_scroll.widget()


def test_history_page_filters_by_quick_range_shop_status_and_specific_date(qtbot):
    page = HistoryPage()
    qtbot.addWidget(page)
    rows = [
        _row(
            "record-today",
            "乐宝零食店",
            "确认写入飞书",
            "已写入飞书",
            "6952003434324366473",
            "何女士",
            "何女士15781304332四川省成都市",
            "请电话送货上门谢谢【3612】",
        ),
        _row(
            "record-yesterday",
            "欢宝零食店",
            "仅存历史",
            "写入失败",
            "6952003434324366111",
            "田宝山",
            "田宝山15784081541山东省德州市",
            "请放门口",
        ),
    ]
    today = date.today()
    yesterday = today - timedelta(days=1)

    rows[0]["order_snapshot"]["placed_at"] = f"{today.isoformat()} 09:00:00"
    rows[0]["order_snapshot"]["order_status"] = "已发货"
    rows[1]["order_snapshot"]["placed_at"] = f"{yesterday.isoformat()} 10:30:00"
    rows[1]["order_snapshot"]["order_status"] = "待发货"

    page.load_rows(rows)

    page.quick_filter_buttons["今天"].click()
    assert page.list_widget.count() == 1
    assert "record-today" in page._filtered_rows[0]["record_id"]

    page.shop_filter_combo.setCurrentText("欢宝零食店")
    page.status_filter_combo.setCurrentText("待发货")
    page.apply_filters_button.click()
    assert page.list_widget.count() == 0

    page.quick_filter_buttons["全部"].click()
    page.date_filter_edit.setDate(page.date_filter_edit.date().fromString(yesterday.isoformat(), "yyyy-MM-dd"))
    page.shop_filter_combo.setCurrentText("欢宝零食店")
    page.status_filter_combo.setCurrentText("待发货")
    page.apply_filters_button.click()
    assert page.list_widget.count() == 1
    assert page.detail_title_label.text() == "欢宝零食店"

    page.clear_filters_button.click()
    assert page.list_widget.count() == 2


def test_history_page_defaults_fee_rate_to_point_zero_six_when_empty(qtbot):
    page = HistoryPage()
    qtbot.addWidget(page)

    assert page.platform_fee_rate_value.text() == "0.06"


def test_history_page_uses_product_presets_for_procurement_editing(qtbot):
    page = HistoryPage()
    qtbot.addWidget(page)
    page.set_product_presets(
        [
            {"name": "27000-澳洲版-1升装", "default_cost": "109"},
            {"name": "康兴-瓶盖-粉色", "default_cost": "13.80"},
        ]
    )
    page.load_rows(
        [
            _row(
                "record-1",
                "乐宝零食店",
                "确认写入飞书",
                "已写入飞书",
                "6952003434324366473",
                "何女士",
                "何女士15781304332四川省成都市",
                "请电话送货上门谢谢【3612】",
            )
        ]
    )
    emitted = []
    page.save_requested.connect(lambda record_id, patch: emitted.append((record_id, patch)))

    assert page.procurement_product_1_combo.currentText() == "澳洲婴儿水"
    page.procurement_product_2_combo.setCurrentText("康兴-瓶盖-粉色")

    assert page.procurement_cost_2_value.text() == "13.80"
    assert page.procurement_quantity_2_value.text() == "1"

    page.save_button.click()

    assert emitted[0][1]["order_snapshot"]["procurement_items"][1] == {
        "product_name": "康兴-瓶盖-粉色",
        "quantity": "1",
        "cost": "13.80",
    }


def test_history_page_recalculates_totals_live_when_procurement_changes(qtbot):
    page = HistoryPage()
    qtbot.addWidget(page)
    page.set_product_presets(
        [
            {"name": "27000-澳洲版-1升装", "default_cost": "109"},
            {"name": "康兴-瓶盖-粉色", "default_cost": "13.80"},
        ]
    )
    page.load_rows(
        [
            _row(
                "record-1",
                "乐宝零食店",
                "确认写入飞书",
                "已写入飞书",
                "6952003434324366473",
                "何女士",
                "何女士15781304332四川省成都市",
                "请电话送货上门谢谢【3612】",
            )
        ]
    )

    assert page.procurement_total_cost_value.text() == "38.00"
    assert page.gross_profit_value.text() == "101.80"

    page.procurement_product_2_combo.setCurrentText("康兴-瓶盖-粉色")

    assert page.procurement_cost_2_value.text() == "13.80"
    assert page.procurement_total_cost_value.text() == "51.80"


def test_history_page_keeps_blank_procurement_slots_blank_when_saving(qtbot):
    page = HistoryPage()
    qtbot.addWidget(page)
    page.load_rows(
        [
            _row(
                "record-1",
                "乐宝零食店",
                "确认写入飞书",
                "已写入飞书",
                "6952003434324366473",
                "何女士",
                "何女士15781304332四川省成都市",
                "请电话送货上门谢谢【3612】",
            )
        ]
    )
    emitted = []
    page.save_requested.connect(lambda record_id, patch: emitted.append((record_id, patch)))

    page.procurement_product_2_combo.setCurrentText("")
    page.procurement_quantity_2_value.setText("")
    page.procurement_cost_2_value.setText("")
    page.procurement_tracking_2_value.setText("")
    page.save_button.click()

    assert emitted[0][1]["order_snapshot"]["procurement_items"][1] == {
        "product_name": "",
        "quantity": "",
        "cost": "",
    }
    assert page.gross_profit_value.text() == "101.80"


def test_history_page_can_filter_by_procurement_tracking_number(qtbot):
    page = HistoryPage()
    qtbot.addWidget(page)
    rows = [
        _row(
            "record-1",
            "乐宝零食店",
            "确认写入飞书",
            "已写入飞书",
            "6952003434324366473",
            "何女士",
            "何女士15781304332四川省成都市",
            "请电话送货上门谢谢【3612】",
        ),
        _row(
            "record-2",
            "欢宝零食店",
            "仅存历史",
            "写入失败",
            "6952003434324366111",
            "田宝山",
            "田宝山15784081541山东省德州市",
            "请放门口",
        ),
    ]
    rows[0]["order_snapshot"]["procurement_tracking_number"] = "SF5566778899"
    rows[1]["order_snapshot"]["procurement_tracking_number"] = "YT111222333"

    page.load_rows(rows)
    page.keyword_filter_edit.setText("SF5566778899")
    page.apply_filters_button.click()

    assert page.list_widget.count() == 1
    assert page.detail_title_label.text() == "乐宝零食店"


def test_history_page_can_filter_by_procurement_item_tracking_number(qtbot):
    page = HistoryPage()
    qtbot.addWidget(page)
    rows = [
        _row(
            "record-1",
            "乐宝零食店",
            "确认写入飞书",
            "已写入飞书",
            "6952003434324366473",
            "何女士",
            "何女士15781304332四川省成都市",
            "请电话送货上门谢谢【3612】",
        )
    ]
    rows[0]["order_snapshot"]["procurement_items"][1]["tracking_number"] = "YT555888999"

    page.load_rows(rows)
    page.keyword_filter_edit.setText("YT555888999")
    page.apply_filters_button.click()

    assert page.list_widget.count() == 1
    assert page.detail_title_label.text() == "乐宝零食店"


def test_history_page_status_cards_show_counts_and_filter_rows(qtbot):
    page = HistoryPage()
    qtbot.addWidget(page)
    rows = [
        _row(
            "record-shipped",
            "乐宝零食店",
            "确认写入飞书",
            "已写入飞书",
            "6952003434324366473",
            "何女士",
            "何女士15781304332四川省成都市",
            "请电话送货上门谢谢【3612】",
        ),
        _row(
            "record-pending",
            "欢宝零食店",
            "仅存历史",
            "仅存历史",
            "6952003434324366111",
            "田宝山",
            "田宝山15784081541山东省德州市",
            "请放门口",
        ),
        _row(
            "record-shot",
            "灵宝零食店",
            "确认写入飞书",
            "已写入飞书",
            "6952003434324366999",
            "王先生",
            "王先生13900001111广东省深圳市",
            "请尽快发货",
        ),
    ]
    rows[0]["order_snapshot"]["placed_at"] = "2026-04-14 09:00:00"
    rows[0]["order_snapshot"]["order_status"] = "已发货"
    rows[1]["order_snapshot"]["placed_at"] = "2026-04-14 10:30:00"
    rows[1]["order_snapshot"]["order_status"] = "待发货"
    rows[2]["order_snapshot"]["placed_at"] = "2026-04-14 11:30:00"
    rows[2]["order_snapshot"]["order_status"] = "已拍单未发货"

    page.load_rows(rows)

    assert page.status_summary_buttons["已发货"].value_label.text() == "1"
    assert page.status_summary_buttons["待发货"].value_label.text() == "1"
    assert page.status_summary_buttons["已拍单未发货"].value_label.text() == "1"

    qtbot.mouseClick(page.status_summary_buttons["待发货"], Qt.MouseButton.LeftButton)

    assert page.status_filter_combo.currentText() == "待发货"
    assert page.list_widget.count() == 1
    assert page.detail_title_label.text() == "欢宝零食店"


def test_history_page_keeps_left_column_compact(qtbot):
    page = HistoryPage()
    qtbot.addWidget(page)

    assert page.left_column_widget.maximumWidth() <= 460
