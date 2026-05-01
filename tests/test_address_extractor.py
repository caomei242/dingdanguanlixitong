from strawberry_order_management.extractors.address import extract_address_payload


def test_extracts_clean_address_and_delivery_note():
    payload = extract_address_payload(
        "何女士[3612]15781304332四川省成都市金牛区营门口街道友谊花园9-2304[3612]"
    )

    assert payload.cleaned_text == "何女士15781304332四川省成都市金牛区营门口街道友谊花园9-2304"
    assert payload.delivery_note == "请电话送货上门谢谢【3612】"
    assert payload.code == "3612"


def test_removes_virtual_number_label_from_bracketed_address():
    payload = extract_address_payload(
        "娃娃 [7437]\n17895014935 虚拟号\n吉林省长春市南关区幸福乡 云湖府邸A1栋一单元502 [7437]"
    )

    assert payload.cleaned_text == "娃娃17895014935吉林省长春市南关区幸福乡云湖府邸A1栋一单元502"
    assert payload.delivery_note == "请电话送货上门谢谢【7437】"
    assert payload.code == "7437"


def test_rejects_mismatched_prefix_suffix_codes():
    try:
        extract_address_payload("何女士[3612]15781304332四川省成都市[9999]")
    except ValueError as exc:
        assert "编号不一致" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_extracts_address_from_name_phone_code_address_format():
    payload = extract_address_payload(
        "郑翔，15795949269-6026，广西壮族自治区北海市海城区 高德街道 北海大道5号北海恒大雅苑2栋2单元1901"
    )

    assert (
        payload.cleaned_text
        == "郑翔15795949269广西壮族自治区北海市海城区高德街道北海大道5号北海恒大雅苑2栋2单元1901"
    )
    assert payload.delivery_note == "请电话送货上门谢谢【6026】"
    assert payload.code == "6026"


def test_extracts_wechat_shop_virtual_number_format():
    payload = extract_address_payload(
        "潇寒（9530)，18401352224-9530，河北省石家庄市裕华区裕华区塔南路位同新村南区位同新村南区多层4幢1单元102（拨打请输入分机号9530）"
    )

    assert (
        payload.cleaned_text
        == "潇寒18401352224河北省石家庄市裕华区裕华区塔南路位同新村南区位同新村南区多层4幢1单元102"
    )
    assert payload.delivery_note == "请电话送货上门谢谢【9530】"
    assert payload.code == "9530"


def test_rejects_wechat_shop_virtual_number_with_mismatched_codes():
    try:
        extract_address_payload(
            "潇寒（9530），18401352224-1111，河北省石家庄市裕华区位同新村南区4幢1单元102（拨打请输入分机号9530）"
        )
    except ValueError as exc:
        assert "编号不一致" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_extracts_wechat_shop_screenshot_label_format():
    payload = extract_address_payload(
        "收件人 潇寒\n收货地址 河北省石家庄市裕华区裕华区塔南路位同新村南区位同新村南区多层4幢1单元102\n虚拟号 18401352224 分机号 9530"
    )

    assert (
        payload.cleaned_text
        == "潇寒18401352224河北省石家庄市裕华区裕华区塔南路位同新村南区位同新村南区多层4幢1单元102"
    )
    assert payload.delivery_note == "请电话送货上门谢谢【9530】"
    assert payload.code == "9530"


def test_extracts_plain_name_phone_address_without_virtual_code():
    payload = extract_address_payload(
        "张春娜15789799611山西省太原市小店区北营街道富力金禧城A区5栋1单元2402"
    )

    assert (
        payload.cleaned_text
        == "张春娜15789799611山西省太原市小店区北营街道富力金禧城A区5栋1单元2402"
    )
    assert payload.delivery_note == ""
    assert payload.code == ""


def test_extracts_plain_name_phone_address_with_tail_code():
    payload = extract_address_payload(
        "朱亦龙15781252286浙江省杭州市萧山区新塘街道金城路奥克斯金宸玖和府10幢1单元101[1767]"
    )

    assert (
        payload.cleaned_text
        == "朱亦龙15781252286浙江省杭州市萧山区新塘街道金城路奥克斯金宸玖和府10幢1单元101"
    )
    assert payload.delivery_note == "请电话送货上门谢谢【1767】"
    assert payload.code == "1767"
