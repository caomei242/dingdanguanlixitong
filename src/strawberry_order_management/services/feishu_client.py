from __future__ import annotations

import requests


class FeishuClient:
    def __init__(self, app_id: str, app_secret: str, table_app_token: str, table_id: str):
        self.app_id = app_id
        self.app_secret = app_secret
        self.table_app_token = table_app_token
        self.table_id = table_id

    def get_tenant_access_token(self) -> str:
        payload = self._post_json(
            "https://open.feishu.cn/open-apis/auth/v3/app_access_token/internal",
            headers={"Content-Type": "application/json; charset=utf-8"},
            json_body={"app_id": self.app_id, "app_secret": self.app_secret},
            error_prefix="飞书鉴权失败",
        )
        tenant_access_token = str(payload.get("tenant_access_token", "")).strip()
        if not tenant_access_token:
            raise ValueError("飞书鉴权失败：响应里缺少 tenant_access_token")
        return tenant_access_token

    def create_record(self, access_token: str, fields: dict) -> dict:
        return self._post_json(
            "https://open.feishu.cn/open-apis/bitable/v1/apps/"
            f"{self.table_app_token}/tables/{self.table_id}/records",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json; charset=utf-8",
            },
            json_body={"fields": fields},
            error_prefix="飞书写入失败",
        )

    @staticmethod
    def _post_json(url: str, headers: dict, json_body: dict, error_prefix: str) -> dict:
        response = requests.post(
            url,
            headers=headers,
            json=json_body,
            timeout=30,
        )
        response.raise_for_status()
        try:
            payload = response.json()
        except ValueError as exc:
            raise ValueError(f"{error_prefix}：接口响应不是合法 JSON") from exc
        if not isinstance(payload, dict):
            raise ValueError(f"{error_prefix}：接口响应格式不正确")
        code = payload.get("code", 0)
        if code not in (0, None):
            message = str(payload.get("msg", "")).strip() or "未知错误"
            raise ValueError(f"{error_prefix}：{message}")
        return payload
