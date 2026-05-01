from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests


class AutoOrderServiceManager:
    def __init__(
        self,
        *,
        startup_timeout_seconds: float = 12.0,
        probe_timeout_seconds: float = 1.5,
    ) -> None:
        self._startup_timeout_seconds = max(1.0, float(startup_timeout_seconds))
        self._probe_timeout_seconds = max(0.2, float(probe_timeout_seconds))
        self._managed_process: subprocess.Popen | None = None
        self._status_message = "未启动"

    def ensure_service(self, bridge_config: dict[str, Any]) -> bool:
        if self._is_service_reachable(bridge_config):
            self._status_message = "运行中（外部服务）" if self._managed_process is None else "运行中"
            return True
        return self._start_service(bridge_config, restarted=False)

    def restart_service(self, bridge_config: dict[str, Any]) -> bool:
        if self._managed_process is None and self._is_service_reachable(bridge_config):
            self._status_message = "运行中（外部服务）"
            return True
        self._stop_managed_process()
        return self._start_service(bridge_config, restarted=True)

    def should_restart_after_failure(self, bridge_config: dict[str, Any], message: str) -> bool:
        text = str(message or "").strip().lower()
        if not bridge_config.get("enabled"):
            return False
        if not self._is_service_reachable(bridge_config):
            return True
        return "503" in text or "service unavailable" in text

    def status_text(self, bridge_config: dict[str, Any] | None = None) -> str:
        bridge_config = dict(bridge_config or {})
        if bridge_config and not bridge_config.get("enabled"):
            return "桥接未启用"
        if bridge_config and not str(bridge_config.get("base_url", "")).strip():
            return "请先填写自动拍单服务 Base URL"
        if self._is_service_reachable(bridge_config):
            return "运行中（外部服务）" if self._managed_process is None else "运行中"
        if self._managed_process is not None:
            exit_code = self._managed_process.poll()
            if exit_code is None:
                return "启动中"
            return f"异常退出（退出码 {exit_code}）"
        return self._status_message

    def shutdown(self) -> None:
        self._stop_managed_process()
        self._status_message = "未启动"

    def _start_service(self, bridge_config: dict[str, Any], *, restarted: bool) -> bool:
        host, port = self._resolve_host_and_port(bridge_config)
        api_key = str(bridge_config.get("api_key", "")).strip()
        if not host or port <= 0:
            self._status_message = "启动失败：Base URL 无效"
            return False
        if not api_key:
            self._status_message = "启动失败：请先填写自动拍单服务 API Key"
            return False

        command = [
            sys.executable,
            "-m",
            "strawberry_order_management.mock_auto_order_service",
            "--real",
            "--host",
            host,
            "--port",
            str(port),
            "--api-key",
            api_key,
        ]
        env = os.environ.copy()
        project_src = str(Path(__file__).resolve().parents[2])
        existing_pythonpath = env.get("PYTHONPATH", "").strip()
        env["PYTHONPATH"] = (
            f"{project_src}{os.pathsep}{existing_pythonpath}" if existing_pythonpath else project_src
        )
        self._status_message = "重启中" if restarted else "启动中"
        self._managed_process = subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
            start_new_session=True,
        )
        deadline = time.monotonic() + self._startup_timeout_seconds
        while time.monotonic() < deadline:
            if self._is_service_reachable(bridge_config):
                self._status_message = "运行中"
                return True
            if self._managed_process.poll() is not None:
                exit_code = self._managed_process.returncode
                self._managed_process = None
                self._status_message = f"异常退出（退出码 {exit_code}）"
                return False
            time.sleep(0.25)
        self._status_message = "启动失败：等待服务响应超时"
        self._stop_managed_process()
        return False

    def _stop_managed_process(self) -> None:
        process = self._managed_process
        self._managed_process = None
        if process is None:
            return
        if process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)

    def _is_service_reachable(self, bridge_config: dict[str, Any] | None) -> bool:
        bridge_config = dict(bridge_config or {})
        base_url = str(bridge_config.get("base_url", "")).strip()
        api_key = str(bridge_config.get("api_key", "")).strip()
        if not base_url:
            return False
        check_url = f"{base_url.rstrip('/')}/auto-order/check"
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        try:
            response = requests.post(
                check_url,
                json={"jd_accounts": []},
                headers=headers,
                timeout=self._probe_timeout_seconds,
            )
        except requests.RequestException:
            host, port = self._resolve_host_and_port(bridge_config)
            if not host or port <= 0:
                return False
            try:
                with socket.create_connection((host, port), timeout=self._probe_timeout_seconds):
                    return True
            except OSError:
                return False
        return response.status_code < 500

    @staticmethod
    def _resolve_host_and_port(bridge_config: dict[str, Any]) -> tuple[str, int]:
        parsed = urlparse(str(bridge_config.get("base_url", "")).strip())
        host = parsed.hostname or ""
        if parsed.port is not None:
            return host, parsed.port
        if parsed.scheme == "https":
            return host, 443
        if parsed.scheme == "http":
            return host, 80
        return host, 0
