from PySide6.QtCore import Qt

from strawberry_order_management.ui.pages.expense_page import ExpensePage


def _history_row(*, record_id: str, shop_name: str, order_id: str, recipient: str, platform: str = "抖店") -> dict:
    return {
        "record_id": record_id,
        "shop_name": shop_name,
        "order_snapshot": {
            "order_id": order_id,
            "recipient_name": recipient,
            "platform": platform,
            "order_status": "已发货",
        },
    }


def _expense_row(
    *,
    record_id: str,
    expense_date: str,
    scope_type: str,
    shop_name: str,
    order_id: str,
    category: str,
    amount: str,
    remark: str,
) -> dict:
    return {
        "record_id": record_id,
        "expense_date": expense_date,
        "scope_type": scope_type,
        "shop_name": shop_name,
        "order_id": order_id,
        "platform": "抖店",
        "category": category,
        "amount": amount,
        "remark": remark,
        "created_at": "2026-04-15 11:00:00",
        "updated_at": "2026-04-15 11:00:00",
    }


def test_expense_page_can_build_order_scope_payload_and_emit_save(qtbot):
    page = ExpensePage()
    qtbot.addWidget(page)
    page.set_shop_names(["乐宝零食店", "欢宝零食店"])
    page.set_order_rows(
        [
            _history_row(
                record_id="row-1",
                shop_name="乐宝零食店",
                order_id="6952059303468209543",
                recipient="丽",
            )
        ]
    )

    captured: list[tuple[str, dict]] = []
    page.save_requested.connect(lambda record_id, payload: captured.append((record_id, payload)))

    page.category_combo.setEditText("售后补偿")
    page.amount_edit.setText("10.00")
    page.remark_edit.setPlainText("客户维护返现")
    page.order_combo.setCurrentIndex(0)

    qtbot.mouseClick(page.save_button, Qt.MouseButton.LeftButton)

    assert captured == [
        (
            "",
            {
                "expense_date": page.expense_date_edit.date().toString("yyyy-MM-dd"),
                "scope_type": "订单级",
                "shop_name": "乐宝零食店",
                "order_id": "6952059303468209543",
                "platform": "抖店",
                "category": "售后补偿",
                "amount": "10.00",
                "remark": "客户维护返现",
            },
        )
    ]


def test_expense_page_filters_rows_and_updates_detail(qtbot):
    page = ExpensePage()
    qtbot.addWidget(page)
    page.set_shop_names(["乐宝零食店", "欢宝零食店"])
    page.load_rows(
        [
            _expense_row(
                record_id="expense-1",
                expense_date="2026-04-15",
                scope_type="订单级",
                shop_name="乐宝零食店",
                order_id="6952059303468209543",
                category="售后补偿",
                amount="10.00",
                remark="订单返现",
            ),
            _expense_row(
                record_id="expense-2",
                expense_date="2026-04-14",
                scope_type="店铺级",
                shop_name="欢宝零食店",
                order_id="",
                category="软件服务",
                amount="99.00",
                remark="自动发货月费",
            ),
        ]
    )

    page.search_edit.setText("软件")
    qtbot.mouseClick(page.apply_filters_button, Qt.MouseButton.LeftButton)

    assert page.list_widget.count() == 1
    assert "软件服务" in page.list_widget.item(0).text()
    assert page.detail_title_label.text() == "软件服务"
    assert page.detail_amount_chip.value_label.text() == "¥99.00"
    assert "店铺经营开支" in page.detail_effect_label.text()
