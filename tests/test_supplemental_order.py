from strawberry_order_management.extractors.supplemental_order import (
    parse_supplemental_order_text,
)


def test_parse_supplemental_order_text_from_manual_backfill_notes():
    patch = parse_supplemental_order_text(
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

    assert patch["order_id"] == "6925796821603614616"
    assert patch["placed_at"] == "2026-04-22 20:44:47"
    assert patch["order_status"] == "已发货"
    assert patch["product_name"] == "【明日达】赵露丝同款27000澳大利亚进口婴儿水宝宝水高偏矿泉水"
    assert patch["specification"] == "1L/桶*12瓶(赵露思同款 澳洲升级...)"
    assert patch["quantity"] == "1"
    assert patch["order_amount"] == "355.00"
    assert patch["income_amount"] == "142.00"
    assert patch["recipient_name"] == "张春娜"
    assert patch["phone_number"] == "15789799611"
    assert patch["code"] == ""
    assert patch["address"] == "山西省太原市小店区北营街道富力金禧城A区5栋1单元2402"
    assert patch["delivery_note"] == ""


def test_parse_supplemental_order_text_from_address_only_text():
    patch = parse_supplemental_order_text(
        "张春娜[2666]15789799611山西省太原市小店区北营街道富力金禧城A区5栋1单元2402[2666]"
    )

    assert patch["recipient_name"] == "张春娜"
    assert patch["phone_number"] == "15789799611"
    assert patch["code"] == "2666"
    assert patch["address"] == "山西省太原市小店区北营街道富力金禧城A区5栋1单元2402"
    assert patch["delivery_note"] == "请电话送货上门谢谢【2666】"


def test_parse_supplemental_order_text_uses_product_order_id_as_fallback():
    patch = parse_supplemental_order_text(
        """
        【明日达】赵露思同款27000澳大利亚进口婴儿水宝宝水高偏矿泉水
        商品单ID:6925968364688539154
        单价/数量 ¥150.00 x1
        商家收入金额 ¥60.00
        收货信息 桃子 [8131] 17804472821 虚拟号 山东省潍坊市寿光市洛城街道洛城街道永泰花园小区 [8131]
        """
    )

    assert patch["order_id"] == "6925968364688539154"
