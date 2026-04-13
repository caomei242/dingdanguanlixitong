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
        "order_snapshot": {
            "order_id": order_id,
            "recipient_name": recipient_name,
        },
        "address_snapshot": {
            "output_one": address_one,
            "output_two": address_two,
        },
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

    page.edit_button.click()
    page.delete_button.click()
    page.resubmit_button.click()

    assert emitted == {
        "edit": ["record-2"],
        "delete": ["record-2"],
        "resubmit": ["record-2"],
    }
