import time

from strawberry_order_management.services.auto_order import (
    AutoOrderRequest,
    AutoOrderTaskTicket,
    LocalHttpAutoOrderBridge,
)
from strawberry_order_management.mock_auto_order_service import MockAutoOrderHttpServer


def _bridge_config() -> dict:
    return {
        "enabled": True,
        "base_url": "http://127.0.0.1:9000/",
        "api_key": "bridge-key",
        "submit_path": "/auto-order/tasks",
        "poll_path_template": "/auto-order/tasks/{task_id}",
        "poll_interval_seconds": 3,
        "timeout_seconds": 1200,
    }


def _request() -> AutoOrderRequest:
    return AutoOrderRequest(
        history_record_id="history-1",
        source="intake",
        shop_name="乐宝零食店",
        recipient_name="张可可",
        phone_number="15781251572",
        address="江苏省南京市秦淮区月牙湖街道观泓雅苑A区3栋A区3栋306",
        delivery_note="请电话送货上门谢谢【9471】",
        address_output_one="张可可15781251572江苏省南京市秦淮区月牙湖街道观泓雅苑A区3栋306",
        address_output_two="请电话送货上门谢谢【9471】",
        procurement_indices=(0,),
        procurement_items=(
            {
                "product_name": "27000-赵露思款",
                "quantity": "2",
                "cost": "89",
                "jd_link": "https://item.jd.com/1001.html",
            },
            {"product_name": "", "quantity": "", "cost": ""},
            {"product_name": "", "quantity": "", "cost": ""},
        ),
        jd_accounts=(
            {
                "name": "京东账号A",
                "environment": "/Users/gd/.jd/account-a",
                "enabled": True,
                "priority": 1,
            },
        ),
    )


def test_local_http_auto_order_bridge_submit_uses_bearer_and_fixed_payload(monkeypatch):
    captured = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "task_id": "task-1",
                "task_status": "queued",
                "message": "排队中",
                "submitted_at": "2026-04-17 12:00:00",
                "updated_at": "2026-04-17 12:00:00",
            }

    def fake_post(url: str, json: dict, headers: dict, timeout: float):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("strawberry_order_management.services.auto_order.requests.post", fake_post)

    bridge = LocalHttpAutoOrderBridge(_bridge_config())
    ticket = bridge.submit(_request())

    assert captured["url"] == "http://127.0.0.1:9000/auto-order/tasks"
    assert captured["headers"]["Authorization"] == "Bearer bridge-key"
    assert captured["json"]["history_record_id"] == "history-1"
    assert captured["json"]["recipient_name"] == "张可可"
    assert captured["json"]["address_output_one"] == "张可可15781251572江苏省南京市秦淮区月牙湖街道观泓雅苑A区3栋306"
    assert captured["json"]["address_output_two"] == "请电话送货上门谢谢【9471】"
    assert captured["json"]["procurement_items"] == [
        {
            "procurement_index": 0,
            "product_name": "27000-赵露思款",
            "quantity": "2",
            "jd_link": "https://item.jd.com/1001.html",
        }
    ]
    assert ticket.task_id == "task-1"
    assert ticket.task_status == "queued"


def test_local_http_auto_order_bridge_poll_uses_task_path_template(monkeypatch):
    captured = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "task_id": "task-1",
                "task_status": "running",
                "message": "执行中",
                "submitted_at": "2026-04-17 12:00:00",
                "updated_at": "2026-04-17 12:00:03",
                "item_results": [
                    {
                        "procurement_index": 0,
                        "status": "执行中",
                        "account_name": "京东账号A",
                        "jd_order_id": "",
                        "error_message": "",
                        "last_run_at": "2026-04-17 12:00:03",
                    }
                ],
            }

    def fake_get(url: str, headers: dict, timeout: float):
        captured["url"] = url
        captured["headers"] = headers
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("strawberry_order_management.services.auto_order.requests.get", fake_get)

    bridge = LocalHttpAutoOrderBridge(_bridge_config())
    snapshot = bridge.poll(
        AutoOrderTaskTicket(
            task_id="task-1",
            task_status="queued",
            message="排队中",
            submitted_at="2026-04-17 12:00:00",
            updated_at="2026-04-17 12:00:00",
        )
    )

    assert captured["url"] == "http://127.0.0.1:9000/auto-order/tasks/task-1"
    assert captured["headers"]["Authorization"] == "Bearer bridge-key"
    assert snapshot.task_status == "running"
    assert snapshot.item_results[0].status == "执行中"


def test_local_http_auto_order_bridge_can_talk_to_mock_service():
    server = MockAutoOrderHttpServer(host="127.0.0.1", port=0, api_key="bridge-key", processing_delay_seconds=0.01)
    server.start()
    try:
        bridge = LocalHttpAutoOrderBridge(
            {
                "enabled": True,
                "base_url": server.url(),
                "api_key": "bridge-key",
                "submit_path": "/auto-order/tasks",
                "poll_path_template": "/auto-order/tasks/{task_id}",
                "poll_interval_seconds": 1,
                "timeout_seconds": 1200,
            }
        )
        ticket = bridge.submit(_request())

        assert ticket.task_status == "queued"

        snapshot = ticket
        for _ in range(20):
            snapshot = bridge.poll(
                AutoOrderTaskTicket(
                    task_id=snapshot.task_id,
                    task_status=snapshot.task_status,
                    message=snapshot.message,
                    submitted_at=snapshot.submitted_at,
                    updated_at=snapshot.updated_at,
                )
            )
            if snapshot.task_status == "succeeded":
                break
            time.sleep(0.02)

        assert snapshot.task_status == "succeeded"
        assert snapshot.item_results[0].status == "待付款"
        assert snapshot.item_results[0].jd_order_id.startswith("JD")
    finally:
        server.stop()
