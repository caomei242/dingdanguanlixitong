from pathlib import Path

from strawberry_order_management.extractors.order_parser import parse_order_text


def test_parses_jd_order_fixture_into_structured_order():
    raw_text = Path("tests/fixtures/ocr/jd_order_01.txt").read_text(encoding="utf-8")

    order = parse_order_text(raw_text)

    assert order.order_id == "6952003434324366473"
    assert order.placed_at == "2026-04-11 20:57:15"
    assert order.order_status == "已发货"
    assert order.recipient_name == "何女士"
    assert order.phone_number == "15781304332"
    assert order.code == "3612"
    assert order.address == "四川省成都市金牛区营门口街道友谊花园9-2304"
    assert order.product_name == "【明日达】赵露丝同款27000澳大利亚进口婴儿水宝宝水高偏矿泉水"
    assert order.specification == "1L/桶*12袋"
    assert order.quantity == "1"
    assert order.order_amount == "405.00"
    assert order.income_amount == "162.00"
    assert order.delivery_note == "请电话送货上门谢谢【3612】"


def test_parses_order_text_with_extra_spaces_and_newlines():
    raw_text = """
    订单编号   6952003434324366473

    下单时间  2026-04-11 20:57:15
    订单状态   已发货
    商品信息
      【明日达】赵露丝同款27000澳大利亚进口婴儿水宝宝水高偏矿泉水 1L/桶*12袋
    单价/数量    ¥405.00   x  1
    商家收入金额
      ¥162.00
    收货信息
      何女士   [3612]
      15781304332
      四川省成都市金牛区营门口街道友谊花园9-2304   [3612]
    """

    order = parse_order_text(raw_text)

    assert order.product_name == "【明日达】赵露丝同款27000澳大利亚进口婴儿水宝宝水高偏矿泉水"
    assert order.specification == "1L/桶*12袋"
    assert order.quantity == "1"
    assert order.delivery_note == "请电话送货上门谢谢【3612】"


def test_parses_specification_and_optional_sku_from_multiline_product_block():
    raw_text = """
    订单编号 6952003434324366473
    下单时间 2026-04-11 20:57:15
    订单状态 待发货
    商品信息
    【明日达】赵露丝同款27000澳大利亚进口婴儿水宝宝水高偏矿泉水
    1L/桶*12袋(赵露思同款 澳洲版)
    SKU：27000-澳洲版-1升装
    商品ID:6952003434324366473
    单价/数量 ¥405.00 x1
    商家收入金额 ¥162.00
    收货信息 团团 [8368] 17804499356 辽宁省大连市中山区海军广场街道港湾广场地铁站DD口丰悦城2号楼4单元1504 [8368]
    """

    order = parse_order_text(raw_text)

    assert order.product_name == "【明日达】赵露丝同款27000澳大利亚进口婴儿水宝宝水高偏矿泉水"
    assert order.specification == "1L/桶*12袋(赵露思同款 澳洲版)"
    assert order.sku == "27000-澳洲版-1升装"
    assert order.order_status == "待发货"


def test_parses_inline_specification_when_it_is_on_same_product_line():
    raw_text = """
    订单编号 69525544900545379782
    下单时间 2026-04-12 21:48:29
    订单状态 已发货
    商品信息
    【明日达】赵露丝同款27000澳大利亚进口婴儿水宝宝水高偏矿泉水 1L/瓶*12袋(赵露思同款（含同款瓶盖）
    单价/数量 ¥355.00 x1
    商家收入金额 ¥142.00
    收货信息 田宝山 [5842] 15784081541 山东省德州市齐河县晏城街道 玫瑰园4号楼（西北门超市） [5842]
    """

    order = parse_order_text(raw_text)

    assert order.product_name == "【明日达】赵露丝同款27000澳大利亚进口婴儿水宝宝水高偏矿泉水"
    assert order.specification == "1L/瓶*12袋(赵露思同款（含同款瓶盖）"


def test_parses_wechat_shop_virtual_number_recipient_format():
    raw_text = """
    订单编号 6952003434324366473
    下单时间 2026-04-20 10:43:00
    订单状态 已发货
    商品信息
    测试商品
    单价/数量 ¥99.00 x1
    商家收入金额 ¥39.00
    收货信息 潇寒（9530)，18401352224-9530，河北省石家庄市裕华区裕华区塔南路位同新村南区位同新村南区多层4幢1单元102（拨打请输入分机号9530）
    """

    order = parse_order_text(raw_text)

    assert order.recipient_name == "潇寒"
    assert order.phone_number == "18401352224"
    assert order.code == "9530"
    assert order.address == "河北省石家庄市裕华区裕华区塔南路位同新村南区位同新村南区多层4幢1单元102"
    assert order.delivery_note == "请电话送货上门谢谢【9530】"
    assert order.platform == "微信小店"


def test_parses_wechat_shop_screenshot_recipient_labels():
    raw_text = """
    订单编号 6952003434324366473
    下单时间 2026-04-20 10:43:00
    订单状态 已发货
    商品信息
    测试商品
    单价/数量 ¥99.00 x1
    商家收入金额 ¥39.00
    收货信息
    收件人 潇寒
    收货地址 河北省石家庄市裕华区裕华区塔南路位同新村南区位同新村南区多层4幢1单元102
    虚拟号 18401352224 分机号 9530
    """

    order = parse_order_text(raw_text)

    assert order.recipient_name == "潇寒"
    assert order.phone_number == "18401352224"
    assert order.code == "9530"
    assert order.address == "河北省石家庄市裕华区裕华区塔南路位同新村南区位同新村南区多层4幢1单元102"
    assert order.platform == "微信小店"


def test_parses_wechat_desktop_order_labels():
    raw_text = """
    订单号: 3735824608022632960
    下单时间: 2026-04-20 09:55
    商品
    【次日达】赵露思同款27000含瓶盖澳大利亚进口婴儿水宝宝水
    1L/瓶*12瓶+1个同款瓶盖（默认粉色）--赵露思同款（天山版）
    单价/数量 ¥355.00 x1
    实收款/优惠信息 ¥142.00 优惠:-¥213.00
    订单状态 已发货
    详细收货信息
    收件人 潇寒
    收货地址 河北省石家庄市裕华区裕华区塔南路位同新村南区位同新村南区多层4幢1单元102
    真实手机号 申请查看
    虚拟号 18401352224 分机号 9530
    """

    order = parse_order_text(raw_text)

    assert order.order_id == "3735824608022632960"
    assert order.placed_at == "2026-04-20 09:55:00"
    assert order.order_status == "已发货"
    assert order.product_name == "【次日达】赵露思同款27000含瓶盖澳大利亚进口婴儿水宝宝水"
    assert order.specification == "1L/瓶*12瓶+1个同款瓶盖（默认粉色）--赵露思同款（天山版）"
    assert order.quantity == "1"
    assert order.order_amount == "355.00"
    assert order.income_amount == "142.00"
    assert order.recipient_name == "潇寒"
    assert order.phone_number == "18401352224"
    assert order.code == "9530"
    assert order.address == "河北省石家庄市裕华区裕华区塔南路位同新村南区位同新村南区多层4幢1单元102"
    assert order.delivery_note == "请电话送货上门谢谢【9530】"
    assert order.platform == "微信小店"


def test_parses_wechat_desktop_pinyin_recipient_with_bracket_code_without_grabbing_product_name():
    raw_text = """
    订单号: 3735824608022632960
    下单时间: 2026-04-20 09:55
    商品
    【次日达】赵露丝同款27000含瓶盖澳大利亚进口婴儿水宝宝水
    1L/瓶*12瓶+1个同款瓶盖（默认粉色）--赵露思同款（天山版）
    单价/数量 ¥355.00 x1
    实收款/优惠信息 ¥142.00 优惠:-¥213.00
    订单状态 已发货
    详细收货信息
    收件人 ya [0069]
    收货地址 河北省石家庄市裕华区裕华区塔南路位同新村南区
    真实手机号 申请查看
    虚拟号 18401352224 分机号 0069
    """

    order = parse_order_text(raw_text)

    assert order.recipient_name == "ya"
    assert order.phone_number == "18401352224"
    assert order.code == "0069"
    assert order.address == "河北省石家庄市裕华区裕华区塔南路位同新村南区"


def test_parses_recipient_block_without_keeping_virtual_number_label_in_address():
    raw_text = """
    订单编号 6952311189220497224
    下单时间 2026-04-23 22:23:26
    订单状态 已发货
    商品信息
    测试商品
    单价/数量 ¥355.00 x2
    商家收入金额 ¥284.00
    收货信息 娃娃 [7437] 17895014935 虚拟号 吉林省长春市南关区幸福乡 云湖府邸A1栋一单元502 [7437]
    """

    order = parse_order_text(raw_text)

    assert order.recipient_name == "娃娃"
    assert order.phone_number == "17895014935"
    assert order.code == "7437"
    assert order.address == "吉林省长春市南关区幸福乡 云湖府邸A1栋一单元502"
