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


def test_history_store_normalizes_auto_order_fields_for_legacy_rows(tmp_path: Path):
    path = tmp_path / "history.json"
    path.write_text(
        """
        [
          {
            "record_id": "row-1",
            "shop_name": "乐宝零食店",
            "status": "已写入飞书",
            "order_snapshot": {
              "order_id": "order-1",
              "procurement_items": [
                {"product_name": "27000", "quantity": "1", "cost": "89"},
                {
                  "product_name": "瓶盖",
                  "quantity": "1",
                  "cost": "13.8",
                  "jd_status": "失败",
                  "jd_account_name": "京东账号A",
                  "jd_error_message": "当前版本未接入真实京东执行器",
                  "jd_last_run_at": "2026-04-17 10:00:00"
                }
              ]
            }
          }
        ]
        """,
        encoding="utf-8",
    )

    store = HistoryStore(path)
    row = store.list_items()[0]

    assert row["auto_order_status"] == ""
    assert row["auto_order_message"] == ""
    assert row["auto_order_last_run_at"] == ""
    assert row["auto_order_task_id"] == ""
    assert row["auto_order_task_status"] == ""
    assert row["auto_order_task_submitted_at"] == ""
    assert row["auto_order_task_last_polled_at"] == ""
    assert row["order_snapshot"]["procurement_items"][0].get("jd_status", "") == ""
    assert row["order_snapshot"]["procurement_items"][0].get("jd_account_name", "") == ""
    assert row["order_snapshot"]["procurement_items"][0].get("jd_order_id", "") == ""
    assert row["order_snapshot"]["procurement_items"][0].get("jd_error_message", "") == ""
    assert row["order_snapshot"]["procurement_items"][1]["jd_status"] == "失败"
    assert row["order_snapshot"]["procurement_items"][1]["jd_account_name"] == "京东账号A"


def test_history_store_strips_virtual_number_label_from_legacy_address_fields(tmp_path: Path):
    path = tmp_path / "history.json"
    path.write_text(
        """
        [
          {
            "record_id": "row-1",
            "shop_name": "乐宝零食店",
            "status": "已写入飞书",
            "order_snapshot": {
              "order_id": "order-1",
              "address": "虚拟号 河北省唐山市路南区广场街道 南湖公园内，世博园派出所"
            },
            "address_snapshot": {
              "output_one": "鲁世豪15780966869虚拟号河北省唐山市路南区广场街道南湖公园内，世博园派出所",
              "output_two": "请电话送货上门谢谢【6862】"
            }
          }
        ]
        """,
        encoding="utf-8",
    )

    store = HistoryStore(path)
    row = store.list_items()[0]

    assert row["order_snapshot"]["address"] == "河北省唐山市路南区广场街道 南湖公园内，世博园派出所"
    assert row["address_snapshot"]["output_one"] == "鲁世豪15780966869河北省唐山市路南区广场街道南湖公园内，世博园派出所"


def test_history_store_normalizes_latest_auto_order_debug_payload(tmp_path: Path):
    path = tmp_path / "history.json"
    path.write_text(
        """
        [
          {
            "record_id": "row-1",
            "shop_name": "乐宝零食店",
            "status": "已写入飞书",
            "order_snapshot": {"order_id": "order-1", "procurement_items": []}
          }
        ]
        """,
        encoding="utf-8",
    )

    store = HistoryStore(path)
    row = store.list_items()[0]

    assert row["auto_order_debug"] == {
        "steps": [],
        "screenshot_path": "",
        "updated_at": "",
        "stage": "",
        "summary": "",
    }
