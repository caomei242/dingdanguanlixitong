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
    assert order.product_name == "【明日达】赵露丝同款27000澳大利亚进口婴儿水宝宝水高偏矿泉水 1L/桶*12袋"
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

    assert order.product_name == "【明日达】赵露丝同款27000澳大利亚进口婴儿水宝宝水高偏矿泉水 1L/桶*12袋"
    assert order.quantity == "1"
    assert order.delivery_note == "请电话送货上门谢谢【3612】"
