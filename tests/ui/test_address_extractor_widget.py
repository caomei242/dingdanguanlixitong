from strawberry_order_management.ui.widgets.address_extractor_widget import (
    AddressExtractorWidget,
)


def test_address_extractor_widget_generates_two_outputs(qtbot):
    widget = AddressExtractorWidget()
    qtbot.addWidget(widget)

    widget.input_edit.setPlainText(
        "何女士[3612]15781304332四川省成都市金牛区营门口街道友谊花园9-2304[3612]"
    )
    widget.extract_button.click()

    assert widget.output_one.toPlainText() == (
        "何女士15781304332四川省成都市金牛区营门口街道友谊花园9-2304"
    )
    assert widget.output_two.toPlainText() == "请电话送货上门谢谢【3612】"
    assert widget.status_label.text() == "提取成功"


def test_address_extractor_widget_shows_error_for_mismatched_codes(qtbot):
    widget = AddressExtractorWidget()
    qtbot.addWidget(widget)

    widget.input_edit.setPlainText("何女士[3612]15781304332四川省成都市[9999]")
    widget.extract_button.click()

    assert widget.output_one.toPlainText() == ""
    assert widget.output_two.toPlainText() == ""
    assert widget.status_label.text() == "编号不一致"


def test_address_extractor_widget_supports_inline_phone_code_format(qtbot):
    widget = AddressExtractorWidget()
    qtbot.addWidget(widget)

    widget.input_edit.setPlainText(
        "郑翔，15795949269-6026，广西壮族自治区北海市海城区 高德街道 北海大道5号北海恒大雅苑2栋2单元1901"
    )
    widget.extract_button.click()

    assert widget.output_one.toPlainText() == (
        "郑翔15795949269广西壮族自治区北海市海城区高德街道北海大道5号北海恒大雅苑2栋2单元1901"
    )
    assert widget.output_two.toPlainText() == "请电话送货上门谢谢【6026】"
    assert widget.status_label.text() == "提取成功"
