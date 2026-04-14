from pathlib import Path

from strawberry_order_management.config import ConfigStore


def test_config_store_round_trips_values(tmp_path: Path):
    store = ConfigStore(tmp_path / "config.json")
    store.save(
        {
            "ocr_base_url": "https://ocr.example.com",
            "helper_base_url": "https://helper.example.com",
            "feishu_app_id": "cli_xxx",
            "feishu_table_id": "tbl_xxx",
        }
    )

    loaded = store.load()
    assert loaded["ocr_base_url"] == "https://ocr.example.com"
    assert loaded["feishu_table_id"] == "tbl_xxx"


def test_config_store_treats_invalid_json_as_empty_config(tmp_path: Path):
    path = tmp_path / "config.json"
    path.write_text("{not valid json}", encoding="utf-8")

    store = ConfigStore(path)

    assert store.load() == {}
