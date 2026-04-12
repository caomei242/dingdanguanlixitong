from strawberry_order_management.extractors.address import extract_address_payload


def test_extracts_clean_address_and_delivery_note():
    payload = extract_address_payload(
        "何女士[3612]15781304332四川省成都市金牛区营门口街道友谊花园9-2304[3612]"
    )

    assert payload.cleaned_text == "何女士15781304332四川省成都市金牛区营门口街道友谊花园9-2304"
    assert payload.delivery_note == "请电话送货上门谢谢【3612】"
    assert payload.code == "3612"


def test_rejects_mismatched_prefix_suffix_codes():
    try:
        extract_address_payload("何女士[3612]15781304332四川省成都市[9999]")
    except ValueError as exc:
        assert "编号不一致" in str(exc)
    else:
        raise AssertionError("expected ValueError")
