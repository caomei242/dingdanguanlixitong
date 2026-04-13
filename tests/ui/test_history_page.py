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
            )
        ]
    )

    emitted = {"edit": [], "delete": [], "resubmit": []}
    page.edit_requested.connect(emitted["edit"].append)
    page.delete_requested.connect(emitted["delete"].append)
    page.resubmit_requested.connect(emitted["resubmit"].append)

    page.edit_button.click()
    page.delete_button.click()
    page.resubmit_button.click()

    assert emitted == {
        "edit": ["record-1"],
        "delete": ["record-1"],
        "resubmit": ["record-1"],
    }
