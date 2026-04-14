from __future__ import annotations

import mimetypes
from urllib.parse import parse_qs, urlparse

import requests


class FeishuClient:
    def __init__(self, app_id: str, app_secret: str, table_app_token: str, table_id: str):
        self.app_id = app_id
        self.app_secret = app_secret
        self.table_app_token = table_app_token
        self.table_id = table_id

    def get_tenant_access_token(self) -> str:
        payload = self._request_json(
            "POST",
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
        prepared_fields, image_field_names = self._materialize_fields(access_token, fields)
        return self._submit_record_request(
            "POST",
            access_token,
            prepared_fields,
            image_field_names=image_field_names,
        )

    def update_record(self, access_token: str, record_id: str, fields: dict) -> dict:
        prepared_fields, image_field_names = self._materialize_fields(access_token, fields)
        return self._submit_record_request(
            "PUT",
            access_token,
            prepared_fields,
            record_id=record_id,
            image_field_names=image_field_names,
        )

    def delete_record(self, access_token: str, record_id: str) -> dict:
        return self._request_json(
            "DELETE",
            "https://open.feishu.cn/open-apis/bitable/v1/apps/"
            f"{self.table_app_token}/tables/{self.table_id}/records/{record_id}",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json; charset=utf-8",
            },
            error_prefix="飞书删除失败",
        )

    def list_field_names(self, access_token: str) -> set[str]:
        payload = self._request_json(
            "GET",
            "https://open.feishu.cn/open-apis/bitable/v1/apps/"
            f"{self.table_app_token}/tables/{self.table_id}/fields",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"page_size": 500},
            error_prefix="飞书字段检测失败",
        )
        items = payload.get("data", {}).get("items", [])
        if not isinstance(items, list):
            return set()
        field_names: set[str] = set()
        for item in items:
            if not isinstance(item, dict):
                continue
            name = str(item.get("field_name", "")).strip()
            if name:
                field_names.add(name)
        return field_names

    def resolve_bitable_from_wiki_url(
        self,
        wiki_url: str,
        access_token: str | None = None,
    ) -> dict[str, str]:
        cleaned_url = str(wiki_url).strip()
        parsed = urlparse(cleaned_url)
        if "/wiki/" not in parsed.path:
            raise ValueError("请填写有效的飞书 wiki 表格链接")
        query = parse_qs(parsed.query)
        table_id = str((query.get("table") or [""])[0]).strip()
        if not table_id:
            raise ValueError("链接里缺少 Table ID")
        wiki_token = parsed.path.rsplit("/", 1)[-1].strip()
        if not wiki_token:
            raise ValueError("链接里缺少 wiki token")

        tenant_token = access_token or self.get_tenant_access_token()
        payload = self._request_json(
            "GET",
            "https://open.feishu.cn/open-apis/wiki/v2/spaces/get_node",
            headers={"Authorization": f"Bearer {tenant_token}"},
            params={"token": wiki_token},
            error_prefix="飞书链接解析失败",
        )
        node = payload.get("data", {}).get("node", {})
        obj_type = str(node.get("obj_type", "")).strip()
        app_token = str(node.get("obj_token", "")).strip()
        if obj_type != "bitable" or not app_token:
            raise ValueError("该 wiki 链接没有指向多维表格")

        return {
            "app_token": app_token,
            "table_id": table_id,
            "wiki_url": cleaned_url,
        }

    def _submit_record_request(
        self,
        method: str,
        access_token: str,
        prepared_fields: dict,
        *,
        record_id: str = "",
        image_field_names: set[str] | None = None,
    ) -> dict:
        if record_id:
            url = (
                "https://open.feishu.cn/open-apis/bitable/v1/apps/"
                f"{self.table_app_token}/tables/{self.table_id}/records/{record_id}"
            )
        else:
            url = (
                "https://open.feishu.cn/open-apis/bitable/v1/apps/"
                f"{self.table_app_token}/tables/{self.table_id}/records"
            )
        try:
            return self._request_json(
                method,
                url,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json; charset=utf-8",
                },
                json_body={"fields": prepared_fields},
                error_prefix="飞书写入失败",
            )
        except ValueError as exc:
            image_field_names = image_field_names or set()
            if not image_field_names or "TextFieldConvFail" not in str(exc):
                raise
            reduced_fields = {
                key: value for key, value in prepared_fields.items() if key not in image_field_names
            }
            return self._request_json(
                method,
                url,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json; charset=utf-8",
                },
                json_body={"fields": reduced_fields},
                error_prefix="飞书写入失败",
            )

    def _materialize_fields(self, access_token: str, fields: dict) -> tuple[dict, set[str]]:
        prepared: dict = {}
        image_field_names: set[str] = set()
        for key, value in dict(fields).items():
            if isinstance(value, list) and value and all(isinstance(item, dict) for item in value):
                local_paths = [str(item.get("local_path", "")).strip() for item in value if item.get("local_path")]
                if local_paths:
                    file_tokens = [
                        {"file_token": self.upload_bitable_image(access_token, image_path)}
                        for image_path in local_paths
                    ]
                    if file_tokens:
                        prepared[key] = file_tokens
                        image_field_names.add(key)
                    continue
            prepared[key] = value
        return prepared, image_field_names

    def upload_bitable_image(self, access_token: str, image_path: str) -> str:
        mime_type = mimetypes.guess_type(image_path)[0] or "image/png"
        with open(image_path, "rb") as handle:
            file_bytes = handle.read()
        response = requests.post(
            "https://open.feishu.cn/open-apis/drive/v1/medias/upload_all",
            headers={"Authorization": f"Bearer {access_token}"},
            data={
                "file_name": image_path.rsplit("/", 1)[-1],
                "parent_type": "bitable_image",
                "parent_node": self.table_app_token,
                "size": str(len(file_bytes)),
            },
            files={"file": (image_path.rsplit("/", 1)[-1], file_bytes, mime_type)},
            timeout=30,
        )
        payload = self._parse_response_payload(response, "飞书图片上传失败")
        data = payload.get("data", {})
        if not isinstance(data, dict):
            raise ValueError("飞书图片上传失败：响应里缺少文件信息")
        file_token = str(data.get("file_token", "")).strip() or str(data.get("token", "")).strip()
        if not file_token:
            raise ValueError("飞书图片上传失败：响应里缺少 file_token")
        return file_token

    @staticmethod
    def _request_json(
        method: str,
        url: str,
        *,
        headers: dict,
        error_prefix: str,
        json_body: dict | None = None,
        params: dict | None = None,
    ) -> dict:
        response = requests.request(
            method,
            url,
            headers=headers,
            json=json_body,
            params=params,
            timeout=30,
        )
        return FeishuClient._parse_response_payload(response, error_prefix)

    @staticmethod
    def _parse_response_payload(response, error_prefix: str) -> dict:
        try:
            payload = response.json()
        except ValueError as exc:
            response.raise_for_status()
            raise ValueError(f"{error_prefix}：接口响应不是合法 JSON") from exc
        if not isinstance(payload, dict):
            response.raise_for_status()
            raise ValueError(f"{error_prefix}：接口响应格式不正确")
        code = payload.get("code", 0)
        if code not in (0, None):
            message = str(payload.get("msg", "")).strip() or "未知错误"
            raise ValueError(f"{error_prefix}：{message}")
        response.raise_for_status()
        return payload
