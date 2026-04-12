from __future__ import annotations

from datetime import datetime

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
from strawberry_order_management.services.helper_client import HelperClient
from strawberry_order_management.services.mcp_ocr_client import McpOCRClient
from strawberry_order_management.services.ocr_client import OCRClient
from strawberry_order_management.services.pipeline import OrderPipeline
from strawberry_order_management.ui.pages.history_page import HistoryPage
from strawberry_order_management.ui.pages.intake_page import IntakePage
from strawberry_order_management.ui.pages.settings_page import SettingsPage
from strawberry_order_management.ui.theme import apply_theme


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

        self.nav = QListWidget()
        self.nav.addItems(["订单录入", "历史", "设置"])
        self.nav.setFixedWidth(180)

        self.stack = QStackedWidget()
        self.intake_page = IntakePage(
            on_process_image=self._extract_order_from_image,
            on_submit=self._handle_submit_request,
            on_save_history=self._handle_save_history_request,
        )
        self.history_page = HistoryPage()
        self.settings_page = SettingsPage()
        self.stack.addWidget(self.intake_page)
        self.stack.addWidget(self.history_page)
        self.stack.addWidget(self.settings_page)

        brand_title = QLabel("草莓")
        brand_title.setObjectName("BrandTitle")
        brand_subtitle = QLabel("订单管理系统")
        brand_subtitle.setObjectName("BrandSubtitle")

        brand_box = QVBoxLayout()
        brand_box.addWidget(brand_title)
        brand_box.addWidget(brand_subtitle)
        brand_box.addStretch(1)

        sidebar = QFrame()
        sidebar.setObjectName("ShellFrame")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.addLayout(brand_box)
        sidebar_layout.addWidget(self.nav)

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
            self.history_page.load_rows(self._history_store.list_items())

        apply_theme(self)

    def _handle_settings_save(self, payload: dict) -> None:
        if self._config_store is not None:
            self._config_store.save(payload)
        self._sync_shop_selector(payload)
        if self._on_settings_save is not None:
            self._on_settings_save(payload)

    def _handle_save_history_request(self, payload: dict) -> None:
        self._append_history(payload, "仅存历史")

    def _handle_submit_request(self, payload: dict) -> None:
        self._append_history(payload, "待写入飞书")

    def _append_history(self, payload: dict, status: str) -> None:
        if self._history_store is None:
            return
        order = payload["order"]
        row = {
            "shop_name": payload.get("shop_name") or "-",
            "order_id": order.order_id,
            "recipient_name": order.recipient_name,
            "status": status,
            "product_name": order.product_name,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        self._history_store.append(row)
        self.history_page.load_rows(self._history_store.list_items())

    def _sync_shop_selector(self, payload: dict) -> None:
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
