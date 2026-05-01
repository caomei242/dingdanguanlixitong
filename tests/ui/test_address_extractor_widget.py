from PySide6.QtGui import QGuiApplication

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


def test_address_extractor_widget_supports_wechat_shop_virtual_number_format(qtbot):
    widget = AddressExtractorWidget()
    qtbot.addWidget(widget)

    widget.input_edit.setPlainText(
        "潇寒（9530)，18401352224-9530，河北省石家庄市裕华区裕华区塔南路位同新村南区位同新村南区多层4幢1单元102（拨打请输入分机号9530）"
    )
    widget.extract_button.click()

    assert widget.output_one.toPlainText() == (
        "潇寒18401352224河北省石家庄市裕华区裕华区塔南路位同新村南区位同新村南区多层4幢1单元102"
    )
    assert widget.output_two.toPlainText() == "请电话送货上门谢谢【9530】"
    assert widget.status_label.text() == "提取成功"


def test_address_extractor_widget_copies_each_output(qtbot):
    widget = AddressExtractorWidget()
    qtbot.addWidget(widget)

    widget.input_edit.setPlainText(
        "郑翔，15795949269-6026，广西壮族自治区北海市海城区 高德街道 北海大道5号北海恒大雅苑2栋2单元1901"
    )
    widget.extract_button.click()

    widget.copy_output_one_button.click()
    assert (
        QGuiApplication.clipboard().text()
        == "郑翔15795949269广西壮族自治区北海市海城区高德街道北海大道5号北海恒大雅苑2栋2单元1901"
    )
    assert widget.status_label.text() == "已复制结果一"

    widget.copy_output_two_button.click()
    assert QGuiApplication.clipboard().text() == "请电话送货上门谢谢【6026】"
    assert widget.status_label.text() == "已复制结果二"
