from __future__ import annotations

import json
import os
import shlex
import subprocess
import tempfile
from io import BytesIO
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from PIL import Image


class McpOCRClient:
    def __init__(self, command: str, api_key: str, api_host: str):
        self.command = command.strip()
        self.api_key = api_key
        self.api_host = _normalize_api_host(api_host)

    def extract_text(self, image_bytes: bytes) -> str:
        if not self.command:
            raise ValueError("请先在设置页填写 MCP 命令")

        image_path = self._write_temp_image(image_bytes)
        try:
            result = self._call_understand_image(image_path)
        finally:
            image_path.unlink(missing_ok=True)
        return result

    def _call_understand_image(self, image_path: Path) -> str:
        args = shlex.split(self.command)
        env = os.environ.copy()
        env["MINIMAX_API_KEY"] = self.api_key
        env["MINIMAX_API_HOST"] = self.api_host

        try:
            process = subprocess.Popen(
                args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
            )
        except FileNotFoundError as exc:
            raise ValueError(
                "未找到 MCP 命令，请先安装 uv/uvx，或在设置页填写可执行命令的绝对路径。"
            ) from exc

        try:
            self._send(
                process,
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {
                            "name": "strawberry-order-management",
                            "version": "0.1.0",
                        },
                    },
                },
            )
            self._read_response(process, 1)
            self._send(
                process,
                {
                    "jsonrpc": "2.0",
                    "method": "notifications/initialized",
                    "params": {},
                },
            )
            self._send(
                process,
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {
                        "name": "understand_image",
                        "arguments": {
                            "prompt": (
                                "请识别这张订单截图，输出尽量完整、可解析的中文原始文本。"
                                "尽量把每个字段单独成行，尤其是收货信息尽量按“姓名 [编号] 手机号 地址 [编号]”的顺序输出。"
                                "不要添加额外说明。"
                            ),
                            "image_source": str(image_path),
                        },
                    },
                },
            )
            payload = self._read_response(process, 2)
        finally:
            self._close_process(process)

        result = payload.get("result") if isinstance(payload, dict) else None
        if not isinstance(result, dict):
            raise ValueError("MCP OCR 返回格式无效")
        if result.get("isError"):
            raise ValueError(self._extract_text_result(result) or "MCP OCR 调用失败")

        text = self._extract_text_result(result)
        if not text:
            raise ValueError("MCP OCR 未返回可识别文本")
        return text

    @staticmethod
    def _send(process, payload: dict) -> None:
        if process.stdin is None:
            raise ValueError("MCP 进程未提供 stdin")
        process.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
        process.stdin.flush()

    @staticmethod
    def _read_response(process, expected_id: int) -> dict:
        if process.stdout is None:
            raise ValueError("MCP 进程未提供 stdout")
        while True:
            line = process.stdout.readline()
            if line == "":
                stderr_output = process.stderr.read() if process.stderr is not None else ""
                raise ValueError(f"MCP 进程提前退出。{stderr_output}".strip())

            payload = json.loads(line)
            if "id" not in payload:
                continue
            if payload["id"] != expected_id:
                continue
            if "error" in payload:
                error = payload["error"]
                if isinstance(error, dict):
                    raise ValueError(str(error.get("message", "MCP 调用失败")))
                raise ValueError("MCP 调用失败")
            return payload

    @staticmethod
    def _extract_text_result(result: dict) -> str:
        content = result.get("content")
        if not isinstance(content, list):
            return ""
        texts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                texts.append(str(item.get("text", "")).strip())
        return "\n".join(text for text in texts if text).strip()

    @staticmethod
    def _write_temp_image(image_bytes: bytes) -> Path:
        image = Image.open(BytesIO(image_bytes))
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as handle:
            image.save(handle, format="PNG")
            return Path(handle.name)

    @staticmethod
    def _close_process(process) -> None:
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()


def _normalize_api_host(api_host: str) -> str:
    raw = api_host.strip()
    if not raw:
        return raw
    parts = urlsplit(raw)
    path = parts.path.rstrip("/")
    if path == "/v1":
        path = ""
    return urlunsplit((parts.scheme, parts.netloc, path, "", ""))
