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
            "order_status": "已发货",
            "product_name": "澳大利亚进口婴儿水",
            "quantity": "1",
            "order_amount": "405.00",
            "income_amount": "162.00",
            "recipient_name": recipient_name,
            "phone_number": "15781304332",
            "code": "3612",
            "address": "四川省成都市金牛区营门口街道友谊花园9-2304",
            "delivery_note": "请电话送货上门谢谢【3612】",
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
    assert page.detail_subtitle_label.text() == "仅存历史 · 已写入飞书"
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
            "草莓店",
            "确认写入飞书",
            "已写入飞书",
            "6952003434324366473",
            "何女士",
            "何女士15781304332四川省成都市",
            "请电话送货上门谢谢【3612】",
        ),
        _row(
            "record-2",
            "乐宝零食店",
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
    assert page.detail_title_label.text() == "草莓店"
    assert page.detail_subtitle_label.text() == "确认写入飞书 · 已写入飞书"
    assert page.order_id_value.toPlainText() == "6952003434324366473"
    assert page.recipient_name_value.toPlainText() == "何女士"
    assert page.address_output_one.toPlainText() == "何女士15781304332四川省成都市"
    assert page.address_output_two.toPlainText() == "请电话送货上门谢谢【3612】"

    page.list_widget.setCurrentRow(1)

    assert page.detail_title_label.text() == "乐宝零食店"
    assert page.detail_subtitle_label.text() == "仅存历史 · 写入失败"
    assert page.order_id_value.toPlainText() == "6952003434324366111"
    assert page.recipient_name_value.toPlainText() == "田宝山"
    assert page.address_output_one.toPlainText() == "田宝山15784081541山东省德州市"
    assert page.address_output_two.toPlainText() == "请放门口"
    assert page.total_count_value.text() == "2"
    assert page.written_count_value.text() == "1"
    assert page.failed_count_value.text() == "1"
    assert page.action_card.isHidden() is False
    assert page.detail_summary_card.isHidden() is False


def test_history_page_keeps_selected_record_when_rows_refresh(qtbot):
    page = HistoryPage()
    qtbot.addWidget(page)

    rows = [
        _row(
            "record-1",
            "草莓店",
            "确认写入飞书",
            "已写入飞书",
            "6952003434324366473",
            "何女士",
            "何女士15781304332四川省成都市",
            "请电话送货上门谢谢【3612】",
        ),
        _row(
            "record-2",
            "乐宝零食店",
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
    assert page.detail_title_label.text() == "乐宝零食店"
    assert page.detail_subtitle_label.text() == "仅存历史 · 写入失败"


def test_history_page_falls_back_to_adjacent_record_when_selected_row_is_deleted(qtbot):
    page = HistoryPage()
    qtbot.addWidget(page)

    rows = [
        _row(
            "record-1",
            "草莓店",
            "确认写入飞书",
            "已写入飞书",
            "6952003434324366473",
            "何女士",
            "何女士15781304332四川省成都市",
            "请电话送货上门谢谢【3612】",
        ),
        _row(
            "record-2",
            "乐宝零食店",
            "仅存历史",
            "写入失败",
            "6952003434324366111",
            "田宝山",
            "田宝山15784081541山东省德州市",
            "请放门口",
        ),
        _row(
            "record-3",
            "橙子店",
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
    assert page.detail_title_label.text() == "橙子店"
    assert page.detail_subtitle_label.text() == "仅存历史 · 已写入飞书"


def test_history_page_emits_record_ids_for_actions(qtbot):
    page = HistoryPage()
    qtbot.addWidget(page)
    page.load_rows(
        [
            _row(
                "record-1",
                "草莓店",
                "确认写入飞书",
                "已写入飞书",
                "6952003434324366473",
                "何女士",
                "何女士15781304332四川省成都市",
                "请电话送货上门谢谢【3612】",
            ),
            _row(
                "record-2",
                "乐宝零食店",
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

    emitted = {"edit": [], "delete": [], "resubmit": []}
    page.edit_requested.connect(emitted["edit"].append)
    page.delete_requested.connect(emitted["delete"].append)
    page.resubmit_requested.connect(emitted["resubmit"].append)

    page.delete_button.click()
    page.resubmit_button.click()
    page.edit_button.click()

    assert emitted == {
        "edit": ["record-2"],
        "delete": ["record-2"],
        "resubmit": ["record-2"],
    }


def test_history_page_toggles_edit_mode_and_emits_save_patch(qtbot):
    page = HistoryPage()
    qtbot.addWidget(page)
    page.load_rows(
        [
            _row(
                "record-1",
                "草莓店",
                "确认写入飞书",
                "已写入飞书",
                "6952003434324366473",
                "何女士",
                "何女士15781304332四川省成都市",
                "请电话送货上门谢谢【3612】",
            )
        ]
    )

    assert page.is_editing is False
    assert page.edit_button.isEnabled() is True
    assert page.save_button.isEnabled() is False
    assert page.cancel_button.isEnabled() is False

    emitted = []
    page.save_requested.connect(lambda record_id, patch: emitted.append((record_id, patch)))

    page.edit_button.click()

    assert page.is_editing is True
    assert page.edit_button.isEnabled() is False
    assert page.delete_button.isEnabled() is False
    assert page.resubmit_button.isEnabled() is False
    assert page.save_button.isEnabled() is True
    assert page.cancel_button.isEnabled() is True
    assert page.product_name_value.isReadOnly() is False
    assert page.procurement_product_1_value.isReadOnly() is False

    page.product_name_value.setPlainText("改后商品")
    page.procurement_product_1_value.setPlainText("改后采购")
    page.procurement_quantity_1_value.setPlainText("3")
    page.procurement_cost_1_value.setPlainText("21.50")
    page.save_button.click()

    assert emitted == [
        (
            "record-1",
            {
                "order_snapshot": {
                    "order_id": "6952003434324366473",
                    "placed_at": "2026-04-11 20:57:15",
                    "order_status": "已发货",
                    "product_name": "改后商品",
                    "quantity": "1",
                    "order_amount": "405.00",
                    "income_amount": "162.00",
                    "recipient_name": "何女士",
                    "phone_number": "15781304332",
                    "code": "3612",
                    "address": "四川省成都市金牛区营门口街道友谊花园9-2304",
                    "delivery_note": "请电话送货上门谢谢【3612】",
                    "procurement_items": [
                        {"product_name": "改后采购", "quantity": "3", "cost": "21.50"},
                        {"product_name": "", "quantity": "1", "cost": ""},
                        {"product_name": "", "quantity": "1", "cost": ""},
                    ],
                }
            },
        )
    ]
    assert page.is_editing is False
    assert page.edit_button.isEnabled() is True
    assert page.save_button.isEnabled() is False
    assert page.cancel_button.isEnabled() is False


def test_history_page_cancel_restores_snapshot_without_emitting_save(qtbot):
    page = HistoryPage()
    qtbot.addWidget(page)
    page.load_rows(
        [
            _row(
                "record-1",
                "草莓店",
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

    page.edit_button.click()
    page.recipient_name_value.setPlainText("临时改名")
    page.delivery_note_value.setPlainText("临时备注")

    page.cancel_button.click()

    assert emitted == []
    assert page.is_editing is False
    assert page.recipient_name_value.toPlainText() == "何女士"
    assert page.delivery_note_value.toPlainText() == "请电话送货上门谢谢【3612】"
