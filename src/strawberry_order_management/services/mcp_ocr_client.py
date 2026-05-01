from __future__ import annotations

import json
import os
import select
import shlex
import subprocess
import tempfile
import time
from io import BytesIO
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from PIL import Image, ImageOps


MAX_OCR_IMAGE_SIDE = 2200
MCP_RESPONSE_TIMEOUT_SECONDS = 90
_HEADER_SEPARATOR = b"\r\n\r\n"


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
                                "如果是微信小店虚拟号，请保留“姓名（分机号） 手机号-分机号 地址（拨打请输入分机号）”这种原始结构。"
                                "如果是微信电脑端订单，请尽量保留“详细收货信息 / 收件人 / 收货地址 / 虚拟号 / 分机号”这些标签。"
                                "不要添加额外说明。"
                            ),
                            "image_source": str(image_path),
                        },
                    },
                },
            )
            payload = self._read_response(process, 2)
        except ValueError as exc:
            raise ValueError(self._friendly_error(str(exc))) from exc
        finally:
            self._close_process(process)

        result = payload.get("result") if isinstance(payload, dict) else None
        if not isinstance(result, dict):
            raise ValueError("MCP OCR 返回格式无效")
        if result.get("isError"):
            error_text = self._extract_text_result(result) or "MCP OCR 调用失败"
            raise ValueError(self._friendly_error(error_text))

        text = self._extract_text_result(result)
        if not text:
            raise ValueError("MCP OCR 未返回可识别文本")
        return text

    @staticmethod
    def _send(process, payload: dict) -> None:
        if process.stdin is None:
            raise ValueError("MCP 进程未提供 stdin")
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        process.stdin.write(body + b"\n")
        process.stdin.flush()

    @staticmethod
    def _read_response(process, expected_id: int) -> dict:
        if process.stdout is None:
            raise ValueError("MCP 进程未提供 stdout")
        deadline = time.monotonic() + MCP_RESPONSE_TIMEOUT_SECONDS
        while True:
            payload = McpOCRClient._read_message(process, deadline)
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
    def _read_message(process, deadline: float) -> dict:
        if process.stdout is None:
            raise ValueError("MCP 进程未提供 stdout")
        headers: dict[str, str] = {}
        line = McpOCRClient._readline_with_deadline(process, deadline)
        if line == b"":
            stderr_output = process.stderr.read() if process.stderr is not None else b""
            stderr_text = (
                stderr_output.decode("utf-8", errors="replace")
                if isinstance(stderr_output, bytes)
                else str(stderr_output)
            )
            raise ValueError(f"MCP 进程提前退出。{stderr_text}".strip())
        stripped_line = line.strip()
        if stripped_line.startswith(b"{"):
            try:
                return json.loads(stripped_line.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ValueError("MCP 返回了无效 JSON") from exc
        decoded_line = line.decode("ascii", errors="replace").strip()
        if ":" in decoded_line:
            name, value = decoded_line.split(":", 1)
            headers[name.strip().lower()] = value.strip()
        while True:
            line = McpOCRClient._readline_with_deadline(process, deadline)
            if line == b"":
                raise ValueError("MCP 返回头不完整")
            if line in (b"\r\n", b"\n"):
                break
            decoded_line = line.decode("ascii", errors="replace").strip()
            if ":" not in decoded_line:
                continue
            name, value = decoded_line.split(":", 1)
            headers[name.strip().lower()] = value.strip()
        try:
            content_length = int(headers["content-length"])
        except (KeyError, ValueError) as exc:
            raise ValueError("MCP 返回缺少有效的 Content-Length") from exc
        body = McpOCRClient._read_bytes_with_deadline(process, content_length, deadline)
        if len(body) != content_length:
            raise ValueError("MCP 返回体长度不完整")
        try:
            return json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("MCP 返回了无效 JSON") from exc

    @staticmethod
    def _readline_with_deadline(process, deadline: float) -> bytes:
        if process.stdout is None:
            raise ValueError("MCP 进程未提供 stdout")
        McpOCRClient._wait_until_readable(process, deadline)
        return process.stdout.readline()

    @staticmethod
    def _read_bytes_with_deadline(process, size: int, deadline: float) -> bytes:
        if process.stdout is None:
            raise ValueError("MCP 进程未提供 stdout")
        chunks: list[bytes] = []
        remaining = size
        while remaining > 0:
            McpOCRClient._wait_until_readable(process, deadline)
            chunk = process.stdout.read(remaining)
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)

    @staticmethod
    def _wait_until_readable(process, deadline: float) -> None:
        if process.stdout is None:
            raise ValueError("MCP 进程未提供 stdout")
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ValueError(
                f"MCP OCR 响应超时（超过 {MCP_RESPONSE_TIMEOUT_SECONDS} 秒），请重试；"
                "如果连续超时，请检查网络、MiniMax API Host、API Key 或 MCP 服务状态。"
            )
        try:
            fileno = process.stdout.fileno()
        except (AttributeError, OSError, ValueError):
            return
        readable, _, _ = select.select([fileno], [], [], remaining)
        if not readable:
            raise ValueError(
                f"MCP OCR 响应超时（超过 {MCP_RESPONSE_TIMEOUT_SECONDS} 秒），请重试；"
                "如果连续超时，请检查网络、MiniMax API Host、API Key 或 MCP 服务状态。"
            )

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
        image = ImageOps.exif_transpose(Image.open(BytesIO(image_bytes)))
        if max(image.size) > MAX_OCR_IMAGE_SIDE:
            image.thumbnail((MAX_OCR_IMAGE_SIDE, MAX_OCR_IMAGE_SIDE), Image.Resampling.LANCZOS)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as handle:
            image.save(handle, format="PNG")
            return Path(handle.name)

    @staticmethod
    def _friendly_error(error_text: str) -> str:
        text = str(error_text or "").strip()
        lowered = text.lower()
        network_markers = (
            "httpsconnectionpool",
            "connectionpool",
            "max retries",
            "connectionerror",
            "connection error",
            "timeout",
            "timed out",
        )
        if any(marker in lowered for marker in network_markers):
            return (
                "OCR 连接 MiniMax 失败，请稍后重试；如果连续失败，请检查网络、"
                f"MiniMax API Host 和 API Key。原始错误：{text}"
            )
        return text

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
