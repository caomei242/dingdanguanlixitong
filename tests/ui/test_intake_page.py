import time

from PySide6.QtGui import QColor, QGuiApplication, QImage
from PySide6.QtWidgets import QFrame, QScrollArea

from strawberry_order_management.models import ParsedOrder, ProcurementItem
from strawberry_order_management import app as app_module
from strawberry_order_management.ui.pages.intake_page import IntakePage
from strawberry_order_management.ui.widgets.address_extractor_widget import (
    AddressExtractorWidget,
)
from strawberry_order_management.ui.widgets.screenshot_input_widget import (
    ScreenshotInputWidget,
)


def test_intake_page_shows_order_card_after_pipeline_result(qtbot):
    submitted_orders = []
    page = IntakePage(on_submit=submitted_orders.append, use_background_thread=False)
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
    page.shop_selector.addItems(["草莓店"])
    page.shop_selector.setCurrentText("草莓店")
    page.submit_button.click()

    assert page.order_card_widget.order_id_edit.text() == "6952003434324366473"
    assert page.order_card_widget.recipient_name_edit.text() == "何女士"
    assert page.order_card_widget.phone_number_edit.text() == "15781304332"
    assert page.order_card_widget.code_edit.text() == "3612"
    assert page.order_card_widget.address_edit.toPlainText() == "四川省成都市金牛区营门口街道友谊花园9-2304"
    assert page.order_card_widget.delivery_note_edit.toPlainText() == "请电话送货上门谢谢【3612】"
    assert isinstance(page.address_widget, AddressExtractorWidget)
    assert page.submit_button.text() == "确认写入飞书"
    assert submitted_orders == [{"shop_name": "草莓店", "order": order}]


def test_screenshot_input_widget_reads_image_from_clipboard(qtbot):
    widget = ScreenshotInputWidget()
    qtbot.addWidget(widget)

    emitted = []
    widget.image_ready.connect(lambda image_bytes, source: emitted.append((image_bytes, source)))

    image = QImage(12, 12, QImage.Format.Format_RGB32)
    image.fill(QColor("#ff4b6e"))
    QGuiApplication.clipboard().setImage(image)

    widget.paste_button.click()

    assert emitted
    assert emitted[0][0].startswith(b"\x89PNG")
    assert emitted[0][1] == "剪贴板截图"
    assert widget.status_label.text() == "已读取剪贴板截图"


def test_intake_page_processes_image_into_order_card_and_address_outputs(qtbot):
    calls = []

    def process_image(image_bytes: bytes):
        calls.append(image_bytes)
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

    page = IntakePage(on_process_image=process_image, use_background_thread=False)
    qtbot.addWidget(page)

    page.process_image_bytes(b"fake-image", "剪贴板截图")

    assert calls == [b"fake-image"]
    assert page.capture_widget.status_label.text() == "已完成剪贴板截图识别"
    assert page.order_card_widget.order_id_edit.text() == "6952003434324366473"
    assert page.address_widget.output_one.toPlainText() == (
        "何女士15781304332四川省成都市金牛区营门口街道友谊花园9-2304"
    )
    assert page.address_widget.output_two.toPlainText() == "请电话送货上门谢谢【3612】"


def test_intake_page_processes_image_in_background_without_blocking(qtbot):
    def process_image(image_bytes: bytes):
        time.sleep(0.05)
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

    page = IntakePage(on_process_image=process_image, use_background_thread=True)
    qtbot.addWidget(page)

    page.process_image_bytes(b"fake-image", "剪贴板截图")

    assert "识别中" in page.capture_widget.status_label.text()
    assert page.address_widget.isEnabled()
    qtbot.waitUntil(
        lambda: page.order_card_widget.order_id_edit.text() == "6952003434324366473",
        timeout=2000,
    )


def test_intake_page_emits_modified_order_for_history_only(qtbot):
    saved_payloads = []
    page = IntakePage(
        on_save_history=saved_payloads.append,
        use_background_thread=False,
    )
    qtbot.addWidget(page)

    page.shop_selector.addItems(["草莓店"])
    page.shop_selector.setCurrentText("草莓店")
    page.show_order(
        ParsedOrder(
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
    )
    page.order_card_widget.product_name_edit.setPlainText("手动改过的商品名")

    page.save_history_button.click()

    assert saved_payloads[0]["shop_name"] == "草莓店"
    assert saved_payloads[0]["order"].product_name == "手动改过的商品名"


def test_app_main_creates_and_shows_main_window(monkeypatch):
    events = {"shown": False, "exec_called": False}

    class FakeWindow:
        def __init__(self, *args, **kwargs):
            pass

        def show(self):
            events["shown"] = True

    class FakeApp:
        def exec(self):
            events["exec_called"] = True
            return 0

    monkeypatch.setattr(app_module, "build_app", lambda: FakeApp())
    monkeypatch.setattr(app_module, "MainWindow", FakeWindow)

    assert app_module.main() == 0
    assert events == {"shown": True, "exec_called": True}


def test_intake_page_wraps_content_in_scroll_area(qtbot):
    page = IntakePage(use_background_thread=False)
    qtbot.addWidget(page)

    scroll_area = page.findChild(QScrollArea)

    assert scroll_area is not None
    assert scroll_area.widgetResizable() is True
    assert scroll_area.frameShape() == QFrame.Shape.NoFrame
    assert scroll_area.widget().objectName() == "PageContent"


def test_order_card_autofills_procurement_cost_from_selected_preset(qtbot):
    page = IntakePage(use_background_thread=False)
    qtbot.addWidget(page)

    page.set_product_presets([{"name": "澳洲婴儿水", "default_cost": "18.50"}])
    page.show_order(
        ParsedOrder(
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
            procurement_items=(
                ProcurementItem("", "1", ""),
                ProcurementItem("", "1", ""),
                ProcurementItem("", "1", ""),
            ),
        )
    )

    page.order_card_widget.procurement_product_1_combo.setCurrentText("澳洲婴儿水")

    assert page.order_card_widget.procurement_quantity_1_edit.text() == "1"
    assert page.order_card_widget.procurement_cost_1_edit.text() == "18.50"


def test_intake_page_emits_procurement_slots_with_order_payload(qtbot):
    submitted_orders = []
    page = IntakePage(on_submit=submitted_orders.append, use_background_thread=False)
    qtbot.addWidget(page)

    page.set_product_presets([{"name": "澳洲婴儿水", "default_cost": "18.50"}])
    page.shop_selector.addItems(["草莓店"])
    page.shop_selector.setCurrentText("草莓店")
    page.show_order(
        ParsedOrder(
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
            procurement_items=(
                ProcurementItem("", "1", ""),
                ProcurementItem("", "1", ""),
                ProcurementItem("", "1", ""),
            ),
        )
    )

    page.order_card_widget.procurement_product_1_combo.setCurrentText("澳洲婴儿水")
    page.order_card_widget.procurement_quantity_1_edit.setText("2")
    page.order_card_widget.procurement_cost_1_edit.setText("19.00")
    page.submit_button.click()

    assert submitted_orders[0]["order"].procurement_items[0] == ProcurementItem(
        "澳洲婴儿水",
        "2",
        "19.00",
    )


def test_order_card_can_request_saving_manual_product_to_library(qtbot):
    saved_products = []
    page = IntakePage(use_background_thread=False)
    qtbot.addWidget(page)
    page.product_library_requested.connect(
        lambda name, cost: saved_products.append((name, cost))
    )
    page.show_order(
        ParsedOrder(
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
    )

    page.order_card_widget.procurement_product_1_combo.setEditText("新商品")
    page.order_card_widget.procurement_cost_1_edit.setText("12.60")
    page.order_card_widget.procurement_save_1_button.click()

    assert saved_products == [("新商品", "12.60")]
