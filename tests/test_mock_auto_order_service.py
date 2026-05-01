from __future__ import annotations

import time

import requests

from strawberry_order_management.mock_auto_order_service import (
    MockAutoOrderHttpServer,
)


def _task_payload(*, order_suffix: str = "1", procurement_items: list[dict] | None = None) -> dict:
    return {
        "history_record_id": f"history-{order_suffix}",
        "source": "intake",
        "shop_name": "乐宝零食店",
        "recipient_name": "张可可",
        "phone_number": "15781251572",
        "address": "江苏省南京市秦淮区月牙湖街道观泓雅苑A区3栋A区3栋306",
        "delivery_note": "请电话送货上门谢谢【9471】",
        "procurement_items": procurement_items
        or [
            {
                "procurement_index": 0,
                "product_name": "27000-赵露思款",
                "quantity": "1",
                "jd_link": "https://item.jd.com/1001.html",
            }
        ],
        "jd_accounts": [
            {
                "name": "京东账号A",
                "environment": "/Users/gd/.jd/account-a",
                "priority": 1,
            }
        ],
    }


def _auth_headers(api_key: str = "bridge-key") -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}"}


def test_mock_auto_order_server_requires_bearer_api_key():
    server = MockAutoOrderHttpServer(host="127.0.0.1", port=0, api_key="bridge-key", processing_delay_seconds=0.01)
    server.start()
    try:
        response = requests.post(
            server.url("/auto-order/tasks"),
            json=_task_payload(),
            timeout=3,
        )

        assert response.status_code == 401
        assert response.json()["message"] == "未授权的自动拍单请求"
    finally:
        server.stop()


def test_mock_auto_order_server_processes_task_until_ready_to_pay():
    server = MockAutoOrderHttpServer(host="127.0.0.1", port=0, api_key="bridge-key", processing_delay_seconds=0.01)
    server.start()
    try:
        submit_response = requests.post(
            server.url("/auto-order/tasks"),
            json=_task_payload(
                procurement_items=[
                    {
                        "procurement_index": 0,
                        "product_name": "27000-赵露思款",
                        "quantity": "1",
                        "jd_link": "https://item.jd.com/1001.html",
                    },
                    {
                        "procurement_index": 1,
                        "product_name": "瓶盖粉色配件",
                        "quantity": "1",
                        "jd_link": "https://item.jd.com/1002.html",
                    },
                ]
            ),
            headers=_auth_headers(),
            timeout=3,
        )

        ticket = submit_response.json()
        assert ticket["task_status"] == "queued"

        snapshot = ticket
        deadline = time.time() + 3
        while time.time() < deadline:
            snapshot = requests.get(
                server.url(f"/auto-order/tasks/{ticket['task_id']}"),
                headers=_auth_headers(),
                timeout=3,
            ).json()
            if snapshot["task_status"] == "succeeded":
                break
            time.sleep(0.02)

        assert snapshot["task_status"] == "succeeded"
        assert [item["status"] for item in snapshot["item_results"]] == ["待付款", "待付款"]
        assert snapshot["item_results"][0]["jd_order_id"].startswith("JD")
        assert snapshot["item_results"][1]["jd_order_id"].startswith("JD")
    finally:
        server.stop()


def test_mock_auto_order_server_processes_tasks_in_single_queue():
    server = MockAutoOrderHttpServer(host="127.0.0.1", port=0, api_key="bridge-key", processing_delay_seconds=0.15)
    server.start()
    try:
        first = requests.post(
            server.url("/auto-order/tasks"),
            json=_task_payload(
                order_suffix="1",
                procurement_items=[
                    {
                        "procurement_index": 0,
                        "product_name": "27000-赵露思款",
                        "quantity": "1",
                        "jd_link": "https://item.jd.com/1001.html",
                    },
                    {
                        "procurement_index": 1,
                        "product_name": "瓶盖粉色配件",
                        "quantity": "1",
                        "jd_link": "https://item.jd.com/1002.html",
                    },
                ],
            ),
            headers=_auth_headers(),
            timeout=3,
        ).json()
        second = requests.post(
            server.url("/auto-order/tasks"),
            json=_task_payload(order_suffix="2"),
            headers=_auth_headers(),
            timeout=3,
        ).json()

        time.sleep(0.05)
        first_snapshot = requests.get(
            server.url(f"/auto-order/tasks/{first['task_id']}"),
            headers=_auth_headers(),
            timeout=3,
        ).json()
        second_snapshot = requests.get(
            server.url(f"/auto-order/tasks/{second['task_id']}"),
            headers=_auth_headers(),
            timeout=3,
        ).json()

        assert first_snapshot["task_status"] in {"running", "succeeded"}
        assert second_snapshot["task_status"] == "queued"
    finally:
        server.stop()
