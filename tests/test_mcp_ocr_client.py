from __future__ import annotations

import io
import json
import os
from pathlib import Path

import pytest
from PIL import Image

from strawberry_order_management.services.mcp_ocr_client import (
    MCP_RESPONSE_TIMEOUT_SECONDS,
    McpOCRClient,
)


def _sample_png_bytes() -> bytes:
    image = Image.new("RGB", (2, 2), "#ff4b6e")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


class _WritableBuffer:
    def __init__(self) -> None:
        self.buffer = bytearray()

    def write(self, value: bytes) -> int:
        self.buffer.extend(value)
        return len(value)

    def flush(self) -> None:
        return None


class FakeProcess:
    def __init__(self, responses: list[dict]) -> None:
        self.stdin = _WritableBuffer()
        self.stdout = io.BytesIO(b"".join(_encode_line(item) for item in responses))
        self.stderr = io.BytesIO(b"")
        self.terminated = False
        self.killed = False

    def poll(self):
        return None

    def terminate(self) -> None:
        self.terminated = True

    def wait(self, timeout=None) -> int:
        return 0

    def kill(self) -> None:
        self.killed = True


def _encode_frame(payload: dict) -> bytes:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    return f"Content-Length: {len(body)}\r\n\r\n".encode("ascii") + body


def _encode_line(payload: dict) -> bytes:
    return json.dumps(payload, ensure_ascii=False).encode("utf-8") + b"\n"


def _decode_frames(raw: bytes) -> list[dict]:
    if raw.strip().startswith(b"{"):
        return [json.loads(line.decode("utf-8")) for line in raw.splitlines() if line.strip()]
    frames: list[dict] = []
    cursor = 0
    while cursor < len(raw):
        separator = raw.find(b"\r\n\r\n", cursor)
        assert separator >= 0
        header_block = raw[cursor:separator].decode("ascii")
        headers = {}
        for line in header_block.split("\r\n"):
            name, value = line.split(":", 1)
            headers[name.strip().lower()] = value.strip()
        content_length = int(headers["content-length"])
        cursor = separator + 4
        body = raw[cursor : cursor + content_length]
        frames.append(json.loads(body.decode("utf-8")))
        cursor += content_length
    return frames


def test_mcp_ocr_client_calls_understand_image_over_stdio(monkeypatch: pytest.MonkeyPatch):
    captured: dict[str, object] = {}
    responses = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "MiniMax", "version": "1.0.0"},
            },
        },
        {
            "jsonrpc": "2.0",
            "id": 2,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": "订单编号 1\n下单时间 2026-04-11 20:57:15",
                    }
                ],
                "isError": False,
            },
        },
    ]

    def fake_popen(args, stdin=None, stdout=None, stderr=None, text=None, env=None):
        captured["args"] = args
        captured["env"] = env
        process = FakeProcess(responses)
        captured["process"] = process
        return process

    monkeypatch.setattr(
        "strawberry_order_management.services.mcp_ocr_client.subprocess.Popen",
        fake_popen,
    )

    client = McpOCRClient(
        command="uvx minimax-coding-plan-mcp -y",
        api_key="secret",
        api_host="https://api.minimaxi.com",
    )

    text = client.extract_text(_sample_png_bytes())

    assert text == "订单编号 1\n下单时间 2026-04-11 20:57:15"
    assert captured["args"] == ["uvx", "minimax-coding-plan-mcp", "-y"]
    assert captured["env"]["MINIMAX_API_KEY"] == "secret"
    assert captured["env"]["MINIMAX_API_HOST"] == "https://api.minimaxi.com"
    written_messages = _decode_frames(captured["process"].stdin.buffer)
    assert written_messages[0]["method"] == "initialize"
    assert written_messages[1]["method"] == "notifications/initialized"
    assert written_messages[2]["method"] == "tools/call"
    assert written_messages[2]["params"]["name"] == "understand_image"
    prompt = written_messages[2]["params"]["arguments"]["prompt"]
    assert "微信小店" in prompt
    assert "姓名（分机号） 手机号-分机号 地址（拨打请输入分机号）" in prompt
    assert "详细收货信息 / 收件人 / 收货地址 / 虚拟号 / 分机号" in prompt
    assert Path(written_messages[2]["params"]["arguments"]["image_source"]).suffix == ".png"


def test_mcp_ocr_client_downscales_large_screenshots_before_sending(
):
    image = Image.new("RGB", (5000, 3000), "#ffffff")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")

    image_path = McpOCRClient._write_temp_image(buffer.getvalue())
    try:
        prepared = Image.open(image_path)
        assert max(prepared.size) == 2200
    finally:
        image_path.unlink(missing_ok=True)


def test_mcp_ocr_client_surfaces_network_errors_clearly(monkeypatch: pytest.MonkeyPatch):
    responses = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {"protocolVersion": "2024-11-05", "capabilities": {}},
        },
        {
            "jsonrpc": "2.0",
            "id": 2,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": "HTTPSConnectionPool(host='api.minimaxi.com', port=443): Max retries exceeded",
                    }
                ],
                "isError": True,
            },
        },
    ]

    def fake_popen(args, stdin=None, stdout=None, stderr=None, text=None, env=None):
        return FakeProcess(responses)

    monkeypatch.setattr(
        "strawberry_order_management.services.mcp_ocr_client.subprocess.Popen",
        fake_popen,
    )

    client = McpOCRClient(
        command="uvx minimax-coding-plan-mcp -y",
        api_key="secret",
        api_host="https://api.minimaxi.com",
    )

    with pytest.raises(ValueError, match="OCR 连接 MiniMax 失败"):
        client.extract_text(_sample_png_bytes())


def test_mcp_ocr_client_surfaces_stderr_network_errors_clearly(monkeypatch: pytest.MonkeyPatch):
    class EarlyExitProcess:
        def __init__(self):
            self.stdin = io.BytesIO()
            self.stdout = io.BytesIO(b"")
            self.stderr = io.BytesIO(
                b"HTTPSConnectionPool(host='api.minimaxi.com', port=443): Max retries exceeded"
            )
            self.terminated = False

        def terminate(self):
            self.terminated = True

        def wait(self, timeout=None) -> int:
            return 0

        def kill(self):
            self.terminated = True

    def fake_popen(args, stdin=None, stdout=None, stderr=None, text=None, env=None):
        return EarlyExitProcess()

    monkeypatch.setattr(
        "strawberry_order_management.services.mcp_ocr_client.subprocess.Popen",
        fake_popen,
    )

    client = McpOCRClient(
        command="uvx minimax-coding-plan-mcp -y",
        api_key="secret",
        api_host="https://api.minimaxi.com",
    )

    with pytest.raises(ValueError, match="OCR 连接 MiniMax 失败"):
        client.extract_text(_sample_png_bytes())


def test_mcp_ocr_client_surfaces_missing_command_clearly(monkeypatch: pytest.MonkeyPatch):
    def fake_popen(args, stdin=None, stdout=None, stderr=None, text=None, env=None):
        raise FileNotFoundError("uvx")

    monkeypatch.setattr(
        "strawberry_order_management.services.mcp_ocr_client.subprocess.Popen",
        fake_popen,
    )

    client = McpOCRClient(
        command="uvx minimax-coding-plan-mcp -y",
        api_key="secret",
        api_host="https://api.minimaxi.com",
    )

    with pytest.raises(ValueError, match="未找到 MCP 命令"):
        client.extract_text(_sample_png_bytes())


def test_mcp_ocr_client_times_out_when_mcp_never_returns(monkeypatch: pytest.MonkeyPatch):
    class HangingProcess:
        def __init__(self):
            self.stdin = _WritableBuffer()
            read_fd, write_fd = os.pipe()
            self.stdout = os.fdopen(read_fd, "rb", buffering=0)
            self._write_handle = os.fdopen(write_fd, "wb", buffering=0)
            self.stderr = io.BytesIO(b"")
            self.terminated = False

        def terminate(self):
            self.terminated = True
            self._write_handle.close()

        def wait(self, timeout=None) -> int:
            return 0

        def kill(self):
            self.terminated = True
            self._write_handle.close()

    def fake_popen(args, stdin=None, stdout=None, stderr=None, text=None, env=None):
        return HangingProcess()

    monkeypatch.setattr(
        "strawberry_order_management.services.mcp_ocr_client.subprocess.Popen",
        fake_popen,
    )
    monkeypatch.setattr(
        "strawberry_order_management.services.mcp_ocr_client.MCP_RESPONSE_TIMEOUT_SECONDS",
        0.01,
    )

    client = McpOCRClient(
        command="uvx minimax-coding-plan-mcp -y",
        api_key="secret",
        api_host="https://api.minimaxi.com",
    )

    with pytest.raises(ValueError, match="MCP OCR 响应超时"):
        client.extract_text(_sample_png_bytes())


def test_mcp_ocr_client_default_timeout_allows_slow_vision_responses():
    assert MCP_RESPONSE_TIMEOUT_SECONDS >= 90


def test_mcp_ocr_client_can_read_content_length_framed_responses(
    monkeypatch: pytest.MonkeyPatch,
):
    class FramedProcess(FakeProcess):
        def __init__(self, responses: list[dict]) -> None:
            super().__init__([])
            self.stdout = io.BytesIO(b"".join(_encode_frame(item) for item in responses))

    responses = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {"protocolVersion": "2024-11-05", "capabilities": {}},
        },
        {
            "jsonrpc": "2.0",
            "id": 2,
            "result": {
                "content": [{"type": "text", "text": "订单编号 2"}],
                "isError": False,
            },
        },
    ]

    def fake_popen(args, stdin=None, stdout=None, stderr=None, text=None, env=None):
        return FramedProcess(responses)

    monkeypatch.setattr(
        "strawberry_order_management.services.mcp_ocr_client.subprocess.Popen",
        fake_popen,
    )

    client = McpOCRClient(
        command="uvx minimax-coding-plan-mcp -y",
        api_key="secret",
        api_host="https://api.minimaxi.com/v1",
    )

    assert client.extract_text(_sample_png_bytes()) == "订单编号 2"
