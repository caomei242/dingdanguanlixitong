from __future__ import annotations

import json
import signal
import time
from pathlib import Path

from strawberry_order_management.config import default_config_path
from strawberry_order_management.history import HistoryStore, default_history_path
from strawberry_order_management.services.helper_client import HelperClient
from strawberry_order_management.services.mcp_ocr_client import McpOCRClient
from strawberry_order_management.services.mobile_order import MobileOrderHttpServer, MobileOrderService
from strawberry_order_management.services.ocr_client import OCRClient
from strawberry_order_management.services.pipeline import OrderPipeline


def _text(value: object) -> str:
    return str(value or "").strip()


def _load_config() -> dict:
    path = default_config_path()
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _find_shop(payload: dict, shop_name: str) -> dict:
    for shop in payload.get("shops", []) or []:
        if isinstance(shop, dict) and _text(shop.get("name")) == shop_name:
            return shop
    return {}


def _build_pipeline_if_ready(payload: dict) -> OrderPipeline | None:
    required_keys = ["ocr_api_key", "helper_base_url", "helper_api_key"]
    if payload.get("ocr_use_mcp"):
        required_keys.extend(["ocr_mcp_command", "ocr_base_url"])
    else:
        required_keys.append("ocr_base_url")
    if any(not payload.get(key) for key in required_keys):
        return None

    if payload.get("ocr_use_mcp"):
        ocr_client = McpOCRClient(
            payload["ocr_mcp_command"],
            payload["ocr_api_key"],
            payload["ocr_base_url"],
        )
    else:
        ocr_client = OCRClient(payload["ocr_base_url"], payload["ocr_api_key"])
    return OrderPipeline(
        ocr_client,
        HelperClient(payload["helper_base_url"], payload["helper_api_key"]),
        None,
    )


def main() -> int:
    payload = _load_config()
    if not payload.get("mobile_order_entry_enabled"):
        print("手机助手入口未启用，请先在草莓系统设置页启用。", flush=True)
        return 2

    api_key = _text(payload.get("mobile_order_entry_api_key"))
    if not api_key:
        print("缺少手机助手入口 API Key，请先在草莓系统设置页填写。", flush=True)
        return 2

    host = _text(payload.get("mobile_order_entry_host")) or "127.0.0.1"
    port = int(payload.get("mobile_order_entry_port") or 9020)
    default_shop = (
        _text(payload.get("intake_default_shop_name"))
        or _text(payload.get("selected_shop_name"))
        or "乐宝零食店"
    )
    default_platform = _text(_find_shop(payload, default_shop).get("platform"))
    service = MobileOrderService(
        HistoryStore(default_history_path()),
        default_shop_name=default_shop,
        default_platform=default_platform,
        procurement_templates=list(payload.get("procurement_templates") or []),
        order_pipeline=_build_pipeline_if_ready(payload),
    )
    server = MobileOrderHttpServer(service, api_key=api_key, host=host, port=port)
    server.start()
    print(f"手机助手入口运行中：{server.base_url}/mobile", flush=True)
    print(f"默认店铺：{default_shop} / {default_platform or '未配置平台'}", flush=True)

    stopped = False

    def _stop(_signum: int, _frame: object) -> None:
        nonlocal stopped
        stopped = True

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    while not stopped:
        time.sleep(1)
    server.stop()
    print("手机助手入口已停止", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
