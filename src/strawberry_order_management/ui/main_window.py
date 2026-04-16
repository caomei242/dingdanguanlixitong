from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from typing import Optional

from PySide6.QtCore import QObject, QThread, Signal, Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
    QMainWindow,
)

from strawberry_order_management.history import HistoryStore
from strawberry_order_management.media import crop_sku_image_from_order_screenshot
from strawberry_order_management.models import ParsedOrder, ProcurementItem
from strawberry_order_management.services.feishu_client import FeishuClient
from strawberry_order_management.services.helper_client import HelperClient
from strawberry_order_management.services.mcp_ocr_client import McpOCRClient
from strawberry_order_management.services.ocr_client import OCRClient
from strawberry_order_management.services.pipeline import OrderPipeline, build_feishu_payload
from strawberry_order_management.ui.app_icon import load_app_icon
from strawberry_order_management.ui.pages.expense_page import ExpensePage
from strawberry_order_management.ui.pages.history_page import HistoryPage
from strawberry_order_management.ui.pages.intake_page import IntakePage
from strawberry_order_management.ui.pages.profit_page import ProfitPage
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
    AUTO_UPDATE_LOG_BACKFILLS = (
        {
            "module": "UI重构",
            "title": "全局壳子升级为 Mac 视窗风格",
            "content": "正式系统新增顶栏、红黄绿控制点、浅灰蓝背景和白卡内容外壳，主导航与业务逻辑保持不变。",
            "created_at": "2026-04-14 20:40:00",
        },
        {
            "module": "订单录入",
            "title": "录单页升级为三栏工作台",
            "content": "订单录入改为左侧识别与输入、中间主表单、右侧结果区的三栏布局，保留全部字段、按钮和提交逻辑。",
            "created_at": "2026-04-14 21:05:00",
        },
        {
            "module": "历史",
            "title": "修复历史备注清空与界面整理",
            "content": "历史页隐藏 SKU 文本字段；历史编辑时允许用空备注覆盖飞书备注列；并补齐本轮修复的更新日志记录。",
            "created_at": "2026-04-14 21:30:00",
        },
        {
            "module": "利润计算",
            "title": "利润页升级为双 Tab 驾驶舱",
            "content": "正式利润页重构为大盘和每日账目明细双 Tab，补齐趋势卡、洞察卡和每日行式明细结构，同时保留原有计算逻辑与筛选联动。",
            "created_at": "2026-04-14 21:45:00",
        },
        {
            "module": "设置",
            "title": "设置页升级为左导航工作台",
            "content": "设置页改为顶部固定保存区、左侧分区导航、右侧内容堆栈，店铺映射区压缩为三列布局，保留原有保存、检测和更新日志逻辑。",
            "created_at": "2026-04-14 22:00:00",
        },
        {
            "module": "UI重构",
            "title": "补齐侧栏命名与财务大盘分层",
            "content": "主导航改为历史订单和财务报表；利润大盘拆出月级别与当日级别概览；录单页恢复横向滚动；并排查正式页白卡对象名遗漏问题。",
            "created_at": "2026-04-14 22:10:00",
        },
        {
            "module": "经营开支",
            "title": "新增独立经营开支页与利润联动",
            "content": "新增项目级、店铺级、订单级三层归属的经营开支工作台，支持独立记录、编辑、删除，并自动接入财务报表的大盘与每日明细。",
            "created_at": "2026-04-15 11:10:00",
        },
        {
            "module": "经营开支",
            "title": "历史订单支持一键带入订单级开支",
            "content": "历史订单详情区新增“新增订单开支”入口，点击后可直接跳转到经营开支页，并自动带入关联订单、店铺和平台信息，减少重复录入。",
            "created_at": "2026-04-15 11:40:00",
        },
        {
            "module": "录单",
            "title": "规格模板联动升级为自动沉淀",
            "content": "保存订单或编辑历史时，如果规格和采购信息完整，系统会自动更新对应规格模板；下次遇到近似规格时会更稳地预填采购明细，同时保留手动入库入口。",
            "created_at": "2026-04-16 10:30:00",
        },
    )

    def __init__(
        self,
        on_settings_save=None,
        config_store=None,
        history_store=None,
        expense_store=None,
        order_pipeline_factory=None,
    ) -> None:
        super().__init__()
        self.setWindowTitle("草莓订单管理系统")
        self.setWindowIcon(load_app_icon())
        self._on_settings_save = on_settings_save
        self._config_store = config_store
        self._history_store = history_store
        self._expense_store = expense_store
        self._order_pipeline_factory = order_pipeline_factory or self._build_order_pipeline
        self._submit_thread = None
        self._submit_worker = None

        self.nav = QListWidget()
        self.nav.addItems(["订单录入", "历史订单", "财务报表", "经营开支", "设置"])
        self.nav.setFixedWidth(148)
        self.nav.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.nav.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.nav.setSpacing(4)

        self.stack = QStackedWidget()
        self.intake_page = IntakePage(
            on_process_image=self._extract_order_from_image,
            on_submit=self._handle_submit_request,
            on_save_history=self._handle_save_history_request,
        )
        self.history_page = HistoryPage()
        self.profit_page = ProfitPage()
        self.expense_page = ExpensePage()
        self.settings_page = SettingsPage(
            on_resolve_shop_link=self._resolve_shop_link,
            on_inspect_table_fields=self._inspect_total_table_fields,
        )
        self.stack.addWidget(self.intake_page)
        self.stack.addWidget(self.history_page)
        self.stack.addWidget(self.profit_page)
        self.stack.addWidget(self.expense_page)
        self.stack.addWidget(self.settings_page)
        self.intake_page.product_library_requested.connect(self._handle_product_library_request)
        self.intake_page.procurement_template_requested.connect(self._handle_procurement_template_request)
        self.history_page.save_requested.connect(self._handle_history_save_request)
        self.history_page.delete_requested.connect(self._handle_history_delete_request)
        self.history_page.resubmit_requested.connect(self._handle_history_resubmit_request)
        self.history_page.expense_requested.connect(self._handle_history_expense_request)
        self.expense_page.save_requested.connect(self._handle_expense_save_request)
        self.expense_page.delete_requested.connect(self._handle_expense_delete_request)

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
        sidebar.setObjectName("WindowSidebar")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(18, 18, 18, 18)
        sidebar_layout.setSpacing(16)
        sidebar_layout.addLayout(brand_box)
        sidebar_layout.addWidget(self.nav)
        sidebar_layout.addStretch(1)

        content = QFrame()
        content.setObjectName("WindowContentShell")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.addWidget(self.stack)

        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)
        body_layout.addWidget(sidebar, 0)
        body_layout.addWidget(content, 1)

        shell = QFrame()
        shell.setObjectName("WindowShell")
        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)
        shell_layout.addWidget(body, 1)

        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(0)
        layout.addWidget(shell)
        self.setCentralWidget(root)

        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav.setCurrentRow(0)
        self.settings_page.save_requested.connect(self._handle_settings_save)

        if self._config_store is not None:
            payload = self._config_store.load()
            self.settings_page.load_payload(payload)
            normalized_payload = self.settings_page.to_payload()
            if (
                payload.get("update_logs_initialized") != normalized_payload.get("update_logs_initialized")
                or payload.get("update_logs") != normalized_payload.get("update_logs")
            ):
                self._persist_settings_payload(normalized_payload)
            self._backfill_runtime_update_logs(payload)
        self._sync_shop_selector(self.settings_page.to_payload())
        if self._history_store is not None:
            self._reload_history_page()
        if self._expense_store is not None:
            self._reload_expense_page()

        apply_theme(self)
        self._sync_nav_height()

    def _sync_nav_height(self) -> None:
        self.nav.doItemsLayout()
        fallback_row_height = self.nav.fontMetrics().height() + 28
        row_heights = [
            max(self.nav.sizeHintForRow(index), fallback_row_height)
            for index in range(self.nav.count())
        ]
        content_height = sum(row_heights)
        spacing_height = self.nav.spacing() * max(0, self.nav.count() - 1)
        frame_height = self.nav.frameWidth() * 2
        vertical_padding = 14
        desired_height = content_height + spacing_height + frame_height + vertical_padding
        self.nav.setFixedHeight(max(desired_height, 360))

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
                "platform": order.platform,
                "order_status": order.order_status,
                "product_name": order.product_name,
                "specification": order.specification,
                "sku": order.sku,
                "sku_image_path": order.sku_image_path,
                "quantity": order.quantity,
                "order_amount": order.order_amount,
                "income_amount": order.income_amount,
                "platform_fee_rate": order.platform_fee_rate,
                "platform_fee_amount": order.platform_fee_amount,
                "other_cost": order.other_cost,
                "procurement_total_cost": order.procurement_total_cost,
                "gross_profit": order.gross_profit,
                "custom_cost_labels": list(order.custom_cost_labels),
                "custom_cost_values": list(order.custom_cost_values),
                "recipient_name": order.recipient_name,
                "phone_number": order.phone_number,
                "code": order.code,
                "address": order.address,
                "delivery_note": order.delivery_note,
                "procurement_tracking_number": order.procurement_tracking_number,
                "procurement_items": [
                    {
                        **{
                            "product_name": item.product_name,
                            "quantity": item.quantity,
                            "cost": item.cost,
                        },
                        **(
                            {"tracking_number": item.tracking_number}
                            if str(item.tracking_number).strip()
                            else {}
                        ),
                    }
                    for item in order.procurement_items
                ],
            },
            "address_snapshot": {
                "output_one": self.intake_page.address_widget.output_one.toPlainText().strip(),
                "output_two": self.intake_page.address_widget.output_two.toPlainText().strip(),
            },
        }
        feishu_record_id = self._extract_feishu_record_id(feishu_result)
        if feishu_record_id:
            row["feishu_record_id"] = feishu_record_id
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
        rows = self._history_store.list_items() if self._history_store is not None else []
        self.history_page.load_rows(rows)
        self.expense_page.set_order_rows(rows)
        self.profit_page.load_rows(rows)
        if self._expense_store is not None:
            self.profit_page.load_expense_rows(self._expense_store.list_items())

    def _reload_expense_page(self, selected_record_id: str = "") -> None:
        rows = self._expense_store.list_items() if self._expense_store is not None else []
        self.expense_page.load_rows(rows, selected_record_id=selected_record_id)
        self.profit_page.load_expense_rows(rows)

    def _handle_expense_save_request(self, record_id: str, payload: dict) -> None:
        if self._expense_store is None:
            return
        if record_id:
            try:
                row = self._expense_store.update(record_id, payload)
            except KeyError:
                row = self._expense_store.append(payload)
        else:
            row = self._expense_store.append(payload)
        self.expense_page.set_status("已保存经营开支")
        self._reload_expense_page(row.get("record_id", ""))

    def _handle_expense_delete_request(self, record_id: str) -> None:
        if self._expense_store is None or not record_id:
            return
        confirm = QMessageBox.question(
            self,
            "删除经营开支",
            "确定要删除这条经营开支吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            self._expense_store.delete(record_id)
        except KeyError:
            return
        self.expense_page.clear_editor()
        self.expense_page.set_status("已删除经营开支")
        self._reload_expense_page()

    def _handle_history_save_request(self, record_id: str, patch: dict) -> None:
        if self._history_store is None:
            return
        row = self._update_history_snapshot(record_id, patch)
        if row is None:
            return
        payload = self._build_payload_from_history_row(row)
        payload["blank_source_fields"] = {"备注"}
        self._sync_products_from_order(payload["order"])
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

        task["history_record_id"] = record_id
        task["mode"] = "update_or_create"
        task["feishu_record_id"] = str(row.get("feishu_record_id", "")).strip()
        self.intake_page.capture_widget.status_label.setText("保存并同步飞书中...")
        self.intake_page.set_submit_in_progress(True)
        self._update_history_snapshot(record_id, {"status": "写入中", "message": ""})
        self._start_submit_job(task)

    def _handle_history_delete_request(self, record_id: str) -> None:
        if self._history_store is None:
            return
        try:
            row = self._history_store.get(record_id)
        except KeyError:
            return
        first_confirm = QMessageBox.question(
            self,
            "删除订单",
            "确定要删除这条订单吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if first_confirm != QMessageBox.StandardButton.Yes:
            return

        delete_remote = False
        if str(row.get("feishu_record_id", "")).strip():
            second_confirm = QMessageBox.question(
                self,
                "删除飞书记录",
                "是否同时删除飞书中的对应记录？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            delete_remote = second_confirm == QMessageBox.StandardButton.Yes
            if delete_remote:
                try:
                    self._delete_remote_history_record(row)
                except ValueError as exc:
                    if self._is_missing_record_error(str(exc)):
                        self.intake_page.capture_widget.status_label.setText("飞书记录不存在，已删除本地历史")
                    else:
                        self.intake_page.capture_widget.status_label.setText(str(exc))
                        return
        try:
            self._history_store.delete(record_id)
        except KeyError:
            pass
        else:
            if delete_remote:
                self.intake_page.capture_widget.status_label.setText("已删除本地历史和飞书记录")
            else:
                self.intake_page.capture_widget.status_label.setText("已删除本地历史")
        self._reload_history_page()

    def _handle_history_resubmit_request(self, record_id: str) -> None:
        if self._history_store is None:
            return
        try:
            row = self._history_store.get(record_id)
        except KeyError:
            return

        payload = self._build_payload_from_history_row(row)
        payload["blank_source_fields"] = {"备注"}
        self._sync_products_from_order(payload["order"])
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
        task["mode"] = "update_or_create"
        task["feishu_record_id"] = str(row.get("feishu_record_id", "")).strip()
        self._update_history_snapshot(
            record_id,
            {
                "status": "写入中",
                "message": "",
            },
        )
        self._start_submit_job(task)

    def _handle_history_expense_request(self, record_id: str) -> None:
        if self._history_store is None:
            return
        try:
            row = self._history_store.get(record_id)
        except KeyError:
            return
        self.nav.setCurrentRow(3)
        self.expense_page.prefill_from_history_row(row)

    def _sync_shop_selector(self, payload: dict) -> None:
        product_presets = payload.get("product_presets")
        if not product_presets:
            product_presets = payload.get("global_product_library", [])
        self.intake_page.set_product_presets(product_presets)
        self.history_page.set_product_presets(product_presets)
        self.intake_page.set_procurement_templates(payload.get("procurement_templates", []))
        self.intake_page.set_custom_cost_labels(payload.get("custom_cost_labels") or ["", "", ""])
        shop_names = []
        for shop in payload.get("shops", []):
            if isinstance(shop, dict):
                name = str(shop.get("name", "")).strip()
                if name:
                    shop_names.append(name)
        self.intake_page.set_shop_names(
            shop_names,
            str(payload.get("intake_default_shop_name", "")).strip()
            or str(payload.get("selected_shop_name", "")).strip()
            or None,
        )
        self.profit_page.set_shop_names(shop_names)
        self.expense_page.set_shop_names(shop_names)

    def _handle_product_library_request(self, product_name: str, default_cost: str) -> None:
        if self.settings_page.upsert_product_preset(product_name, default_cost):
            payload = self.settings_page.to_payload()
            self._persist_settings_payload(payload)
            self.intake_page.set_product_presets(payload.get("product_presets", []))
            self.intake_page.capture_widget.status_label.setText(f"已加入商品库：{product_name}")

    def _handle_procurement_template_request(self, template: dict) -> None:
        if self.settings_page.upsert_procurement_template(
            str(template.get("specification", "")).strip(),
            list(template.get("procurement_items") or []),
        ):
            payload = self.settings_page.to_payload()
            self._persist_settings_payload(payload)

    def _sync_products_from_order(self, order) -> None:
        changed = False
        for item in order.procurement_items:
            if self.settings_page.upsert_product_preset(item.product_name, item.cost):
                changed = True
        specification = str(getattr(order, "specification", "")).strip()
        template_items = []
        for item in list(getattr(order, "procurement_items", []) or [])[:3]:
            product_name = str(getattr(item, "product_name", "")).strip()
            quantity = str(getattr(item, "quantity", "")).strip()
            cost = str(getattr(item, "cost", "")).strip()
            if quantity == "1" and not any((product_name, cost)):
                quantity = ""
            elif not quantity and any((product_name, cost)):
                quantity = "1"
            template_items.append(
                {
                    "product_name": product_name,
                    "quantity": quantity,
                    "cost": cost,
                }
            )
        while len(template_items) < 3:
            template_items.append({"product_name": "", "quantity": "", "cost": ""})
        if specification and any(item["product_name"] or item["cost"] for item in template_items):
            if self.settings_page.upsert_procurement_template(specification, template_items):
                changed = True
        if not changed:
            return
        payload = self.settings_page.to_payload()
        self._persist_settings_payload(payload)

    def _persist_settings_payload(self, payload: dict) -> None:
        if self._config_store is not None:
            self._config_store.save(payload)
        self._sync_shop_selector(payload)
        if self._on_settings_save is not None:
            self._on_settings_save(payload)

    def _backfill_runtime_update_logs(self, loaded_payload: dict | None = None) -> None:
        payload = loaded_payload or {}
        if "update_logs_initialized" not in payload and "update_logs" not in payload:
            return
        changed = False
        existing_keys = {
            (
                str(item.get("module", "")).strip(),
                str(item.get("title", "")).strip(),
            )
            for item in self.settings_page.to_payload().get("update_logs", [])
            if isinstance(item, dict)
        }
        for item in self.AUTO_UPDATE_LOG_BACKFILLS:
            key = (item["module"], item["title"])
            if key in existing_keys:
                continue
            if self.settings_page.append_update_log(
                item["module"],
                item["title"],
                item["content"],
                created_at=item["created_at"],
            ):
                changed = True
                existing_keys.add(key)
        if changed:
            self._persist_settings_payload(self.settings_page.to_payload())

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
        order = pipeline.extract_order(image_bytes)
        sku_image_path = crop_sku_image_from_order_screenshot(image_bytes, order_id=order.order_id)
        return replace(order, sku_image_path=sku_image_path)

    def _resolve_shop_link(self, wiki_url: str) -> dict[str, str]:
        settings_payload = self.settings_page.to_payload()
        app_id = str(settings_payload.get("feishu_app_id", "")).strip()
        app_secret = str(settings_payload.get("feishu_app_secret", "")).strip()
        if not app_id or not app_secret:
            raise ValueError("请先填写飞书 App ID 和 App Secret")
        client = FeishuClient(app_id, app_secret, "", "")
        return client.resolve_bitable_from_wiki_url(wiki_url)

    def _inspect_total_table_fields(self, settings_payload: dict) -> set[str]:
        app_id = str(settings_payload.get("feishu_app_id", "")).strip()
        app_secret = str(settings_payload.get("feishu_app_secret", "")).strip()
        table_app_token = str(settings_payload.get("feishu_table_app_token", "")).strip()
        table_id = str(settings_payload.get("feishu_table_id", "")).strip()
        missing = []
        if not app_id:
            missing.append("飞书 App ID")
        if not app_secret:
            missing.append("飞书 App Secret")
        if not table_app_token:
            missing.append("总表 App Token")
        if not table_id:
            missing.append("总表 Table ID")
        if missing:
            raise ValueError(f"请先在设置页填写：{'、'.join(missing)}")
        client = FeishuClient(app_id, app_secret, table_app_token, table_id)
        access_token = client.get_tenant_access_token()
        return client.list_field_names(access_token)

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
            "mode": str(payload.get("mode", "create")).strip() or "create",
            "feishu_record_id": str(payload.get("feishu_record_id", "")).strip(),
            "fields": build_feishu_payload(
                payload["order"],
                field_mapping,
                shop_name=shop_name,
                sync_source="确认写入飞书",
                sync_status="已写入飞书",
                sync_message="写入成功",
                blank_source_fields=set(payload.get("blank_source_fields") or []),
            ),
        }

    @staticmethod
    def _build_payload_from_history_row(row: dict) -> dict:
        order_snapshot = row.get("order_snapshot") or {}
        procurement_items = []
        for item in order_snapshot.get("procurement_items", []):
            if not isinstance(item, dict):
                continue
            product_name = str(item.get("product_name", "")).strip()
            quantity = str(item.get("quantity", "")).strip()
            cost = str(item.get("cost", "")).strip()
            tracking_number = str(item.get("tracking_number", "")).strip()
            procurement_items.append(
                ProcurementItem(
                    product_name,
                    (
                        quantity
                        if quantity != "1" or any((product_name, cost, tracking_number))
                        else ""
                    ) or ("1" if any((product_name, cost, tracking_number)) else ""),
                    cost,
                    tracking_number,
                )
            )
        while len(procurement_items) < 3:
            procurement_items.append(ProcurementItem("", "", "", ""))

        return {
            "shop_name": row.get("shop_name", ""),
            "feishu_record_id": str(row.get("feishu_record_id", "")).strip(),
            "order": ParsedOrder(
                order_id=str(order_snapshot.get("order_id", "")).strip(),
                placed_at=str(order_snapshot.get("placed_at", "")).strip(),
                platform=str(order_snapshot.get("platform", "抖店")).strip() or "抖店",
                order_status=str(order_snapshot.get("order_status", "")).strip(),
                product_name=str(order_snapshot.get("product_name", "")).strip(),
                specification=str(order_snapshot.get("specification", "")).strip(),
                sku=str(order_snapshot.get("sku", "")).strip(),
                sku_image_path=str(order_snapshot.get("sku_image_path", "")).strip(),
                quantity=str(order_snapshot.get("quantity", "")).strip(),
                order_amount=str(order_snapshot.get("order_amount", "")).strip(),
                income_amount=str(order_snapshot.get("income_amount", "")).strip(),
                platform_fee_rate=str(order_snapshot.get("platform_fee_rate", "")).strip() or "0.06",
                platform_fee_amount=str(order_snapshot.get("platform_fee_amount", "")).strip(),
                other_cost=str(order_snapshot.get("other_cost", "")).strip(),
                procurement_total_cost=str(order_snapshot.get("procurement_total_cost", "")).strip(),
                gross_profit=str(order_snapshot.get("gross_profit", "")).strip(),
                custom_cost_labels=tuple(
                    str(item).strip()
                    for item in list(order_snapshot.get("custom_cost_labels") or ["", "", ""])[:3]
                ),
                custom_cost_values=tuple(
                    str(item).strip()
                    for item in list(order_snapshot.get("custom_cost_values") or ["", "", ""])[:3]
                ),
                recipient_name=str(order_snapshot.get("recipient_name", "")).strip(),
                phone_number=str(order_snapshot.get("phone_number", "")).strip(),
                code=str(order_snapshot.get("code", "")).strip(),
                address=str(order_snapshot.get("address", "")).strip(),
                delivery_note=str(order_snapshot.get("delivery_note", "")).strip(),
                procurement_tracking_number=str(
                    order_snapshot.get("procurement_tracking_number", "")
                ).strip(),
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
        sync_message = "写入成功"
        feishu_record_id = str(task.get("feishu_record_id", "")).strip()
        if task.get("mode") == "update_or_create" and feishu_record_id:
            try:
                response = client.update_record(access_token, feishu_record_id, task["fields"])
                sync_message = "已保存并同步飞书"
            except ValueError as exc:
                if not MainWindow._is_missing_record_error(str(exc)):
                    raise
                response = client.create_record(access_token, task["fields"])
                sync_message = "原记录不存在，已自动新建"
        else:
            response = client.create_record(access_token, task["fields"])
        return {
            "payload": task["payload"],
            "shop_name": task["shop_name"],
            "response": response,
            "history_record_id": task.get("history_record_id"),
            "sync_message": sync_message,
            "feishu_record_id": MainWindow._extract_feishu_record_id(response),
        }

    def _handle_submit_success(self, result: dict) -> None:
        payload = result["payload"]
        shop_name = result["shop_name"]
        history_record_id = result.get("history_record_id")
        sync_message = str(result.get("sync_message", "")).strip() or "写入成功"
        self.intake_page.set_submit_in_progress(False)
        self.intake_page.capture_widget.status_label.setText(f"已写入飞书：{shop_name}")
        if history_record_id is not None:
            self._update_history_snapshot(
                history_record_id,
                {
                    "status": "已写入飞书",
                    "message": sync_message,
                    "feishu_result": result["response"],
                    "feishu_record_id": result.get("feishu_record_id", ""),
                },
            )
        else:
            snapshot = self._build_history_snapshot(
                payload,
                "确认写入飞书",
                "已写入飞书",
                sync_message,
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

    def _delete_remote_history_record(self, row: dict) -> None:
        settings_payload = self.settings_page.to_payload()
        client = FeishuClient(
            str(settings_payload["feishu_app_id"]).strip(),
            str(settings_payload["feishu_app_secret"]).strip(),
            str(settings_payload["feishu_table_app_token"]).strip(),
            str(settings_payload["feishu_table_id"]).strip(),
        )
        access_token = client.get_tenant_access_token()
        client.delete_record(access_token, str(row.get("feishu_record_id", "")).strip())

    @staticmethod
    def _extract_feishu_record_id(response: Optional[dict]) -> str:
        if not isinstance(response, dict):
            return ""
        data = response.get("data")
        if not isinstance(data, dict):
            return ""
        record_id = str(data.get("record_id", "")).strip()
        if record_id:
            return record_id
        record = data.get("record")
        if not isinstance(record, dict):
            return ""
        return str(record.get("record_id", "")).strip() or str(record.get("id", "")).strip()

    @staticmethod
    def _is_missing_record_error(message: str) -> bool:
        text = str(message).lower()
        return any(
            token in text
            for token in (
                "record not found",
                "recordidnotfound",
                "记录不存在",
                "该记录不存在",
            )
        )

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
