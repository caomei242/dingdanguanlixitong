from strawberry_order_management.extractors.multi_order import (
    parse_order_text_batch,
    split_order_text_blocks,
)


def _order_text(
    order_id: str,
    income_amount: str,
    recipient_name: str,
    phone_number: str,
    code: str,
) -> str:
    return f"""
    订单编号 {order_id}
    下单时间 2026-04-11 20:57:15
    订单状态 已发货
    商品信息
    测试商品 1L/桶*12袋
    单价/数量 ¥405.00 x1
    商家收入金额 ¥{income_amount}
    收货信息 {recipient_name} [{code}] {phone_number} 四川省成都市金牛区测试路1号 [{code}]
    """


def test_splits_and_parses_two_order_blocks():
    raw_text = "\n".join(
        [
            _order_text("6952003434324366473", "162.00", "何女士", "15781304332", "3612"),
            _order_text("69525544900545379782", "142.00", "田先生", "17804499356", "5842"),
        ]
    )

    blocks = split_order_text_blocks(raw_text)
    results = parse_order_text_batch(raw_text)

    assert len(blocks) == 2
    assert all(block.startswith("订单编号") for block in blocks)
    assert [result["ok"] for result in results] == [True, True]
    assert [result["order"].order_id for result in results] == [
        "6952003434324366473",
        "69525544900545379782",
    ]
    assert [result["order"].income_amount for result in results] == ["162.00", "142.00"]
    assert [result["order"].phone_number[-4:] for result in results] == ["4332", "9356"]


def test_single_order_text_returns_one_batch_result():
    raw_text = _order_text("6952003434324366473", "162.00", "何女士", "15781304332", "3612")

    blocks = split_order_text_blocks(raw_text)
    results = parse_order_text_batch(raw_text)

    assert blocks == [raw_text.strip()]
    assert len(results) == 1
    assert results[0]["ok"] is True
    assert results[0]["index"] == 1
    assert results[0]["order"].order_id == "6952003434324366473"


def test_failed_block_does_not_stop_following_order_parse():
    raw_text = "\n".join(
        [
            """
            订单编号 6952003434324366473
            这是一段不完整的订单文本
            """,
            _order_text("69525544900545379782", "142.00", "田先生", "17804499356", "5842"),
        ]
    )

    results = parse_order_text_batch(raw_text)

    assert len(results) == 2
    assert results[0]["index"] == 1
    assert results[0]["ok"] is False
    assert results[0]["order"] is None
    assert "解析失败" in results[0]["error"]
    assert results[1]["index"] == 2
    assert results[1]["ok"] is True
    assert results[1]["order"].order_id == "69525544900545379782"
    assert results[1]["error"] == ""
