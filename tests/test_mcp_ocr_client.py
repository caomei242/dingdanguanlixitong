from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from PIL import Image

from strawberry_order_management.services.mcp_ocr_client import McpOCRClient


def _sample_png_bytes() -> bytes:
    image = Image.new("RGB", (2, 2), "#ff4b6e")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


class _WritableBuffer:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def write(self, value: str) -> int:
        self.lines.append(value)
        return len(value)

    def flush(self) -> None:
        return None


class FakeProcess:
    def __init__(self, responses: list[dict]) -> None:
        self.stdin = _WritableBuffer()
        self.stdout = io.StringIO("".join(json.dumps(item) + "\n" for item in responses))
        self.stderr = io.StringIO("")
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
    written_lines = [json.loads(line) for line in captured["process"].stdin.lines]
    assert written_lines[0]["method"] == "initialize"
    assert written_lines[1]["method"] == "notifications/initialized"
    assert written_lines[2]["method"] == "tools/call"
    assert written_lines[2]["params"]["name"] == "understand_image"
    assert Path(written_lines[2]["params"]["arguments"]["image_source"]).suffix == ".png"


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
