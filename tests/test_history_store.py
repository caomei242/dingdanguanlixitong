from pathlib import Path

from strawberry_order_management.history import HistoryStore


def test_history_store_appends_and_updates_status(tmp_path: Path):
    store = HistoryStore(tmp_path / "history.json")
    item = store.append(
        {
            "shop_name": "草莓店",
            "order_id": "6952003434324366473",
            "recipient_name": "何女士",
            "status": "pending_review",
        }
    )

    store.update_status(item["record_id"], "written")
    rows = store.list_items()

    assert rows[0]["order_id"] == "6952003434324366473"
    assert rows[0]["shop_name"] == "草莓店"
    assert rows[0]["status"] == "written"


def test_history_store_ignores_payload_record_id(tmp_path: Path):
    store = HistoryStore(tmp_path / "history.json")

    item = store.append(
        {
            "record_id": "evil",
            "order_id": "6952003434324366473",
            "status": "pending_review",
        }
    )

    assert item["record_id"] != "evil"
    assert store.list_items()[0]["record_id"] == item["record_id"]


def test_history_store_treats_invalid_json_as_empty_history(tmp_path: Path):
    path = tmp_path / "history.json"
    path.write_text("{not valid json}", encoding="utf-8")

    store = HistoryStore(path)

    assert store.list_items() == []


def test_history_store_raises_for_missing_record_id(tmp_path: Path):
    store = HistoryStore(tmp_path / "history.json")

    store.append(
        {
            "order_id": "6952003434324366473",
            "status": "pending_review",
        }
    )

    try:
        store.update_status("missing", "written")
    except KeyError as exc:
        assert "missing" in str(exc)
    else:
        raise AssertionError("expected KeyError")
