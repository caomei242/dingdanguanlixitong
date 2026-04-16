from pathlib import Path

import pytest

from strawberry_order_management.expenses import ExpenseStore, default_expense_path


def test_expense_store_appends_and_generates_record_id(tmp_path: Path):
    store = ExpenseStore(tmp_path / "expenses.json")

    row = store.append(
        {
            "record_id": "evil",
            "expense_date": "2026-04-15",
            "scope_type": "订单级",
            "shop_name": "乐宝零食店",
            "order_id": "6952059303468209543",
            "category": "售后补偿",
            "amount": "10.00",
            "remark": "售后返现 10 元",
        }
    )

    assert row["record_id"]
    assert row["record_id"] != "evil"
    assert row["scope_type"] == "订单级"
    assert row["amount"] == "10.00"
    assert store.list_items()[0]["record_id"] == row["record_id"]


def test_expense_store_get_update_delete_and_invalid_json(tmp_path: Path):
    path = tmp_path / "expenses.json"
    store = ExpenseStore(path)
    row = store.append(
        {
            "expense_date": "2026-04-15",
            "scope_type": "店铺级",
            "shop_name": "乐宝零食店",
            "category": "软件服务",
            "amount": "99.00",
            "remark": "自动发货软件月费",
        }
    )

    fetched = store.get(row["record_id"])
    assert fetched["shop_name"] == "乐宝零食店"

    updated = store.update(
        row["record_id"],
        {
            "record_id": "evil",
            "amount": "109.00",
            "remark": "自动发货软件月费升级版",
        },
    )
    assert updated["record_id"] == row["record_id"]
    assert updated["amount"] == "109.00"
    assert store.get(row["record_id"])["remark"] == "自动发货软件月费升级版"

    with pytest.raises(KeyError):
        store.update("missing", {"amount": "1.00"})

    store.delete(row["record_id"])
    assert store.list_items() == []

    with pytest.raises(KeyError):
        store.get(row["record_id"])

    path.write_text("{not valid json}", encoding="utf-8")
    assert ExpenseStore(path).list_items() == []


def test_default_expense_path_points_to_config_directory():
    path = default_expense_path()

    assert path.name == "expenses.json"
    assert ".config" in str(path)
