from strawberry_order_management.models import ParsedOrder
from strawberry_order_management.ui.pages.intake_page import IntakePage
from strawberry_order_management.ui.widgets.address_extractor_widget import (
    AddressExtractorWidget,
)


def test_intake_page_shows_order_card_after_pipeline_result(qtbot):
    submitted_orders = []
    page = IntakePage(on_submit=submitted_orders.append)
    qtbot.addWidget(page)

    order = ParsedOrder(
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

    page.show_order(order)
    page.submit_button.click()

    assert page.order_card_widget.order_id_value.text() == "6952003434324366473"
    assert page.order_card_widget.recipient_name_value.text() == "何女士"
    assert page.order_card_widget.phone_number_value.text() == "15781304332"
    assert page.order_card_widget.code_value.text() == "3612"
    assert page.order_card_widget.address_value.text() == "四川省成都市金牛区营门口街道友谊花园9-2304"
    assert page.order_card_widget.delivery_note_value.text() == "请电话送货上门谢谢【3612】"
    assert isinstance(page.address_widget, AddressExtractorWidget)
    assert page.submit_button.text() == "确认写入飞书"
    assert submitted_orders == [order]
