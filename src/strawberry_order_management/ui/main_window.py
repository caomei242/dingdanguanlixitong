from __future__ import annotations

from datetime import datetime
from typing import Optional

from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
    QMainWindow,
)

from strawberry_order_management.history import HistoryStore
from strawberry_order_management.models import ParsedOrder, ProcurementItem
from strawberry_order_management.services.feishu_client import FeishuClient
from strawberry_order_management.services.helper_client import HelperClient
from strawberry_order_management.services.mcp_ocr_client import McpOCRClient
from strawberry_order_management.services.ocr_client import OCRClient
from strawberry_order_management.services.pipeline import OrderPipeline, build_feishu_payload
from strawberry_order_management.ui.pages.history_page import HistoryPage
from strawberry_order_management.ui.pages.intake_page import IntakePage
from strawberry_order_management.ui.pages.settings_page import SettingsPage
from strawberry_order_management.ui.theme import apply_theme


class _SubmitWorker(QObject):
    finished = Signal(object)
    failed = Signal(object)

    def __init__(self, callback, task: dict):
        super().__init__()
        self._callback = callback
        self._task = task

    def run(self) -> None:
        try:
            result = self._callback(self._task)
        except Exception as exc:
            self.failed.emit(
                {
                    "message": str(exc),
                    "payload": self._task["payload"],
                    "history_record_id": self._task.get("history_record_id"),
                }
            )
            return
        self.finished.emit(result)


class MainWindow(QMainWindow):
    def __init__(
        self,
        on_settings_save=None,
        config_store=None,
        history_store=None,
        order_pipeline_factory=None,
    ) -> None:
        super().__init__()
        self.setWindowTitle("草莓订单管理系统")
        self._on_settings_save = on_settings_save
        self._config_store = config_store
        self._history_store = history_store
        self._order_pipeline_factory = order_pipeline_factory or self._build_order_pipeline
        self._submit_thread = None
        self._submit_worker = None

        self.nav = QListWidget()
        self.nav.addItems(["订单录入", "历史", "设置"])
        self.nav.setFixedWidth(118)

        self.stack = QStackedWidget()
        self.intake_page = IntakePage(
            on_process_image=self._extract_order_from_image,
            on_submit=self._handle_submit_request,
            on_save_history=self._handle_save_history_request,
        )
        self.history_page = HistoryPage()
        self.settings_page = SettingsPage(on_resolve_shop_link=self._resolve_shop_link)
        self.stack.addWidget(self.intake_page)
        self.stack.addWidget(self.history_page)
        self.stack.addWidget(self.settings_page)
        self.intake_page.product_library_requested.connect(self._handle_product_library_request)
        self.history_page.save_requested.connect(self._handle_history_save_request)
        self.history_page.delete_requested.connect(self._handle_history_delete_request)
        self.history_page.resubmit_requested.connect(self._handle_history_resubmit_request)

        brand_title = QLabel("草莓")
        brand_title.setObjectName("BrandTitle")
        brand_subtitle = QLabel("订单管理系统")
        brand_subtitle.setObjectName("BrandSubtitle")

        brand_box = QVBoxLayout()
        brand_box.setContentsMargins(0, 0, 0, 0)
        brand_box.setSpacing(2)
        brand_box.addWidget(brand_title)
        brand_box.addWidget(brand_subtitle)

        sidebar = QFrame()
        sidebar.setObjectName("ShellFrame")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(14, 14, 14, 14)
        sidebar_layout.setSpacing(12)
        sidebar_layout.addLayout(brand_box)
        sidebar_layout.addWidget(self.nav)
        sidebar_layout.addStretch(1)

        content = QFrame()
        content.setObjectName("ShellFrame")
        content_layout = QVBoxLayout(content)
        content_layout.addWidget(self.stack)

        root = QWidget()
        layout = QHBoxLayout(root)
        layout.addWidget(sidebar, 0)
        layout.addWidget(content, 1)
        self.setCentralWidget(root)

        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav.setCurrentRow(0)
        self.settings_page.save_requested.connect(self._handle_settings_save)

        if self._config_store is not None:
            payload = self._config_store.load()
            self.settings_page.load_payload(payload)
            self._sync_shop_selector(payload)
        if self._history_store is not None:
            self._reload_history_page()

        apply_theme(self)

    def _handle_settings_save(self, payload: dict) -> None:
        self._persist_settings_payload(payload)

    def _handle_save_history_request(self, payload: dict) -> None:
        self._sync_products_from_order(payload["order"])
        snapshot = self._build_history_snapshot(payload, "仅存历史", "仅存历史")
        self._save_history_snapshot(snapshot)
        self.intake_page.capture_widget.status_label.setText("已保存到历史")

    def _handle_submit_request(self, payload: dict) -> None:
        self._sync_products_from_order(payload["order"])
        snapshot = self._build_history_snapshot(payload, "确认写入飞书", "写入中")
        saved_row = self._save_history_snapshot(snapshot)
        try:
            task = self._build_feishu_submission_task(payload)
        except Exception as exc:
            message = str(exc)
            self.intake_page.capture_widget.status_label.setText(message)
            if saved_row is not None:
                self._update_history_snapshot(
                    saved_row["record_id"],
                    {
                        "status": "写入失败",
                        "message": message,
                        "feishu_result": {"error": message},
                    },
                )
            return
        self.intake_page.capture_widget.status_label.setText("写入飞书中...")
        self.intake_page.set_submit_in_progress(True)
        if saved_row is not None:
            task["history_record_id"] = saved_row["record_id"]
        self._start_submit_job(task)

    def _build_history_snapshot(
        self,
        payload: dict,
        sync_source: str,
        status: str,
        message: str = "",
        feishu_result: Optional[dict] = None,
    ) -> dict:
        order = payload["order"]
        row = {
            "shop_name": payload.get("shop_name") or "-",
            "sync_source": sync_source,
            "status": status,
            "message": message,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "order_snapshot": {
                "order_id": order.order_id,
                "placed_at": order.placed_at,
                "order_status": order.order_status,
                "product_name": order.product_name,
                "quantity": order.quantity,
                "order_amount": order.order_amount,
                "income_amount": order.income_amount,
                "recipient_name": order.recipient_name,
                "phone_number": order.phone_number,
                "code": order.code,
                "address": order.address,
                "delivery_note": order.delivery_note,
                "procurement_items": [
                    {
                        "product_name": item.product_name,
                        "quantity": item.quantity,
                        "cost": item.cost,
                    }
                    for item in order.procurement_items
                ],
            },
            "address_snapshot": {
                "output_one": self.intake_page.address_widget.output_one.toPlainText().strip(),
                "output_two": self.intake_page.address_widget.output_two.toPlainText().strip(),
            },
        }
        if feishu_result is not None:
            row["feishu_result"] = feishu_result
        return row

    def _save_history_snapshot(self, snapshot: dict) -> Optional[dict]:
        if self._history_store is None:
            return None
        row = self._history_store.append(snapshot)
        self._reload_history_page()
        return row

    def _update_history_snapshot(self, record_id: str, patch: dict) -> Optional[dict]:
        if self._history_store is None:
            return None
        try:
            row = self._history_store.update(record_id, patch)
        except KeyError:
            return None
        self._reload_history_page()
        return row

    def _reload_history_page(self) -> None:
        if self._history_store is None:
            return
        self.history_page.load_rows(self._history_store.list_items())

    def _handle_history_save_request(self, record_id: str, patch: dict) -> None:
        if self._history_store is None:
            return
        self._update_history_snapshot(record_id, patch)

    def _handle_history_delete_request(self, record_id: str) -> None:
        if self._history_store is None:
            return
        try:
            self._history_store.delete(record_id)
        except KeyError:
            pass
        self._reload_history_page()

    def _handle_history_resubmit_request(self, record_id: str) -> None:
        if self._history_store is None:
            return
        try:
            row = self._history_store.get(record_id)
        except KeyError:
            return

        payload = self._build_payload_from_history_row(row)
        try:
            task = self._build_feishu_submission_task(payload)
        except Exception as exc:
            message = str(exc)
            self.intake_page.capture_widget.status_label.setText(message)
            self._update_history_snapshot(
                record_id,
                {
                    "status": "写入失败",
                    "message": message,
                    "feishu_result": {"error": message},
                },
            )
            return

        self.intake_page.capture_widget.status_label.setText("写入飞书中...")
        self.intake_page.set_submit_in_progress(True)
        task["history_record_id"] = record_id
        self._update_history_snapshot(
            record_id,
            {
                "status": "写入中",
                "message": "",
            },
        )
        self._start_submit_job(task)

    def _sync_shop_selector(self, payload: dict) -> None:
        product_presets = payload.get("product_presets")
        if not product_presets:
            product_presets = payload.get("global_product_library", [])
        self.intake_page.set_product_presets(product_presets)
        shop_names = []
        for shop in payload.get("shops", []):
            if isinstance(shop, dict):
                name = str(shop.get("name", "")).strip()
                if name:
                    shop_names.append(name)
        self.intake_page.set_shop_names(
            shop_names,
            str(payload.get("selected_shop_name", "")).strip() or None,
        )

    def _handle_product_library_request(self, product_name: str, default_cost: str) -> None:
        if self.settings_page.upsert_product_preset(product_name, default_cost):
            payload = self.settings_page.to_payload()
            self._persist_settings_payload(payload)
            self.intake_page.set_product_presets(payload.get("product_presets", []))
            self.intake_page.capture_widget.status_label.setText(f"已加入商品库：{product_name}")

    def _sync_products_from_order(self, order) -> None:
        changed = False
        for item in order.procurement_items:
            if self.settings_page.upsert_product_preset(item.product_name, item.cost):
                changed = True
        if not changed:
            return
        payload = self.settings_page.to_payload()
        self._persist_settings_payload(payload)
        self.intake_page.set_product_presets(payload.get("product_presets", []))

    def _persist_settings_payload(self, payload: dict) -> None:
        if self._config_store is not None:
            self._config_store.save(payload)
        self._sync_shop_selector(payload)
        if self._on_settings_save is not None:
            self._on_settings_save(payload)

    def _extract_order_from_image(self, image_bytes: bytes):
        payload = self.settings_page.to_payload()
        required_keys = {
            "ocr_api_key": "OCR API Key",
            "helper_base_url": "辅助提取 API Base URL",
            "helper_api_key": "辅助提取 API Key",
        }
        if payload.get("ocr_use_mcp"):
            required_keys["ocr_mcp_command"] = "MCP 命令"
            required_keys["ocr_base_url"] = "OCR API Base URL"
        else:
            required_keys["ocr_base_url"] = "OCR API Base URL"
        missing = [label for key, label in required_keys.items() if not payload.get(key)]
        if missing:
            raise ValueError(f"请先在设置页填写：{'、'.join(missing)}")

        pipeline = self._order_pipeline_factory(payload)
        return pipeline.extract_order(image_bytes)

    def _resolve_shop_link(self, wiki_url: str) -> dict[str, str]:
        settings_payload = self.settings_page.to_payload()
        app_id = str(settings_payload.get("feishu_app_id", "")).strip()
        app_secret = str(settings_payload.get("feishu_app_secret", "")).strip()
        if not app_id or not app_secret:
            raise ValueError("请先填写飞书 App ID 和 App Secret")
        client = FeishuClient(app_id, app_secret, "", "")
        return client.resolve_bitable_from_wiki_url(wiki_url)

    def _build_feishu_submission_task(self, payload: dict) -> dict:
        settings_payload = self.settings_page.to_payload()
        shop_name = str(payload.get("shop_name", "")).strip()
        if not shop_name:
            raise ValueError("请先选择店铺")

        missing_global = []
        if not settings_payload.get("feishu_app_id"):
            missing_global.append("飞书 App ID")
        if not settings_payload.get("feishu_app_secret"):
            missing_global.append("飞书 App Secret")
        if missing_global:
            raise ValueError(f"请先在设置页填写：{'、'.join(missing_global)}")

        table_app_token = str(
            settings_payload.get("feishu_table_app_token")
            or (self._find_shop(settings_payload, shop_name) or {}).get("app_token", "")
        ).strip()
        table_id = str(
            settings_payload.get("feishu_table_id")
            or (self._find_shop(settings_payload, shop_name) or {}).get("table_id", "")
        ).strip()
        field_mapping = settings_payload.get("feishu_field_mapping")
        if not field_mapping:
            field_mapping = (self._find_shop(settings_payload, shop_name) or {}).get("field_mapping")

        missing_table = []
        if not table_app_token:
            missing_table.append("总表 App Token")
        if not table_id:
            missing_table.append("总表 Table ID")
        if missing_table:
            raise ValueError(f"请先在设置页填写：{'、'.join(missing_table)}")

        return {
            "payload": payload,
            "shop_name": shop_name,
            "app_id": str(settings_payload["feishu_app_id"]).strip(),
            "app_secret": str(settings_payload["feishu_app_secret"]).strip(),
            "app_token": table_app_token,
            "table_id": table_id,
            "fields": build_feishu_payload(
                payload["order"],
                field_mapping,
                shop_name=shop_name,
                sync_source="确认写入飞书",
                sync_status="已写入飞书",
                sync_message="写入成功",
            ),
        }

    @staticmethod
    def _build_payload_from_history_row(row: dict) -> dict:
        order_snapshot = row.get("order_snapshot") or {}
        procurement_items = []
        for item in order_snapshot.get("procurement_items", []):
            if not isinstance(item, dict):
                continue
            procurement_items.append(
                ProcurementItem(
                    str(item.get("product_name", "")).strip(),
                    str(item.get("quantity", "")).strip() or "1",
                    str(item.get("cost", "")).strip(),
                )
            )
        while len(procurement_items) < 3:
            procurement_items.append(ProcurementItem("", "1", ""))

        return {
            "shop_name": row.get("shop_name", ""),
            "order": ParsedOrder(
                order_id=str(order_snapshot.get("order_id", "")).strip(),
                placed_at=str(order_snapshot.get("placed_at", "")).strip(),
                order_status=str(order_snapshot.get("order_status", "")).strip(),
                product_name=str(order_snapshot.get("product_name", "")).strip(),
                quantity=str(order_snapshot.get("quantity", "")).strip(),
                order_amount=str(order_snapshot.get("order_amount", "")).strip(),
                income_amount=str(order_snapshot.get("income_amount", "")).strip(),
                recipient_name=str(order_snapshot.get("recipient_name", "")).strip(),
                phone_number=str(order_snapshot.get("phone_number", "")).strip(),
                code=str(order_snapshot.get("code", "")).strip(),
                address=str(order_snapshot.get("address", "")).strip(),
                delivery_note=str(order_snapshot.get("delivery_note", "")).strip(),
                procurement_items=tuple(procurement_items[:3]),
            ),
        }

    @staticmethod
    def _find_shop(settings_payload: dict, shop_name: str) -> Optional[dict]:
        for shop in settings_payload.get("shops", []):
            if not isinstance(shop, dict):
                continue
            name = str(shop.get("name", "")).strip()
            if name == shop_name:
                return shop
        return None

    def _start_submit_job(self, task: dict) -> None:
        self._submit_thread = QThread(self)
        self._submit_worker = _SubmitWorker(self._perform_feishu_submission, task)
        self._submit_worker.moveToThread(self._submit_thread)
        self._submit_thread.started.connect(self._submit_worker.run)
        self._submit_worker.finished.connect(self._handle_submit_success)
        self._submit_worker.failed.connect(self._handle_submit_failure)
        self._submit_worker.finished.connect(self._submit_thread.quit)
        self._submit_worker.failed.connect(self._submit_thread.quit)
        self._submit_thread.finished.connect(self._submit_worker.deleteLater)
        self._submit_thread.finished.connect(self._submit_thread.deleteLater)
        self._submit_thread.finished.connect(self._clear_submit_refs)
        self._submit_thread.start()

    @staticmethod
    def _perform_feishu_submission(task: dict) -> dict:
        client = FeishuClient(
            task["app_id"],
            task["app_secret"],
            task["app_token"],
            task["table_id"],
        )
        access_token = client.get_tenant_access_token()
        response = client.create_record(access_token, task["fields"])
        return {
            "payload": task["payload"],
            "shop_name": task["shop_name"],
            "response": response,
            "history_record_id": task.get("history_record_id"),
        }

    def _handle_submit_success(self, result: dict) -> None:
        payload = result["payload"]
        shop_name = result["shop_name"]
        history_record_id = result.get("history_record_id")
        self.intake_page.set_submit_in_progress(False)
        self.intake_page.capture_widget.status_label.setText(f"已写入飞书：{shop_name}")
        if history_record_id is not None:
            self._update_history_snapshot(
                history_record_id,
                {
                    "status": "已写入飞书",
                    "message": "写入成功",
                    "feishu_result": result["response"],
                },
            )
        else:
            snapshot = self._build_history_snapshot(
                payload,
                "确认写入飞书",
                "已写入飞书",
                "写入成功",
                result["response"],
            )
            self._save_history_snapshot(snapshot)

    def _handle_submit_failure(self, failure: dict) -> None:
        message = str(failure.get("message", "")).strip() or "飞书写入失败"
        payload = failure.get("payload")
        history_record_id = failure.get("history_record_id")
        self.intake_page.set_submit_in_progress(False)
        self.intake_page.capture_widget.status_label.setText(message)
        if history_record_id is not None:
            self._update_history_snapshot(
                history_record_id,
                {
                    "status": "写入失败",
                    "message": message,
                    "feishu_result": {"error": message},
                },
            )
        elif payload is not None:
            snapshot = self._build_history_snapshot(
                payload,
                "确认写入飞书",
                "写入失败",
                message,
                {"error": message},
            )
            self._save_history_snapshot(snapshot)

    def _clear_submit_refs(self) -> None:
        self._submit_thread = None
        self._submit_worker = None

    def _shutdown_submit_job(self) -> None:
        thread = self._submit_thread
        if thread is None:
            return
        thread.quit()
        thread.wait(3000)
        self._clear_submit_refs()

    def closeEvent(self, event) -> None:
        self._shutdown_submit_job()
        self.intake_page.shutdown_background_job()
        super().closeEvent(event)

    @staticmethod
    def _build_order_pipeline(payload: dict) -> OrderPipeline:
        if payload.get("ocr_use_mcp"):
            ocr_client = McpOCRClient(
                payload["ocr_mcp_command"],
                payload["ocr_api_key"],
                payload["ocr_base_url"],
            )
        else:
            ocr_client = OCRClient(payload["ocr_base_url"], payload["ocr_api_key"])
        return OrderPipeline(
            ocr_client,
            HelperClient(payload["helper_base_url"], payload["helper_api_key"]),
            None,
        )
