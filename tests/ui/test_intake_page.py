from PySide6.QtGui import QColor, QGuiApplication, QImage

from strawberry_order_management.models import ParsedOrder
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

    page = IntakePage(on_process_image=process_image)
    qtbot.addWidget(page)

    page.process_image_bytes(b"fake-image", "剪贴板截图")

    assert calls == [b"fake-image"]
    assert page.capture_widget.status_label.text() == "已完成剪贴板截图识别"
    assert page.order_card_widget.order_id_value.text() == "6952003434324366473"
    assert page.address_widget.output_one.toPlainText() == (
        "何女士15781304332四川省成都市金牛区营门口街道友谊花园9-2304"
    )
    assert page.address_widget.output_two.toPlainText() == "请电话送货上门谢谢【3612】"


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
