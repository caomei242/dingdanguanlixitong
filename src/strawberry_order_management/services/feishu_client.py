from __future__ import annotations

import requests


class FeishuClient:
    def __init__(self, app_id: str, app_secret: str, table_app_token: str, table_id: str):
        self.app_id = app_id
        self.app_secret = app_secret
        self.table_app_token = table_app_token
        self.table_id = table_id

    def create_record(self, access_token: str, fields: dict) -> dict:
        response = requests.post(
            "https://open.feishu.cn/open-apis/bitable/v1/apps/"
            f"{self.table_app_token}/tables/{self.table_id}/records",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"fields": fields},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()
