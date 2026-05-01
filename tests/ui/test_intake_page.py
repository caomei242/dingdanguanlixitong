import time
from dataclasses import replace

from PySide6.QtWidgets import QCompleter
from PySide6.QtGui import QColor, QGuiApplication, QImage
from PySide6.QtWidgets import QFrame, QLabel, QMessageBox, QScrollArea, QWidget
from PySide6.QtCore import QPoint, Qt

from strawberry_order_management.models import ParsedOrder, ProcurementItem
from strawberry_order_management import app as app_module
from strawberry_order_management.ui.pages.intake_page import IntakePage
from strawberry_order_management.ui.theme import APP_STYLESHEET
from strawberry_order_management.ui.widgets.address_extractor_widget import (
    AddressExtractorWidget,
)
from strawberry_order_management.ui.widgets.screenshot_input_widget import (
    ScreenshotInputWidget,
)


def test_intake_page_uses_compact_two_column_workspace_shell(qtbot):
    page = IntakePage(use_background_thread=False)
    qtbot.addWidget(page)

    assert page.findChild(QFrame, "EntryActionBar") is not None
    assert page.findChild(QWidget, "EntryLeftRail") is not None
    assert page.findChild(QScrollArea, "EntryFormRail") is not None
    assert page.findChild(QFrame, "EntryCaptureCard") is not None
    assert page.findChild(QFrame, "EntryExtractorInputCard") is not None
    assert page.findChild(QFrame, "EntryExtractorResultCard") is not None
    assert page.findChild(QWidget, "EntryRightRail") is None
    assert page.address_widget.input_edit.maximumHeight() <= 180
    assert page.findChild(QScrollArea, "EntryFormRail").horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAsNeeded
    assert page.findChild(QScrollArea, "EntryFormRail").viewport().objectName() == "EntryFormViewport"


def test_intake_page_hides_helper_copy(qtbot):
    page = IntakePage(use_background_thread=False)
    qtbot.addWidget(page)

    texts = [label.text() for label in page.findChildren(QLabel)]

    assert "支持粘贴截图、拖拽图片或选择图片，识别后自动生成订单卡" not in texts
    assert "编号、状态和金额放在一起，方便快速校对。" not in texts
    assert "收件人、电话、地址与备注单独收拢。" not in texts
    assert "三条采购槽位用于入库或补录商品库信息。" not in texts


def test_intake_theme_includes_financial_section_card_selector():
    assert "QFrame#FinancialSectionCard" in APP_STYLESHEET
    assert "QWidget#EntryFormViewport" in APP_STYLESHEET
    assert "QComboBox QAbstractItemView" in APP_STYLESHEET
    assert "QScrollBar:horizontal" in APP_STYLESHEET
    assert "QScrollBar::handle:horizontal" in APP_STYLESHEET
    assert "QAbstractScrollArea::viewport" in APP_STYLESHEET
    assert "QToolTip" in APP_STYLESHEET
    assert "QSplitter::handle" in APP_STYLESHEET


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
    page.shop_selector.addItems(["乐宝零食店"])
    page.shop_selector.setCurrentText("乐宝零食店")
    page.submit_button.click()

    assert page.order_card_widget.order_id_edit.text() == "6952003434324366473"
    assert page.order_card_widget.recipient_name_edit.text() == "何女士"
    assert page.order_card_widget.phone_number_edit.text() == "15781304332"
    assert page.order_card_widget.code_edit.text() == "3612"
    assert page.order_card_widget.address_edit.toPlainText() == "四川省成都市金牛区营门口街道友谊花园9-2304"
    assert page.order_card_widget.delivery_note_edit.toPlainText() == ""
    assert isinstance(page.address_widget, AddressExtractorWidget)
    assert page.submit_button.text() == "确认写入飞书"
    assert submitted_orders == [
        {
            "shop_name": "乐宝零食店",
            "order": replace(
                order,
                delivery_note="",
                platform_fee_rate="0.06",
                platform_fee_amount="9.72",
                gross_profit="152.28",
                procurement_total_cost="0.00",
            ),
        }
    ]


def test_intake_page_preserves_custom_delivery_note(qtbot):
    page = IntakePage(use_background_thread=False)
    qtbot.addWidget(page)

    order = ParsedOrder(
        order_id="1",
        placed_at="2026-04-11 20:57:15",
        order_status="已发货",
        product_name="商品",
        quantity="1",
        order_amount="10.00",
        income_amount="8.00",
        recipient_name="何女士",
        phone_number="15781304332",
        code="3612",
        address="重庆市",
        delivery_note="请尽快发货",
    )

    page.show_order(order)

    assert page.order_card_widget.delivery_note_edit.toPlainText() == "请尽快发货"


def test_intake_page_submits_procurement_tracking_number(qtbot):
    submitted_orders = []
    page = IntakePage(on_submit=submitted_orders.append, use_background_thread=False)
    qtbot.addWidget(page)

    order = ParsedOrder(
        order_id="1",
        placed_at="2026-04-11 20:57:15",
        order_status="已发货",
        product_name="商品",
        quantity="1",
        order_amount="10.00",
        income_amount="8.00",
        recipient_name="何女士",
        phone_number="15781304332",
        code="3612",
        address="重庆市",
        delivery_note="备注",
    )

    page.show_order(order)
    page.shop_selector.addItems(["乐宝零食店"])
    page.shop_selector.setCurrentText("乐宝零食店")
    page.order_card_widget.procurement_tracking_number_1_edit.setText("YT99887766")

    page.submit_button.click()

    assert submitted_orders[0]["order"].procurement_tracking_number == "YT99887766"
    assert submitted_orders[0]["order"].procurement_items[0].tracking_number == "YT99887766"


def test_intake_page_does_not_expose_procurement_jd_link_field(qtbot):
    submitted_orders = []
    page = IntakePage(on_submit=submitted_orders.append, use_background_thread=False)
    qtbot.addWidget(page)

    order = ParsedOrder(
        order_id="1",
        placed_at="2026-04-11 20:57:15",
        order_status="已发货",
        product_name="商品",
        quantity="1",
        order_amount="10.00",
        income_amount="8.00",
        recipient_name="何女士",
        phone_number="15781304332",
        code="3612",
        address="重庆市",
        delivery_note="备注",
    )

    page.show_order(order)
    page.shop_selector.addItems(["乐宝零食店"])
    page.shop_selector.setCurrentText("乐宝零食店")

    page.submit_button.click()

    assert not hasattr(page.order_card_widget, "procurement_jd_link_1_edit")
    assert submitted_orders[0]["order"].procurement_items[0].jd_link == ""


def test_intake_page_keeps_blank_procurement_slots_blank_when_submitting(qtbot):
    submitted_orders = []
    page = IntakePage(on_submit=submitted_orders.append, use_background_thread=False)
    qtbot.addWidget(page)

    order = ParsedOrder(
        order_id="1",
        placed_at="2026-04-11 20:57:15",
        order_status="已发货",
        product_name="商品",
        quantity="1",
        order_amount="10.00",
        income_amount="8.00",
        recipient_name="何女士",
        phone_number="15781304332",
        code="3612",
        address="重庆市",
        delivery_note="备注",
    )

    page.show_order(order)
    page.shop_selector.addItems(["乐宝零食店"])
    page.shop_selector.setCurrentText("乐宝零食店")
    page.submit_button.click()

    assert submitted_orders[0]["order"].procurement_items[1] == ProcurementItem("", "", "", "")
    assert submitted_orders[0]["order"].procurement_items[2] == ProcurementItem("", "", "", "")


def test_intake_page_defaults_platform_to_douyin_and_supports_wechat(qtbot):
    submitted_orders = []
    page = IntakePage(on_submit=submitted_orders.append, use_background_thread=False)
    qtbot.addWidget(page)

    order = ParsedOrder(
        order_id="1",
        placed_at="2026-04-11 20:57:15",
        order_status="已发货",
        product_name="商品",
        quantity="1",
        order_amount="10.00",
        income_amount="8.00",
        recipient_name="何女士",
        phone_number="15781304332",
        code="3612",
        address="重庆市",
        delivery_note="备注",
    )

    page.show_order(order)
    page.shop_selector.addItems(["乐宝零食店"])
    page.shop_selector.setCurrentText("乐宝零食店")

    assert page.platform_selector.currentText() == "抖店"

    page.platform_selector.setCurrentText("微信小店")
    page.submit_button.click()

    assert submitted_orders == [
        {
            "shop_name": "乐宝零食店",
            "order": replace(
                order,
                platform="微信小店",
                platform_fee_rate="0.06",
                platform_fee_amount="0.48",
                procurement_total_cost="0.00",
                gross_profit="7.52",
            ),
        }
    ]


def test_intake_page_preserves_recognized_wechat_platform_when_showing_order(qtbot):
    page = IntakePage(use_background_thread=False)
    qtbot.addWidget(page)
    page.set_shop_names(["乐宝零食店", "乐宝零食店--微信"])
    page.set_shop_platforms({"乐宝零食店": "抖店", "乐宝零食店--微信": "微信小店"})

    page.show_order(
        ParsedOrder(
            order_id="1",
            placed_at="2026-04-20 09:55",
            order_status="已发货",
            product_name="商品",
            quantity="1",
            order_amount="355.00",
            income_amount="142.00",
            recipient_name="潇寒",
            phone_number="18401352224",
            code="9530",
            address="河北省石家庄市裕华区",
            delivery_note="请电话送货上门谢谢【9530】",
            platform="微信小店",
        )
    )

    assert page.platform_selector.currentText() == "微信小店"
    assert page.shop_selector.currentText() == "乐宝零食店--微信"


def test_intake_page_keeps_selected_douyin_shop_when_ocr_detects_wechat(qtbot):
    def process_image(_image_bytes: bytes):
        return ParsedOrder(
            order_id="6952520193484068417",
            placed_at="2026-05-02 00:06:32",
            order_status="已拍单未发货",
            product_name="测试商品",
            quantity="2",
            order_amount="355.00",
            income_amount="284.00",
            recipient_name="张钰",
            phone_number="18413026178",
            code="5236",
            address="河南省安阳市北关区",
            delivery_note="请电话送货上门谢谢【5236】",
            platform="微信小店",
        )

    submitted_orders = []
    page = IntakePage(
        on_submit=submitted_orders.append,
        on_process_image=process_image,
        use_background_thread=False,
    )
    qtbot.addWidget(page)
    page.set_shop_names(["乐宝零食店", "乐宝零食店--微信"])
    page.set_shop_platforms({"乐宝零食店": "抖店", "乐宝零食店--微信": "微信小店"})
    page.shop_selector.setCurrentText("乐宝零食店")
    page.platform_selector.setCurrentText("抖店")

    page.process_image_bytes(b"fake-image", "剪贴板截图")
    page.submit_button.click()

    assert page.shop_selector.currentText() == "乐宝零食店"
    assert page.platform_selector.currentText() == "抖店"
    assert submitted_orders[0]["shop_name"] == "乐宝零食店"
    assert submitted_orders[0]["order"].platform == "抖店"


def test_intake_page_switches_default_shop_when_platform_changes(qtbot):
    page = IntakePage(use_background_thread=False)
    qtbot.addWidget(page)
    page.set_shop_names(["乐宝零食店", "乐宝零食店--微信"])
    page.set_shop_platforms({"乐宝零食店": "抖店", "乐宝零食店--微信": "微信小店"})
    page.shop_selector.setCurrentText("乐宝零食店")

    page.platform_selector.setCurrentText("微信小店")

    assert page.shop_selector.currentText() == "乐宝零食店--微信"

    page.platform_selector.setCurrentText("抖店")

    assert page.shop_selector.currentText() == "乐宝零食店"


def test_intake_page_defaults_fee_rate_to_point_zero_six_and_uses_fixed_status_options(qtbot):
    page = IntakePage(use_background_thread=False)
    qtbot.addWidget(page)

    order = ParsedOrder(
        order_id="1",
        placed_at="2026-04-11 20:57:15",
        order_status="已拍单未发货",
        product_name="商品",
        quantity="1",
        order_amount="10.00",
        income_amount="8.00",
        recipient_name="何女士",
        phone_number="15781304332",
        code="3612",
        address="重庆市",
        delivery_note="备注",
    )

    page.show_order(order)

    assert page.order_card_widget.platform_fee_rate_edit.text() == "0.06"
    assert page.order_card_widget.platform_fee_amount_edit.text() == "0.48"
    assert page.order_card_widget.order_status_edit.currentText() == "已拍单未发货"
    assert [
        page.order_card_widget.order_status_edit.itemText(index)
        for index in range(page.order_card_widget.order_status_edit.count())
    ] == ["已发货", "待发货", "已拍单未发货", "已完成售后"]


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
    assert widget.status_label.text() == ""


def test_screenshot_input_widget_hides_helper_subtitle(qtbot):
    widget = ScreenshotInputWidget()
    qtbot.addWidget(widget)

    texts = [label.text() for label in widget.findChildren(QLabel)]

    assert "支持粘贴截图、拖拽图片或选择图片，识别后自动生成订单卡" not in texts


def test_screenshot_input_widget_status_wraps_long_errors(qtbot):
    widget = ScreenshotInputWidget()
    qtbot.addWidget(widget)

    assert widget.status_label.wordWrap()


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
    assert page.address_widget.status_label.text() == ""


def test_intake_page_switches_between_multiple_recognized_orders(qtbot):
    def process_image(image_bytes: bytes):
        return [
            ParsedOrder(
                order_id="6925968364688539154",
                placed_at="2026-04-29 15:58:48",
                order_status="待发货",
                product_name="【明日达】赵露丝同款27000澳大利亚进口婴儿水宝宝水高偏矿泉水",
                specification="1ml/袋*4袋(赵露思瓶盖X4个)x1",
                quantity="1",
                order_amount="150.00",
                income_amount="60.00",
                recipient_name="桃子",
                phone_number="17804472821",
                code="8131",
                address="山东省潍坊市寿光市洛城街道永泰花园小区",
                delivery_note="请电话送货上门谢谢【8131】",
            ),
            ParsedOrder(
                order_id="6925956120875073042",
                placed_at="2026-04-29 15:29:31",
                order_status="待发货",
                product_name="【明日达】赵露丝同款27000澳大利亚进口婴儿水宝宝水高偏矿泉水",
                specification="500ml/桶*12袋(赵露思同款澳版（同款瓶盖，默认粉色）)x1",
                quantity="1",
                order_amount="325.00",
                income_amount="130.00",
                recipient_name="桃子",
                phone_number="18413059360",
                code="4317",
                address="山东省潍坊市寿光市洛城街道永泰花园小区",
                delivery_note="请电话送货上门谢谢【4317】",
            ),
        ]

    page = IntakePage(on_process_image=process_image, use_background_thread=False)
    qtbot.addWidget(page)

    page.process_image_bytes(b"fake-image", "剪贴板截图")

    assert page.batch_selector_card.isHidden() is False
    assert page.batch_selector_label.text() == "识别到 2 单，点下面切换填写"
    assert [button.text() for button in page._batch_order_buttons] == [
        "第1单 桃子 · 收入 60.00",
        "第2单 桃子 · 收入 130.00",
    ]
    assert page.order_card_widget.order_id_edit.text() == "6925968364688539154"
    assert page.address_widget.output_two.toPlainText() == "请电话送货上门谢谢【8131】"

    page._batch_order_buttons[1].click()

    assert page.order_card_widget.order_id_edit.text() == "6925956120875073042"
    assert page.order_card_widget.order_amount_edit.text() == "325.00"
    assert page.address_widget.output_one.toPlainText() == (
        "桃子18413059360山东省潍坊市寿光市洛城街道永泰花园小区"
    )
    assert page.address_widget.output_two.toPlainText() == "请电话送货上门谢谢【4317】"
    assert page.capture_widget.status_label.text() == "已完成剪贴板截图识别，识别到 2 单，当前第 2 单"


def test_intake_page_does_not_keep_stale_sku_image_when_switching_batch_orders(qtbot):
    old_order = ParsedOrder(
        order_id="old-order",
        placed_at="2026-04-11 20:57:15",
        order_status="已发货",
        product_name="旧商品",
        quantity="1",
        order_amount="10.00",
        income_amount="8.00",
        recipient_name="何女士",
        phone_number="15781304332",
        code="3612",
        address="重庆市",
        delivery_note="请电话送货上门谢谢【3612】",
        sku_image_path="/tmp/old-sku.png",
    )

    def process_image(image_bytes: bytes):
        return [
            ParsedOrder(
                order_id="6925968364688539154",
                placed_at="2026-04-29 15:58:48",
                order_status="待发货",
                product_name="测试商品一",
                sku_image_path="/tmp/first-sku.png",
                quantity="1",
                order_amount="150.00",
                income_amount="60.00",
                recipient_name="桃子",
                phone_number="17804472821",
                code="8131",
                address="山东省潍坊市寿光市",
                delivery_note="请电话送货上门谢谢【8131】",
            ),
            ParsedOrder(
                order_id="6925956120875073042",
                placed_at="2026-04-29 15:29:31",
                order_status="待发货",
                product_name="测试商品二",
                quantity="1",
                order_amount="325.00",
                income_amount="130.00",
                recipient_name="桃子",
                phone_number="18413059360",
                code="4317",
                address="山东省潍坊市寿光市",
                delivery_note="请电话送货上门谢谢【4317】",
            ),
        ]

    page = IntakePage(on_process_image=process_image, use_background_thread=False)
    qtbot.addWidget(page)
    page.show_order(old_order)

    assert page.order_card_widget.sku_image_label.property("imagePath") == "/tmp/old-sku.png"

    page.process_image_bytes(b"fake-image", "剪贴板截图")

    assert page.order_card_widget.sku_image_label.property("imagePath") == "/tmp/first-sku.png"

    page._batch_order_buttons[1].click()

    assert page.order_card_widget.order_id_edit.text() == "6925956120875073042"
    assert page.order_card_widget.sku_image_label.property("imagePath") == ""


def test_intake_page_shows_partial_batch_failures(qtbot):
    def process_image(_image_bytes: bytes):
        return {
            "recognized_orders": [
                ParsedOrder(
                    order_id="6925968364688539154",
                    placed_at="2026-04-29 15:58:48",
                    order_status="待发货",
                    product_name="测试商品一",
                    quantity="1",
                    order_amount="150.00",
                    income_amount="60.00",
                    recipient_name="桃子",
                    phone_number="17804472821",
                    code="8131",
                    address="山东省潍坊市寿光市洛城街道永泰花园小区",
                    delivery_note="请电话送货上门谢谢【8131】",
                )
            ],
            "failed_messages": ["第 2 单识别失败：MCP OCR 响应超时，请重试；可重试或手动补录"],
            "total_count": 2,
        }

    page = IntakePage(on_process_image=process_image, use_background_thread=False)
    qtbot.addWidget(page)

    page.process_image_bytes(b"fake-image", "剪贴板截图")

    assert page.batch_selector_card.isHidden() is False
    assert page.batch_selector_label.text() == "识别到 2 单，其中 1 单失败，点下面切换填写"
    assert [button.text() for button in page._batch_order_buttons] == ["第1单 桃子 · 收入 60.00"]
    assert page.capture_widget.status_label.text() == (
        "已完成剪贴板截图识别，识别到 2 单，其中 1 单失败，当前第 1 个成功订单"
    )


def test_intake_page_clears_stale_sku_image_when_single_recognition_has_no_image(qtbot):
    def process_image(image_bytes: bytes):
        return ParsedOrder(
            order_id="6925796821603614616",
            placed_at="2026-04-22 20:44:47",
            order_status="已发货",
            product_name="测试商品",
            quantity="1",
            order_amount="355.00",
            income_amount="142.00",
            recipient_name="张春娜",
            phone_number="15789799611",
            code="2666",
            address="山西省太原市小店区",
            delivery_note="请电话送货上门谢谢【2666】",
        )

    page = IntakePage(on_process_image=process_image, use_background_thread=False)
    qtbot.addWidget(page)
    page.show_order(
        ParsedOrder(
            order_id="old-order",
            placed_at="2026-04-11 20:57:15",
            order_status="已发货",
            product_name="旧商品",
            quantity="1",
            order_amount="10.00",
            income_amount="8.00",
            recipient_name="何女士",
            phone_number="15781304332",
            code="3612",
            address="重庆市",
            delivery_note="请电话送货上门谢谢【3612】",
            sku_image_path="/tmp/old-sku.png",
        )
    )

    assert page.order_card_widget.sku_image_label.property("imagePath") == "/tmp/old-sku.png"

    page.process_image_bytes(b"fake-image", "剪贴板截图")

    assert page.order_card_widget.order_id_edit.text() == "6925796821603614616"
    assert page.order_card_widget.sku_image_label.property("imagePath") == ""


def test_intake_page_passes_progress_callback_to_image_processor(qtbot):
    progress_messages = []

    def process_image(image_bytes: bytes, on_progress):
        on_progress("OCR识别中...")
        on_progress("辅助整理中...")
        progress_messages.extend(["OCR识别中...", "辅助整理中..."])
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

    assert progress_messages == ["OCR识别中...", "辅助整理中..."]
    assert page.capture_widget.status_label.text() == "已完成剪贴板截图识别"


def test_intake_page_merges_partial_image_result_into_existing_manual_entry(qtbot):
    def process_image(image_bytes: bytes):
        return ParsedOrder(
            order_id="6925796821603614616",
            placed_at="2026-04-22 20:44:47",
            order_status="",
            product_name="【明日达】赵露丝同款27000澳大利亚进口婴儿水宝宝水高偏矿泉水",
            specification="1L/桶*12瓶(赵露思同款 澳洲升级...)",
            quantity="1",
            order_amount="355.00",
            income_amount="",
            recipient_name="",
            phone_number="",
            code="",
            address="",
            delivery_note="",
        )

    page = IntakePage(on_process_image=process_image, use_background_thread=False)
    qtbot.addWidget(page)
    page.show_order(
        ParsedOrder(
            order_id="",
            placed_at="",
            order_status="已发货",
            product_name="",
            quantity="",
            order_amount="",
            income_amount="142.00",
            recipient_name="张春娜",
            phone_number="15789799611",
            code="2666",
            address="山西省太原市小店区北营街道富力金禧城A区5栋1单元2402",
            delivery_note="请电话送货上门谢谢【2666】",
        )
    )

    page.process_image_bytes(b"fake-image", "剪贴板截图")

    assert page.order_card_widget.order_id_edit.text() == "6925796821603614616"
    assert page.order_card_widget.placed_at_edit.text() == "2026-04-22 20:44:47"
    assert page.order_card_widget.order_status_edit.currentText() == "已发货"
    assert page.order_card_widget.product_name_edit.toPlainText() == (
        "【明日达】赵露丝同款27000澳大利亚进口婴儿水宝宝水高偏矿泉水"
    )
    assert page.order_card_widget.specification_edit.text() == "1L/桶*12瓶(赵露思同款 澳洲升级...)"
    assert page.order_card_widget.order_amount_edit.text() == "355.00"
    assert page.order_card_widget.income_amount_edit.text() == "142.00"
    assert page.order_card_widget.recipient_name_edit.text() == "张春娜"
    assert page.order_card_widget.phone_number_edit.text() == "15789799611"
    assert page.order_card_widget.code_edit.text() == "2666"
    assert page.order_card_widget.address_edit.toPlainText() == (
        "山西省太原市小店区北营街道富力金禧城A区5栋1单元2402"
    )
    assert page.capture_widget.status_label.text() == "已完成剪贴板截图识别，缺失字段已保留原填写内容"


def test_intake_page_backfills_order_from_manual_text_input(qtbot):
    page = IntakePage(use_background_thread=False)
    qtbot.addWidget(page)

    page.address_widget.input_edit.setPlainText(
        """
        订单编号 6925796821603614616
        下单时间 2026-04-22 20:44:47
        订单状态 完成
        商品
        【明日达】赵露丝同款27000澳大利亚进口婴儿水宝宝水高偏矿泉水
        1L/桶*12瓶(赵露思同款 澳洲升级...)
        单价/数量 ¥355.00 x1
        商家收入金额 ¥142.00
        收货信息 张春娜15789799611山西省太原市小店区北营街道富力金禧城A区5栋1单元2402
        """
    )

    page.address_widget.extract_button.click()

    assert page.order_card_widget.order_id_edit.text() == "6925796821603614616"
    assert page.order_card_widget.placed_at_edit.text() == "2026-04-22 20:44:47"
    assert page.order_card_widget.order_status_edit.currentText() == "已发货"
    assert page.order_card_widget.product_name_edit.toPlainText() == (
        "【明日达】赵露丝同款27000澳大利亚进口婴儿水宝宝水高偏矿泉水"
    )
    assert page.order_card_widget.specification_edit.text() == "1L/桶*12瓶(赵露思同款 澳洲升级...)"
    assert page.order_card_widget.quantity_edit.text() == "1"
    assert page.order_card_widget.order_amount_edit.text() == "355.00"
    assert page.order_card_widget.income_amount_edit.text() == "142.00"
    assert page.order_card_widget.recipient_name_edit.text() == "张春娜"
    assert page.order_card_widget.phone_number_edit.text() == "15789799611"
    assert page.order_card_widget.code_edit.text() == ""
    assert page.order_card_widget.address_edit.toPlainText() == (
        "山西省太原市小店区北营街道富力金禧城A区5栋1单元2402"
    )
    assert page.address_widget.output_one.toPlainText() == (
        "张春娜15789799611山西省太原市小店区北营街道富力金禧城A区5栋1单元2402"
    )
    assert page.address_widget.output_two.toPlainText() == ""
    assert page.save_history_button.isEnabled() is True
    assert page.submit_button.isEnabled() is True
    assert page.address_widget.status_label.text() == "已按文字补单填入订单"


def test_intake_page_fills_recipient_from_address_only_text(qtbot):
    page = IntakePage(use_background_thread=False)
    qtbot.addWidget(page)

    page.address_widget.input_edit.setPlainText(
        "张春娜[2666]15789799611山西省太原市小店区北营街道富力金禧城A区5栋1单元2402[2666]"
    )

    page.address_widget.extract_button.click()

    assert page.order_card_widget.recipient_name_edit.text() == "张春娜"
    assert page.order_card_widget.phone_number_edit.text() == "15789799611"
    assert page.order_card_widget.code_edit.text() == "2666"
    assert page.order_card_widget.address_edit.toPlainText() == (
        "山西省太原市小店区北营街道富力金禧城A区5栋1单元2402"
    )
    assert page.address_widget.output_one.toPlainText() == (
        "张春娜15789799611山西省太原市小店区北营街道富力金禧城A区5栋1单元2402"
    )
    assert page.address_widget.output_two.toPlainText() == "请电话送货上门谢谢【2666】"
    assert page.order_card_widget.order_id_edit.text() == ""
    assert page.order_card_widget.product_name_edit.toPlainText() == ""
    assert page.address_widget.status_label.text() == "已填入收货信息，订单号和商品请继续补齐"


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

    page.shop_selector.addItems(["乐宝零食店"])
    page.shop_selector.setCurrentText("乐宝零食店")
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

    assert saved_payloads[0]["shop_name"] == "乐宝零食店"
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
                ProcurementItem("", "", ""),
                ProcurementItem("", "", ""),
                ProcurementItem("", "", ""),
            ),
        )
    )

    page.order_card_widget.procurement_product_1_combo.setCurrentText("澳洲婴儿水")

    assert page.order_card_widget.procurement_quantity_1_edit.text() == "1"
    assert page.order_card_widget.procurement_cost_1_edit.text() == "18.50"


def test_order_card_predicts_procurement_products_from_library_prefix(qtbot):
    page = IntakePage(use_background_thread=False)
    qtbot.addWidget(page)

    page.set_product_presets(
        [
            {"name": "27000-澳洲版-1升装", "default_cost": "109"},
            {"name": "27000-天山版-1升装", "default_cost": "89"},
            {"name": "康兴-瓶盖-粉色", "default_cost": "13.8"},
        ]
    )

    combo = page.order_card_widget.procurement_product_1_combo
    completer = combo.completer()
    completer.setCompletionPrefix("27000-")

    assert completer.completionMode() == QCompleter.CompletionMode.PopupCompletion
    assert completer.filterMode() == Qt.MatchFlag.MatchContains
    assert completer.caseSensitivity() == Qt.CaseSensitivity.CaseInsensitive
    assert {
        completer.completionModel().index(row, 0).data()
        for row in range(completer.completionCount())
    } == {"27000-澳洲版-1升装", "27000-天山版-1升装"}


def test_intake_page_groups_order_entry_into_sections(qtbot):
    page = IntakePage(use_background_thread=False)
    qtbot.addWidget(page)

    section_titles = []
    order_layout = page.order_card_widget.layout()
    for index in range(order_layout.count() - 1):
        section_card = order_layout.itemAt(index).widget()
        if isinstance(section_card, QFrame):
            section_title = section_card.findChild(QLabel)
            if section_title is not None:
                section_titles.append(section_title.text())

    procurement_card = None
    for frame in page.order_card_widget.findChildren(QFrame):
        labels = [label.text() for label in frame.findChildren(QLabel)]
        if "采购信息" in labels:
            procurement_card = frame
            break

    assert section_titles == ["采购信息", "财务信息", "订单概览", "收件信息"]
    assert procurement_card is not None
    assert "采购1" in [label.text() for label in procurement_card.findChildren(QLabel)]
    assert "采购2" in [label.text() for label in procurement_card.findChildren(QLabel)]
    assert "采购3" in [label.text() for label in procurement_card.findChildren(QLabel)]
    assert "订单编号" not in [label.text() for label in page.order_card_widget.findChildren(QLabel)]


def test_intake_page_emits_procurement_slots_with_order_payload(qtbot):
    submitted_orders = []
    page = IntakePage(on_submit=submitted_orders.append, use_background_thread=False)
    qtbot.addWidget(page)

    page.set_product_presets([{"name": "澳洲婴儿水", "default_cost": "18.50"}])
    page.shop_selector.addItems(["乐宝零食店"])
    page.shop_selector.setCurrentText("乐宝零食店")
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


def test_order_card_can_request_saving_spec_template_to_library(qtbot):
    saved_templates = []
    page = IntakePage(use_background_thread=False)
    qtbot.addWidget(page)
    page.procurement_template_requested.connect(saved_templates.append)
    page.show_order(
        ParsedOrder(
            order_id="6952003434324366473",
            placed_at="2026-04-11 20:57:15",
            order_status="已发货",
            product_name="澳大利亚进口婴儿水",
            specification="1L/桶*12袋(赵露思同款 澳洲版)",
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

    page.order_card_widget.procurement_product_1_combo.setEditText("27000-澳洲版-1升装")
    page.order_card_widget.procurement_quantity_1_edit.setText("2")
    page.order_card_widget.procurement_cost_1_edit.setText("109")
    page.order_card_widget.procurement_tracking_number_1_edit.setText("SF123")
    page.order_card_widget.procurement_save_1_button.click()

    assert saved_templates == [
        {
            "specification": "1L/桶*12袋(赵露思同款 澳洲版)",
            "procurement_items": [
                {
                    "product_name": "27000-澳洲版-1升装",
                    "quantity": "2",
                    "cost": "109",
                    "tracking_number": "",
                },
                {"product_name": "", "quantity": "", "cost": "", "tracking_number": ""},
                {"product_name": "", "quantity": "", "cost": "", "tracking_number": ""},
            ],
        }
    ]


def test_order_card_prefills_procurement_items_from_matching_specification_template(qtbot):
    page = IntakePage(use_background_thread=False)
    qtbot.addWidget(page)
    page.set_product_presets([{"name": "27000-澳洲版-1升装", "default_cost": "109"}])
    page.set_procurement_templates(
        [
            {
                "specification": "1L/桶*12袋(赵露思同款 澳洲版)",
                "procurement_items": [
                    {
                        "product_name": "27000-澳洲版-1升装",
                        "quantity": "2",
                        "cost": "109",
                    },
                    {"product_name": "康兴-瓶盖-粉色", "quantity": "1", "cost": "13.8"},
                    {"product_name": "", "quantity": "1", "cost": ""},
                ],
            }
        ]
    )

    page.show_order(
        ParsedOrder(
            order_id="6952003434324366473",
            placed_at="2026-04-11 20:57:15",
            order_status="已发货",
            product_name="澳大利亚进口婴儿水",
            specification="1L/桶*12袋(赵露思同款 澳洲版)",
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

    assert page.order_card_widget.procurement_product_1_combo.currentText() == "27000-澳洲版-1升装"
    assert page.order_card_widget.procurement_quantity_1_edit.text() == "2"
    assert page.order_card_widget.procurement_cost_1_edit.text() == "109"
    assert page.order_card_widget.procurement_tracking_number_1_edit.text() == ""


def test_order_card_prefills_procurement_items_from_normalized_specification_template(qtbot):
    page = IntakePage(use_background_thread=False)
    qtbot.addWidget(page)
    page.set_product_presets([{"name": "27000-澳洲版-1升装", "default_cost": "109"}])
    page.set_procurement_templates(
        [
            {
                "specification": "1L/桶*12袋(赵露思同款 澳洲版)",
                "procurement_items": [
                    {
                        "product_name": "27000-澳洲版-1升装",
                        "quantity": "2",
                        "cost": "109",
                    },
                    {"product_name": "康兴-瓶盖-粉色", "quantity": "1", "cost": "13.8"},
                    {"product_name": "", "quantity": "1", "cost": ""},
                ],
            }
        ]
    )

    page.show_order(
        ParsedOrder(
            order_id="6952003434324366473",
            placed_at="2026-04-11 20:57:15",
            order_status="已发货",
            product_name="澳大利亚进口婴儿水",
            specification=" 1L/桶*12袋 (赵露思同款 澳洲版) x1 ",
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

    assert page.order_card_widget.procurement_product_1_combo.currentText() == "27000-澳洲版-1升装"
    assert page.order_card_widget.procurement_quantity_1_edit.text() == "2"
    assert page.order_card_widget.procurement_cost_1_edit.text() == "109"
    assert page.order_card_widget.procurement_tracking_number_1_edit.text() == ""


def test_order_card_defaults_procurement_quantity_to_one_when_product_is_entered(qtbot):
    page = IntakePage(use_background_thread=False)
    qtbot.addWidget(page)
    page.set_product_presets([{"name": "27000-澳洲版-1升装", "default_cost": "109"}])
    page.show()

    page.order_card_widget.procurement_product_1_combo.setCurrentText("27000-澳洲版-1升装")

    assert page.order_card_widget.procurement_quantity_1_edit.text() == "1"
    assert page.order_card_widget.procurement_cost_1_edit.text() == "109"


def test_order_card_prioritizes_procurement_and_finance_sections(qtbot):
    page = IntakePage(use_background_thread=False)
    qtbot.addWidget(page)

    section_titles = [
        label.text()
        for label in page.order_card_widget.findChildren(QLabel)
        if label.objectName() == "SectionTitle"
    ]

    assert section_titles[:4] == ["采购信息", "财务信息", "订单概览", "收件信息"]


def test_order_card_places_income_next_to_quantity_and_order_amount(qtbot):
    page = IntakePage(use_background_thread=False)
    qtbot.addWidget(page)
    page.show()

    quantity_pos = page.order_card_widget.quantity_edit.mapTo(
        page.order_card_widget, QPoint(0, 0)
    )
    income_pos = page.order_card_widget.income_amount_edit.mapTo(
        page.order_card_widget, QPoint(0, 0)
    )
    order_amount_pos = page.order_card_widget.order_amount_edit.mapTo(
        page.order_card_widget, QPoint(0, 0)
    )

    assert quantity_pos.y() == income_pos.y() == order_amount_pos.y()


def test_order_card_clear_tracking_button_only_clears_current_slot(qtbot):
    page = IntakePage(use_background_thread=False)
    qtbot.addWidget(page)

    page.order_card_widget.procurement_tracking_number_1_edit.setText("YT99887766")
    page.order_card_widget.procurement_tracking_number_2_edit.setText("SF55667788")

    page.order_card_widget.procurement_clear_tracking_1_button.click()

    assert page.order_card_widget.procurement_tracking_number_1_edit.text() == ""
    assert page.order_card_widget.procurement_tracking_number_2_edit.text() == "SF55667788"


def test_intake_page_warns_when_order_quantity_is_greater_than_one(qtbot, monkeypatch):
    warnings = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *args: warnings.append(args[1:3]) or QMessageBox.StandardButton.Ok,
    )
    page = IntakePage(use_background_thread=False)
    qtbot.addWidget(page)
    page.show()

    page.show_order(
        ParsedOrder(
            order_id="6952003434324366999",
            placed_at="2026-04-12 09:15:00",
            order_status="待发货",
            product_name="云南蓝莓",
            quantity="2",
            order_amount="88.00",
            income_amount="44.00",
            recipient_name="王先生",
            phone_number="13900001111",
            code="8899",
            address="广东省深圳市南山区科技园",
            delivery_note="请尽快发货",
        )
    )

    assert warnings == [("数量提醒", "当前订单数量大于 1，请确认采购数量不要和实际订单数量不一致。")]


def test_order_card_computes_fee_total_cost_and_gross_profit(qtbot):
    page = IntakePage(use_background_thread=False)
    qtbot.addWidget(page)

    page.order_card_widget.set_custom_cost_labels(["包装费", "", ""])
    page.order_card_widget.income_amount_edit.setText("100")
    page.order_card_widget.platform_fee_rate_edit.setText("10")
    page.order_card_widget.procurement_quantity_1_edit.setText("2")
    page.order_card_widget.procurement_cost_1_edit.setText("20")
    page.order_card_widget.other_cost_edit.setText("5")
    page.order_card_widget.custom_cost_value_edits[0].setText("3")

    assert page.order_card_widget.platform_fee_amount_edit.text() == "10.00"
    assert page.order_card_widget.procurement_total_cost_edit.text() == "40.00"
    assert page.order_card_widget.gross_profit_edit.text() == "42.00"


def test_order_card_treats_decimal_fee_rate_as_direct_multiplier(qtbot):
    page = IntakePage(use_background_thread=False)
    qtbot.addWidget(page)

    page.order_card_widget.income_amount_edit.setText("162.00")
    page.order_card_widget.platform_fee_rate_edit.setText("0.06")

    assert page.order_card_widget.platform_fee_amount_edit.text() == "9.72"
    assert page.order_card_widget.gross_profit_edit.text() == "152.28"


def test_show_order_recalculates_fee_amount_from_income_and_rate(qtbot):
    page = IntakePage(use_background_thread=False)
    qtbot.addWidget(page)

    order = ParsedOrder(
        order_id="1",
        placed_at="2026-04-13 21:31:20",
        order_status="待发货",
        product_name="商品",
        quantity="1",
        order_amount="405.00",
        income_amount="162.00",
        recipient_name="团团",
        phone_number="17804499356",
        code="8368",
        address="辽宁省大连市",
        delivery_note="请电话送货上门谢谢【8368】",
        platform_fee_rate="0.06",
        platform_fee_amount="0.10",
        gross_profit="39.10",
    )

    page.show_order(order)

    assert page.order_card_widget.platform_fee_amount_edit.text() == "9.72"


def test_intake_page_submits_financial_fields_and_custom_costs(qtbot):
    submitted_orders = []
    page = IntakePage(on_submit=submitted_orders.append, use_background_thread=False)
    qtbot.addWidget(page)

    order = ParsedOrder(
        order_id="1",
        placed_at="2026-04-11 20:57:15",
        order_status="已发货",
        product_name="商品",
        quantity="1",
        order_amount="10.00",
        income_amount="8.00",
        recipient_name="何女士",
        phone_number="15781304332",
        code="3612",
        address="重庆市",
        delivery_note="备注",
    )
    page.show_order(order)
    page.shop_selector.addItems(["乐宝零食店"])
    page.shop_selector.setCurrentText("乐宝零食店")
    page.order_card_widget.set_custom_cost_labels(["包装费", "赠品", ""])
    page.order_card_widget.platform_fee_rate_edit.setText("10")
    page.order_card_widget.other_cost_edit.setText("2")
    page.order_card_widget.custom_cost_value_edits[0].setText("1.5")

    page.submit_button.click()

    submitted = submitted_orders[0]["order"]
    assert submitted.platform_fee_rate == "10"
    assert submitted.platform_fee_amount == "0.80"
    assert submitted.other_cost == "2"
    assert submitted.custom_cost_labels == ("包装费", "赠品", "")
    assert submitted.custom_cost_values == ("1.5", "", "")
