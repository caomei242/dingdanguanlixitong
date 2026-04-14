from pathlib import Path

import pytest

from strawberry_order_management.history import HistoryStore


def test_history_store_appends_full_snapshot_and_generates_record_id(tmp_path: Path):
    store = HistoryStore(tmp_path / "history.json")

    row = store.append(
        {
            "record_id": "evil",
            "shop_name": "乐宝零食店",
            "sync_source": "确认写入飞书",
            "status": "已写入飞书",
            "order_snapshot": {
                "order_id": "69525544900545379782",
                "recipient_name": "田宝山",
                "income_amount": "142.00",
            },
            "address_snapshot": {
                "output_one": "田宝山15784081541山东省德州市齐河县晏城街道玫瑰园4号楼",
                "output_two": "请电话送货上门谢谢【5842】",
            },
            "created_at": "2026-04-13T10:24:18",
        }
    )

    assert row["record_id"]
    assert row["record_id"] != "evil"
    assert row["order_snapshot"]["recipient_name"] == "田宝山"
    assert row["address_snapshot"]["output_two"] == "请电话送货上门谢谢【5842】"
    assert store.list_items()[0]["record_id"] == row["record_id"]


def test_history_store_get_update_and_delete(tmp_path: Path):
    store = HistoryStore(tmp_path / "history.json")
    row = store.append({"shop_name": "乐宝零食店", "status": "仅存历史"})

    fetched = store.get(row["record_id"])
    assert fetched["status"] == "仅存历史"

    updated = store.update(
        row["record_id"],
        {"record_id": "evil", "status": "写入失败", "message": "FieldNameNotFound"},
    )
    assert updated["status"] == "写入失败"
    assert updated["record_id"] == row["record_id"]
    assert store.get(row["record_id"])["message"] == "FieldNameNotFound"

    with pytest.raises(KeyError):
        store.update("missing", {"status": "写入失败"})

    store.delete(row["record_id"])
    assert store.list_items() == []

    with pytest.raises(KeyError):
        store.get(row["record_id"])

    with pytest.raises(KeyError):
        store.delete("missing")


def test_history_store_update_status_wrapper_still_works(tmp_path: Path):
    store = HistoryStore(tmp_path / "history.json")
    row = store.append({"shop_name": "乐宝零食店", "status": "仅存历史"})

    store.update_status(row["record_id"], "写入失败")

    assert store.get(row["record_id"])["status"] == "写入失败"


def test_history_store_treats_invalid_json_as_empty_history(tmp_path: Path):
    path = tmp_path / "history.json"
    path.write_text("{not valid json}", encoding="utf-8")

    store = HistoryStore(path)

    assert store.list_items() == []


def test_history_store_normalizes_legacy_flat_rows(tmp_path: Path):
    path = tmp_path / "history.json"
    path.write_text(
        '[{"shop_name":"草莓店","order_id":"1","recipient_name":"何女士","status":"已写入飞书","message":"oops","created_at":"2026-04-13T10:24:18"}]',
        encoding="utf-8",
    )

    store = HistoryStore(path)
    row = store.list_items()[0]

    assert row["order_snapshot"]["order_id"] == "1"
    assert row["order_snapshot"]["recipient_name"] == "何女士"
    assert "shop_name" not in row["order_snapshot"]
    assert "status" not in row["order_snapshot"]
    assert "message" not in row["order_snapshot"]
    assert "created_at" not in row["order_snapshot"]
    assert row["address_snapshot"]["output_one"] == ""
    assert row["address_snapshot"]["output_two"] == ""
    assert row["sync_source"] == "-"


def test_history_store_backfills_feishu_record_id_from_nested_feishu_result(tmp_path: Path):
    store = HistoryStore(tmp_path / "history.json")

    row = store.append(
        {
            "shop_name": "乐宝零食店",
            "status": "已写入飞书",
            "message": "写入成功",
            "feishu_result": {"code": 0, "data": {"record": {"record_id": "rec_nested_1"}}},
            "order_snapshot": {"order_id": "order-1"},
            "address_snapshot": {"output_one": "", "output_two": ""},
        }
    )

    loaded = store.get(row["record_id"])

    assert loaded["feishu_record_id"] == "rec_nested_1"
