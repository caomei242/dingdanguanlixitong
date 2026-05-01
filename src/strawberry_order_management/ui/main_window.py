from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import inspect
import time
from typing import Optional
import urllib.error
import urllib.request

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
from strawberry_order_management.services.auto_order import (
    AUTO_ORDER_TASK_STATUS_FAILED,
    AUTO_ORDER_TASK_STATUS_QUEUED,
    AUTO_ORDER_TASK_STATUS_RUNNING,
    AutoOrderExecutor,
    AutoOrderBridge,
    AutoOrderBridgeError,
    AutoOrderRequest,
    AutoOrderResult,
    AutoOrderTaskTicket,
    LocalHttpAutoOrderBridge,
    SafeFailAutoOrderExecutor,
    apply_auto_order_result,
    build_failed_auto_order_result,
    enabled_jd_accounts,
    normalize_jd_accounts,
    normalize_auto_order_bridge_config,
    normalize_procurement_items,
    now_timestamp,
    ready_jd_accounts,
    row_needs_manual_retry_hint,
    row_auto_order_status,
    row_auto_order_resume_hint,
    row_has_auto_order_scope,
    summarize_auto_order_message,
    summarize_auto_order_status,
    task_snapshot_to_result,
    task_ticket_to_snapshot,
    unresolved_procurement_indices,
)
from strawberry_order_management.services.auto_order_service_manager import AutoOrderServiceManager
from strawberry_order_management.services.feishu_client import FeishuClient
from strawberry_order_management.services.helper_client import HelperClient
from strawberry_order_management.services.mcp_ocr_client import McpOCRClient
from strawberry_order_management.services.mobile_order import MobileOrderHttpServer, MobileOrderService
from strawberry_order_management.services.ocr_client import OCRClient
from strawberry_order_management.services.pipeline import (
    DEFAULT_FEISHU_FIELD_MAPPING,
    OrderPipeline,
    build_feishu_payload,
)
from strawberry_order_management.services.wechat_callback import WechatCallbackService
from strawberry_order_management.ui.app_icon import load_app_icon
from strawberry_order_management.ui.pages.expense_page import ExpensePage
from strawberry_order_management.ui.pages.auto_order_page import AutoOrderPage
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


class _AutoOrderPollWorker(QObject):
    snapshot_ready = Signal(str, object)
    failed = Signal(str, str, str)
    finished = Signal(str)

    def __init__(
        self,
        record_id: str,
        bridge: AutoOrderBridge,
        ticket: AutoOrderTaskTicket,
        interval_ms: int,
        timeout_seconds: int,
    ) -> None:
        super().__init__()
        self._record_id = record_id
        self._bridge = bridge
        self._ticket = ticket
        self._interval_seconds = max(0.001, interval_ms / 1000)
        self._timeout_seconds = max(1, timeout_seconds)
        self._cancelled = False

    def stop(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        deadline = time.monotonic() + self._timeout_seconds
        current_ticket = self._ticket
        while not self._cancelled:
            time.sleep(self._interval_seconds)
            if self._cancelled:
                break
            if time.monotonic() >= deadline:
                self.failed.emit(
                    self._record_id,
                    "自动拍单任务超时，请确认后手动重试",
                    now_timestamp(),
                )
                break
            try:
                snapshot = self._bridge.poll(current_ticket)
            except AutoOrderBridgeError as exc:
                self.failed.emit(self._record_id, str(exc), now_timestamp())
                break
            self.snapshot_ready.emit(self._record_id, snapshot)
            current_ticket = AutoOrderTaskTicket(
                task_id=snapshot.task_id,
                task_status=snapshot.task_status,
                message=snapshot.message,
                submitted_at=snapshot.submitted_at,
                updated_at=snapshot.updated_at,
            )
            if snapshot.task_status not in {AUTO_ORDER_TASK_STATUS_QUEUED, AUTO_ORDER_TASK_STATUS_RUNNING}:
                break
        self.finished.emit(self._record_id)


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
        auto_order_executor: AutoOrderExecutor | None = None,
        auto_order_service_manager: AutoOrderServiceManager | None = None,
        wechat_service_manager: object | None = None,
    ) -> None:
        super().__init__()
        self.setWindowTitle("草莓订单管理系统")
        self.setWindowIcon(load_app_icon())
        self._on_settings_save = on_settings_save
        self._config_store = config_store
        self._history_store = history_store
        self._expense_store = expense_store
        self._order_pipeline_factory = order_pipeline_factory or self._build_order_pipeline
        self._auto_order_executor = auto_order_executor or SafeFailAutoOrderExecutor()
        self._auto_order_service_manager = auto_order_service_manager or AutoOrderServiceManager()
        self._wechat_service_manager = wechat_service_manager
        self._mobile_order_server: MobileOrderHttpServer | None = None
        self._wechat_service_runtime: dict[str, str] | None = None
        self._active_auto_order_tasks: dict[str, dict] = {}
        self._submit_thread = None
        self._submit_worker = None

        self.nav = QListWidget()
        self.nav.addItems(["订单录入", "历史订单", "自动拍单", "财务报表", "经营开支", "设置"])
        self.nav.setFixedWidth(152)
        self.nav.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.nav.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.nav.setSpacing(4)

        self.stack = QStackedWidget()
        self.intake_page = IntakePage(
            on_process_image=self._extract_order_from_image,
            on_submit=self._handle_submit_request,
            on_submit_and_auto_order=self._handle_submit_and_auto_order_request,
            on_save_history=self._handle_save_history_request,
        )
        self.history_page = HistoryPage()
        self.auto_order_page = AutoOrderPage()
        self.profit_page = ProfitPage()
        self.expense_page = ExpensePage()
        self.settings_page = SettingsPage(
            on_resolve_shop_link=self._resolve_shop_link,
            on_inspect_table_fields=self._inspect_total_table_fields,
        )
        self.stack.addWidget(self.intake_page)
        self.stack.addWidget(self.history_page)
        self.stack.addWidget(self.auto_order_page)
        self.stack.addWidget(self.profit_page)
        self.stack.addWidget(self.expense_page)
        self.stack.addWidget(self.settings_page)
        self.intake_page.product_library_requested.connect(self._handle_product_library_request)
        self._configure_window_behavior()

    def _configure_window_behavior(self) -> None:
        self.setWindowFlag(Qt.WindowType.Window, True)
        self.setWindowFlag(Qt.WindowType.CustomizeWindowHint, False)
        self.setWindowFlag(Qt.WindowType.WindowTitleHint, True)
        self.setWindowFlag(Qt.WindowType.WindowSystemMenuHint, True)
        self.setWindowFlag(Qt.WindowType.WindowMinimizeButtonHint, True)
        self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, True)
        self.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, True)
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.intake_page.procurement_template_requested.connect(self._handle_procurement_template_request)
        self.history_page.save_requested.connect(self._handle_history_save_request)
        self.history_page.delete_requested.connect(self._handle_history_delete_request)
        self.history_page.resubmit_requested.connect(self._handle_history_resubmit_request)
        self.history_page.expense_requested.connect(self._handle_history_expense_request)
        self.history_page.auto_order_requested.connect(self._handle_history_auto_order_request)
        self.history_page.auto_order_view_requested.connect(self._handle_history_auto_order_view_request)
        self.auto_order_page.auto_order_requested.connect(self._handle_auto_order_page_request)
        self.auto_order_page.history_view_requested.connect(self._handle_auto_order_history_view_request)
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

        brand_divider = QFrame()
        brand_divider.setObjectName("BrandDivider")

        sidebar = QFrame()
        sidebar.setObjectName("WindowSidebar")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(18, 18, 18, 18)
        sidebar_layout.setSpacing(16)
        sidebar_layout.addLayout(brand_box)
        sidebar_layout.addWidget(brand_divider)
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
        self.settings_page.auto_order_check_requested.connect(self._handle_auto_order_check_requested)
        self.settings_page.auto_order_service_restart_requested.connect(
            self._handle_auto_order_service_restart_requested
        )
        self.settings_page.mobile_order_service_start_requested.connect(
            self._handle_mobile_order_service_start_requested
        )
        self.settings_page.mobile_order_service_stop_requested.connect(
            self._handle_mobile_order_service_stop_requested
        )
        self.settings_page.mobile_order_service_test_requested.connect(
            self._handle_mobile_order_service_test_requested
        )
        self._bind_optional_wechat_service_controls()

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
        self._refresh_auto_order_service_status()
        self._refresh_mobile_order_service_status()
        self._refresh_wechat_service_status()
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
        if not normalize_auto_order_bridge_config(payload)["enabled"]:
            self._auto_order_service_manager.shutdown()
        self._refresh_auto_order_service_status(payload)
        if not self._mobile_order_config(payload)["enabled"]:
            self._stop_mobile_order_server()
        self._refresh_mobile_order_service_status(payload)
        if not self._wechat_service_config(payload)["enabled"]:
            self._stop_wechat_service()
        self._refresh_wechat_service_status(payload)

    def _handle_mobile_order_service_start_requested(self, payload: dict) -> None:
        config = self._mobile_order_config(payload)
        if not config["enabled"]:
            self.settings_page.set_mobile_order_service_status("手机助手入口未启用")
            return
        if not config["api_key"]:
            self.settings_page.set_mobile_order_service_status("请先填写手机助手入口 API Key")
            return
        if self._history_store is None:
            self.settings_page.set_mobile_order_service_status("当前环境没有历史存储，无法创建手机草稿")
            return
        self._stop_mobile_order_server()
        settings_payload = self.settings_page.to_payload()
        default_shop = (
            str(settings_payload.get("intake_default_shop_name", "")).strip()
            or str(settings_payload.get("selected_shop_name", "")).strip()
            or "乐宝零食店"
        )
        default_platform = str((self._find_shop(settings_payload, default_shop) or {}).get("platform", "")).strip()
        service = MobileOrderService(
            self._history_store,
            default_shop_name=default_shop,
            default_platform=default_platform,
            procurement_templates=list(settings_payload.get("procurement_templates") or []),
            order_pipeline=self._build_mobile_order_pipeline_if_ready(settings_payload),
        )
        wechat_callback_service = None
        wechat_config = self._wechat_service_config(settings_payload)
        if wechat_config["enabled"] and wechat_config["mode"] == "shared_mobile" and wechat_config["token"]:
            wechat_callback_service = WechatCallbackService(
                token=wechat_config["token"],
                mobile_order_service=service,
                callback_path=wechat_config["callback_path"],
            )
        try:
            self._mobile_order_server = MobileOrderHttpServer(
                service,
                api_key=config["api_key"],
                host=config["host"],
                port=config["port"],
                wechat_callback_service=wechat_callback_service,
            )
            self._mobile_order_server.start()
        except OSError as exc:
            self._mobile_order_server = None
            self.settings_page.set_mobile_order_service_status(f"启动失败：{exc}")
            return
        self.settings_page.set_mobile_order_service_status(
            f"运行中：{self._mobile_order_server.base_url}"
        )
        self.settings_page.set_mobile_order_entry_url(f"{self._mobile_order_server.base_url}/mobile")
        if wechat_callback_service is not None:
            self._wechat_service_runtime = {
                "base_url": self._mobile_order_server.base_url,
                "callback_url": self._build_wechat_service_callback_url(wechat_config),
                "status_text": "运行中：公众号回调已复用手机助手入口",
            }
        else:
            self._wechat_service_runtime = None
        self._refresh_wechat_service_status(settings_payload)

    def _handle_mobile_order_service_stop_requested(self, payload: dict) -> None:
        self._stop_mobile_order_server()
        self._refresh_mobile_order_service_status(payload)
        self._refresh_wechat_service_status(payload)

    def _handle_mobile_order_service_test_requested(self, payload: dict) -> None:
        config = self._mobile_order_config(payload)
        if not config["api_key"]:
            self.settings_page.set_mobile_order_service_status("请先填写手机助手入口 API Key")
            return
        base_url = self._mobile_order_server.base_url if self._mobile_order_server is not None else (
            f"http://{config['host']}:{config['port']}"
        )
        url = f"{base_url.rstrip('/')}/mobile/orders/preview"
        body = '{"text":"测试"}'.encode("utf-8")
        request = urllib.request.Request(
            url,
            data=body,
            headers={
                "Authorization": f"Bearer {config['api_key']}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=0.5):
                pass
        except urllib.error.HTTPError as exc:
            self.settings_page.set_mobile_order_service_status(f"连接失败：HTTP {exc.code}")
            return
        except OSError as exc:
            self.settings_page.set_mobile_order_service_status(f"连接失败：{exc}")
            return
        self.settings_page.set_mobile_order_service_status(f"连接成功：{url.rsplit('/', 2)[0]}")

    def _refresh_mobile_order_service_status(self, settings_payload: dict | None = None) -> None:
        payload = settings_payload or self.settings_page.to_payload()
        config = self._mobile_order_config(payload)
        if not config["enabled"]:
            self.settings_page.set_mobile_order_service_status("手机助手入口未启用")
            return
        if self._mobile_order_server is not None:
            self.settings_page.set_mobile_order_service_status(
                f"运行中：{self._mobile_order_server.base_url}"
            )
            self.settings_page.set_mobile_order_entry_url(f"{self._mobile_order_server.base_url}/mobile")
            return
        self.settings_page.set_mobile_order_service_status(
            f"未启动：可访问地址 http://{config['host']}:{config['port']}"
        )

    def _stop_mobile_order_server(self) -> None:
        if self._mobile_order_server is None:
            return
        self._mobile_order_server.stop()
        self._mobile_order_server = None

    def _bind_optional_wechat_service_controls(self) -> None:
        bindings = (
            (
                (
                    "wechat_service_start_requested",
                    "wechat_official_account_service_start_requested",
                    "official_account_service_start_requested",
                    "wechat_mp_service_start_requested",
                ),
                self._handle_wechat_service_start_requested,
            ),
            (
                (
                    "wechat_service_stop_requested",
                    "wechat_official_account_service_stop_requested",
                    "official_account_service_stop_requested",
                    "wechat_mp_service_stop_requested",
                ),
                self._handle_wechat_service_stop_requested,
            ),
            (
                (
                    "wechat_service_test_requested",
                    "wechat_official_account_service_test_requested",
                    "official_account_service_test_requested",
                    "wechat_mp_service_test_requested",
                ),
                self._handle_wechat_service_test_requested,
            ),
        )
        for signal_names, handler in bindings:
            signal = self._first_available_attr(self.settings_page, signal_names)
            if signal is not None and hasattr(signal, "connect"):
                signal.connect(handler)

    def _handle_wechat_service_start_requested(self, payload: dict) -> None:
        config = self._wechat_service_config(payload)
        self._apply_wechat_service_callback_url(self._build_wechat_service_callback_url(config))
        if not config["enabled"]:
            self._apply_wechat_service_status("微信公众号服务未启用")
            return
        if not config["api_key"]:
            self._apply_wechat_service_status("请先填写微信公众号服务 API Key")
            return
        starter = getattr(self._wechat_service_manager, "start", None)
        if not callable(starter):
            self._apply_wechat_service_status("待接入：请补充微信公众号服务管理器")
            return
        self._stop_wechat_service()
        try:
            self._wechat_service_runtime = self._normalize_wechat_service_runtime(starter(config), config)
        except OSError as exc:
            self._wechat_service_runtime = None
            self._apply_wechat_service_status(f"启动失败：{exc}")
            return
        except Exception as exc:
            self._wechat_service_runtime = None
            self._apply_wechat_service_status(f"启动失败：{exc}")
            return
        self._refresh_wechat_service_status(payload)

    def _handle_wechat_service_stop_requested(self, payload: dict) -> None:
        self._stop_wechat_service()
        self._refresh_wechat_service_status(payload)

    def _handle_wechat_service_test_requested(self, payload: dict) -> None:
        config = self._wechat_service_config(payload)
        self._apply_wechat_service_callback_url(self._build_wechat_service_callback_url(config))
        if not config["api_key"]:
            self._apply_wechat_service_status("请先填写微信公众号服务 API Key")
            return
        tester = getattr(self._wechat_service_manager, "test_connection", None)
        if not callable(tester):
            self._apply_wechat_service_status("待接入：暂无可测试的微信公众号服务")
            return
        try:
            result = tester(config)
        except urllib.error.HTTPError as exc:
            self._apply_wechat_service_status(f"连接失败：HTTP {exc.code}")
            return
        except OSError as exc:
            self._apply_wechat_service_status(f"连接失败：{exc}")
            return
        except Exception as exc:
            self._apply_wechat_service_status(f"连接失败：{exc}")
            return
        normalized = self._normalize_wechat_service_test_result(result, config)
        self._apply_wechat_service_callback_url(normalized["callback_url"])
        self._apply_wechat_service_status(normalized["status_text"])

    def _refresh_wechat_service_status(self, settings_payload: dict | None = None) -> None:
        payload = settings_payload or self.settings_page.to_payload()
        config = self._wechat_service_config(payload)
        self._apply_wechat_service_callback_url(self._build_wechat_service_callback_url(config))
        if not config["enabled"]:
            self._apply_wechat_service_status("微信公众号服务未启用")
            return
        if config["mode"] == "manager":
            if self._wechat_service_runtime is not None:
                self._apply_wechat_service_status(self._wechat_service_runtime["status_text"])
                self._apply_wechat_service_callback_url(self._wechat_service_runtime["callback_url"])
                return
            self._apply_wechat_service_status(
                f"未启动：回调地址 {self._build_wechat_service_callback_url(config)}"
            )
            return
        if not config["token"]:
            self._apply_wechat_service_status("请先填写微信公众号 Token")
            return
        if not config["public_url"]:
            self._apply_wechat_service_status("请先填写 Cloudflare Tunnel 公网地址")
            return
        mobile_config = self._mobile_order_config(payload)
        if not mobile_config["enabled"]:
            self._apply_wechat_service_status("请先启用手机助手入口，公众号回调和手机网页共用同一入口")
            return
        if self._wechat_service_runtime is not None:
            self._apply_wechat_service_status(self._wechat_service_runtime["status_text"])
            self._apply_wechat_service_callback_url(self._wechat_service_runtime["callback_url"])
            return
        self._apply_wechat_service_status("未启动：请先启动手机助手入口，再让 Tunnel 指到这个端口")

    def _stop_wechat_service(self) -> None:
        stopper = getattr(self._wechat_service_manager, "stop", None)
        if callable(stopper) and self._wechat_service_runtime is not None:
            stopper()
        self._wechat_service_runtime = None

    @staticmethod
    def _mobile_order_config(payload: dict) -> dict:
        host = str(payload.get("mobile_order_entry_host", "")).strip() or "127.0.0.1"
        try:
            port = int(str(payload.get("mobile_order_entry_port", "")).strip() or "9020")
        except ValueError:
            port = 9020
        return {
            "enabled": bool(payload.get("mobile_order_entry_enabled")),
            "host": host,
            "port": max(0, min(65535, port)),
            "api_key": str(payload.get("mobile_order_entry_api_key", "")).strip(),
        }

    @classmethod
    def _wechat_service_config(cls, payload: dict) -> dict:
        callback_path = cls._payload_text(
            payload,
            (
                "wechat_mp_callback_path",
                "wechat_service_callback_path",
                "wechat_official_account_service_callback_path",
                "official_account_service_callback_path",
                "wechat_mp_service_callback_path",
            ),
            "/wechat/callback",
        )
        if not callback_path.startswith("/"):
            callback_path = f"/{callback_path}"
        public_url = cls._payload_text(
            payload,
            (
                "wechat_mp_tunnel_public_url",
                "wechat_service_public_url",
                "wechat_service_tunnel_public_url",
            ),
        ).rstrip("/")
        host = cls._payload_text(
            payload,
            (
                "wechat_service_host",
                "wechat_official_account_service_host",
                "official_account_service_host",
                "wechat_mp_service_host",
            ),
            "127.0.0.1",
        )
        port = cls._payload_int(
            payload,
            (
                "wechat_service_port",
                "wechat_official_account_service_port",
                "official_account_service_port",
                "wechat_mp_service_port",
            ),
            9030,
        )
        api_key = cls._payload_text(
            payload,
            (
                "wechat_service_api_key",
                "wechat_official_account_service_api_key",
                "official_account_service_api_key",
                "wechat_mp_service_api_key",
            ),
        )
        token = cls._payload_text(
            payload,
            (
                "wechat_mp_token",
                "wechat_service_token",
            ),
        )
        mode = "shared_mobile" if (
            bool(payload.get("wechat_mp_enabled"))
            or any(
                cls._payload_text(payload, (key,))
                for key in (
                    "wechat_mp_token",
                    "wechat_mp_tunnel_public_url",
                    "wechat_mp_app_id",
                    "wechat_mp_app_secret",
                )
            )
        ) else "manager"
        return {
            "enabled": cls._payload_bool(
                payload,
                (
                    "wechat_mp_enabled",
                    "wechat_service_enabled",
                    "wechat_official_account_service_enabled",
                    "official_account_service_enabled",
                    "wechat_mp_service_enabled",
                ),
            ),
            "mode": mode,
            "host": host,
            "port": max(0, min(65535, port)),
            "api_key": api_key,
            "token": token,
            "public_url": public_url,
            "callback_path": callback_path,
        }

    @staticmethod
    def _first_available_attr(target: object, names: tuple[str, ...]):
        for name in names:
            value = getattr(target, name, None)
            if value is not None:
                return value
        return None

    @staticmethod
    def _payload_bool(payload: dict, keys: tuple[str, ...]) -> bool:
        seen_key = False
        for key in keys:
            if key in payload:
                seen_key = True
                if bool(payload.get(key)):
                    return True
        return False if seen_key else False

    @staticmethod
    def _payload_text(payload: dict, keys: tuple[str, ...], fallback: str = "") -> str:
        for key in keys:
            value = payload.get(key)
            if value is None:
                continue
            cleaned = str(value).strip()
            if cleaned:
                return cleaned
        return fallback

    @staticmethod
    def _payload_int(payload: dict, keys: tuple[str, ...], fallback: int) -> int:
        for key in keys:
            value = payload.get(key)
            if value is None or str(value).strip() == "":
                continue
            try:
                return int(str(value).strip())
            except ValueError:
                continue
        return fallback

    @staticmethod
    def _build_wechat_service_base_url(config: dict) -> str:
        public_url = str(config.get("public_url", "")).strip()
        if public_url:
            return public_url
        return f"http://{config['host']}:{config['port']}"

    @classmethod
    def _build_wechat_service_callback_url(cls, config: dict) -> str:
        base_url = cls._build_wechat_service_base_url(config)
        if not base_url:
            return "待填写 Cloudflare Tunnel 公网地址后生成"
        return f"{base_url}{config['callback_path']}"

    def _apply_wechat_service_status(self, message: str) -> None:
        setter = self._first_available_attr(
            self.settings_page,
            (
                "set_wechat_service_status",
                "set_wechat_official_account_service_status",
                "set_official_account_service_status",
                "set_wechat_mp_service_status",
            ),
        )
        if callable(setter):
            setter(message)

    def _apply_wechat_service_callback_url(self, url: str) -> None:
        setter = self._first_available_attr(
            self.settings_page,
            (
                "set_wechat_service_callback_url",
                "set_wechat_official_account_service_callback_url",
                "set_official_account_service_callback_url",
                "set_wechat_callback_url",
                "set_wechat_mp_service_callback_url",
            ),
        )
        if callable(setter):
            setter(url)

    @classmethod
    def _coerce_wechat_service_result(cls, result: object, config: dict) -> dict[str, object]:
        if isinstance(result, dict):
            data: dict[str, object] = dict(result)
        elif isinstance(result, bool):
            data = {"ok": result}
        else:
            data = {
                "ok": getattr(result, "ok", None),
                "base_url": getattr(result, "base_url", ""),
                "callback_url": getattr(result, "callback_url", ""),
                "callback_path": getattr(result, "callback_path", ""),
                "status_text": getattr(result, "status_text", ""),
                "message": getattr(result, "message", ""),
                "http_status": getattr(result, "http_status", None),
            }
        base_url = str(data.get("base_url", "")).strip() or cls._build_wechat_service_base_url(config)
        callback_path = str(data.get("callback_path", "")).strip() or config["callback_path"]
        if not callback_path.startswith("/"):
            callback_path = f"/{callback_path}"
        callback_url = str(data.get("callback_url", "")).strip() or f"{base_url}{callback_path}"
        data["base_url"] = base_url
        data["callback_url"] = callback_url
        return data

    @classmethod
    def _normalize_wechat_service_runtime(cls, result: object, config: dict) -> dict[str, str]:
        data = cls._coerce_wechat_service_result(result, config)
        status_text = str(data.get("status_text", "")).strip() or f"运行中：{data['base_url']}"
        return {
            "base_url": str(data["base_url"]),
            "callback_url": str(data["callback_url"]),
            "status_text": status_text,
        }

    @classmethod
    def _normalize_wechat_service_test_result(cls, result: object, config: dict) -> dict[str, str]:
        data = cls._coerce_wechat_service_result(result, config)
        ok_value = data.get("ok")
        ok = bool(ok_value) if ok_value is not None else str(data.get("status", "")).strip().lower() in {
            "ok",
            "success",
            "healthy",
            "running",
        }
        status_text = str(data.get("status_text", "")).strip()
        if not status_text:
            if ok:
                status_text = f"连接成功：{data['base_url']}"
            else:
                http_status = data.get("http_status")
                message = str(data.get("message", "")).strip()
                if http_status not in (None, ""):
                    status_text = f"连接失败：HTTP {http_status}"
                elif message:
                    status_text = f"连接失败：{message}"
                else:
                    status_text = f"连接失败：{data['base_url']}"
        return {
            "callback_url": str(data["callback_url"]),
            "status_text": status_text,
        }

    def _build_mobile_order_pipeline_if_ready(self, payload: dict) -> OrderPipeline | None:
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
        if any(not payload.get(key) for key in required_keys):
            return None
        return self._order_pipeline_factory(payload)

    def _handle_auto_order_service_restart_requested(self, payload: dict) -> None:
        bridge_config = normalize_auto_order_bridge_config(payload)
        missing = []
        if not bridge_config["enabled"]:
            self.settings_page.set_auto_order_service_status("桥接未启用")
            return
        if not bridge_config["base_url"]:
            missing.append("Base URL")
        if not bridge_config["api_key"]:
            missing.append("API Key")
        if missing:
            self.settings_page.set_auto_order_service_status(
                f"请先填写自动拍单服务{'、'.join(missing)}"
            )
            return
        self._auto_order_service_manager.restart_service(bridge_config)
        self._refresh_auto_order_service_status(payload)

    def _refresh_auto_order_service_status(self, settings_payload: dict | None = None) -> None:
        payload = settings_payload or self.settings_page.to_payload()
        bridge_config = normalize_auto_order_bridge_config(payload)
        self.settings_page.set_auto_order_service_status(
            self._auto_order_service_manager.status_text(bridge_config)
        )

    def _ensure_auto_order_service(self, settings_payload: dict) -> bool:
        bridge_config = normalize_auto_order_bridge_config(settings_payload)
        if not bridge_config["enabled"]:
            self._refresh_auto_order_service_status(settings_payload)
            return False
        started = self._auto_order_service_manager.ensure_service(bridge_config)
        self._refresh_auto_order_service_status(settings_payload)
        return started

    def _should_restart_auto_order_service_after_failure(
        self,
        settings_payload: dict,
        message: str,
    ) -> bool:
        bridge_config = normalize_auto_order_bridge_config(settings_payload)
        if not bridge_config["enabled"]:
            return False
        should_restart = self._auto_order_service_manager.should_restart_after_failure(
            bridge_config,
            message,
        )
        if not should_restart:
            self._refresh_auto_order_service_status(settings_payload)
            return False
        restarted = self._auto_order_service_manager.restart_service(bridge_config)
        self._refresh_auto_order_service_status(settings_payload)
        return restarted

    def _handle_auto_order_check_requested(self, payload: dict) -> None:
        bridge_config = normalize_auto_order_bridge_config(payload)
        missing_fields: list[str] = []
        if not bridge_config["enabled"]:
            self.settings_page.set_auto_order_check_result("失败：请先启用本地 HTTP 自动拍单桥接")
            return
        if not bridge_config["base_url"]:
            missing_fields.append("Base URL")
        if not bridge_config["api_key"]:
            missing_fields.append("API Key")
        if missing_fields:
            self.settings_page.set_auto_order_check_result(f"失败：请先填写自动拍单服务{'、'.join(missing_fields)}")
            return
        verified_accounts = ready_jd_accounts(payload.get("jd_accounts"))
        if not verified_accounts:
            self.settings_page.set_auto_order_check_result(
                "失败：请先勾选至少一个京东账号的地址槽已验证，再做真实拍单自检"
            )
            return
        if not self._ensure_auto_order_service(payload):
            self.settings_page.set_auto_order_check_result(
                f"失败：{self._auto_order_service_manager.status_text(bridge_config)}"
            )
            return
        try:
            result = LocalHttpAutoOrderBridge(bridge_config).check(verified_accounts)
        except AutoOrderBridgeError as exc:
            self.settings_page.set_auto_order_check_result(f"失败：{exc}")
            return
        self.settings_page.set_auto_order_check_result(self._format_auto_order_check_result(result))

    def _handle_save_history_request(self, payload: dict) -> None:
        self._sync_products_from_order(payload["order"])
        snapshot = self._build_history_snapshot(payload, "仅存历史", "仅存历史")
        self._save_history_snapshot(snapshot)
        self.intake_page.capture_widget.status_label.setText("已保存到历史")

    def _handle_submit_request(self, payload: dict) -> None:
        self._submit_to_feishu(payload, auto_order_after_submit=False)

    def _handle_submit_and_auto_order_request(self, payload: dict) -> None:
        self._submit_to_feishu(payload, auto_order_after_submit=True)

    def _submit_to_feishu(self, payload: dict, *, auto_order_after_submit: bool) -> None:
        payload, validation_message = self._prepare_payload_for_feishu(payload)
        if validation_message:
            self.intake_page.capture_widget.status_label.setText(validation_message)
            return
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
        task["auto_order_after_submit"] = auto_order_after_submit
        task["auto_order_source"] = "intake"
        self._start_submit_job(task)

    def _prepare_payload_for_feishu(self, payload: dict) -> tuple[dict, str]:
        order = payload.get("order")
        if not isinstance(order, ParsedOrder):
            return payload, ""
        normalized_placed_at = self._normalize_submit_placed_at(order.placed_at)
        if not normalized_placed_at:
            return payload, "请先补齐下单时间，格式：YYYY-MM-DD HH:MM 或 YYYY-MM-DD HH:MM:SS"
        if normalized_placed_at == order.placed_at:
            return payload, ""
        normalized_payload = dict(payload)
        normalized_payload["order"] = replace(order, placed_at=normalized_placed_at)
        return normalized_payload, ""

    @staticmethod
    def _normalize_submit_placed_at(value: object) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        for fmt in (
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y/%m/%d %H:%M:%S",
            "%Y/%m/%d %H:%M",
        ):
            try:
                parsed = datetime.strptime(text, fmt)
            except ValueError:
                continue
            return parsed.strftime("%Y-%m-%d %H:%M:%S")
        return ""

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
            "auto_order_status": "",
            "auto_order_message": "",
            "auto_order_last_run_at": "",
            "auto_order_task_id": "",
            "auto_order_task_status": "",
            "auto_order_task_submitted_at": "",
            "auto_order_task_last_polled_at": "",
            "auto_order_debug": self._build_auto_order_debug_payload(),
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
                "procurement_items": normalize_procurement_items(
                    [
                        {
                            "product_name": item.product_name,
                            "quantity": item.quantity,
                            "cost": item.cost,
                            "tracking_number": item.tracking_number,
                            "jd_link": getattr(item, "jd_link", ""),
                        }
                        for item in order.procurement_items
                    ]
                ),
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
        active_task_ids = {
            str(task_state.get("task_id", "")).strip()
            for task_state in self._active_auto_order_tasks.values()
            if str(task_state.get("task_id", "")).strip()
        }
        rows = self._sync_stale_auto_order_rows(rows, active_task_ids)
        rows = [
            {
                **row,
                "auto_order_resume_hint": row_auto_order_resume_hint(row, active_task_ids),
            }
            for row in rows
        ]
        self.history_page.load_rows(rows)
        self.auto_order_page.load_rows(rows)
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
        payload, validation_message = self._prepare_payload_for_feishu(payload)
        if validation_message:
            self.intake_page.capture_widget.status_label.setText(validation_message)
            return
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
        payload, validation_message = self._prepare_payload_for_feishu(payload)
        if validation_message:
            self.intake_page.capture_widget.status_label.setText(validation_message)
            return
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
        self.nav.setCurrentRow(4)
        self.expense_page.prefill_from_history_row(row)

    def _handle_history_auto_order_request(self, record_id: str, procurement_indices: object) -> None:
        self._request_auto_order_for_record(
            record_id,
            source="history",
            procurement_indices=tuple(procurement_indices or ()),
        )

    def _handle_history_auto_order_view_request(self, record_id: str) -> None:
        self.nav.setCurrentRow(2)
        self.auto_order_page.focus_record(record_id)

    def _handle_auto_order_page_request(self, record_id: str, procurement_indices: object) -> None:
        self._request_auto_order_for_record(
            record_id,
            source="auto_order",
            procurement_indices=tuple(procurement_indices or ()),
        )

    def _handle_auto_order_history_view_request(self, record_id: str) -> None:
        self.nav.setCurrentRow(1)
        self.history_page.select_record(record_id)

    def _sync_shop_selector(self, payload: dict) -> None:
        product_presets = payload.get("product_presets")
        if not product_presets:
            product_presets = payload.get("global_product_library", [])
        self.intake_page.set_product_presets(product_presets)
        self.history_page.set_product_presets(product_presets)
        self.intake_page.set_procurement_templates(payload.get("procurement_templates", []))
        self.intake_page.set_custom_cost_labels(payload.get("custom_cost_labels") or ["", "", ""])
        shop_names = []
        shop_platforms: dict[str, str] = {}
        for shop in payload.get("shops", []):
            if isinstance(shop, dict):
                name = str(shop.get("name", "")).strip()
                if name:
                    shop_names.append(name)
                    shop_platforms[name] = self._infer_shop_platform(name, shop.get("platform", ""))
        self.intake_page.set_shop_platforms(shop_platforms)
        intake_default_platform = self._resolve_intake_default_platform(payload, shop_platforms)
        platform_default_shops = {
            "抖店": self._resolve_platform_default_shop(payload, shop_platforms, "抖店"),
            "微信小店": self._resolve_platform_default_shop(payload, shop_platforms, "微信小店"),
        }
        self.intake_page.set_platform_default_shops(platform_default_shops)
        initial_shop_name = (
            platform_default_shops.get(intake_default_platform)
            or str(payload.get("intake_default_shop_name", "")).strip()
            or str(payload.get("selected_shop_name", "")).strip()
            or None
        )
        self.intake_page.set_shop_names(
            shop_names,
            initial_shop_name,
        )
        self.history_page.set_shop_names(shop_names)
        self.history_page.set_shop_platforms(shop_platforms)
        self.profit_page.set_shop_names(shop_names)
        self.expense_page.set_shop_names(shop_names)

    @staticmethod
    def _infer_shop_platform(shop_name: str, platform: object = "") -> str:
        cleaned_platform = str(platform or "").strip()
        if cleaned_platform in ("抖店", "微信小店"):
            return cleaned_platform
        if "微信" in str(shop_name or "").strip():
            return "微信小店"
        return "抖店"

    @classmethod
    def _resolve_intake_default_platform(cls, payload: dict, shop_platforms: dict[str, str]) -> str:
        configured_platform = str(payload.get("intake_default_platform", "")).strip()
        if configured_platform in ("抖店", "微信小店"):
            return configured_platform
        legacy_default_shop_name = (
            str(payload.get("intake_default_shop_name", "")).strip()
            or str(payload.get("selected_shop_name", "")).strip()
        )
        if legacy_default_shop_name:
            return shop_platforms.get(legacy_default_shop_name) or cls._infer_shop_platform(legacy_default_shop_name)
        return "抖店"

    @classmethod
    def _resolve_platform_default_shop(
        cls,
        payload: dict,
        shop_platforms: dict[str, str],
        platform: str,
    ) -> str:
        platform_key = "intake_default_shop_name_wechat" if platform == "微信小店" else "intake_default_shop_name_douyin"
        candidate_shops = [shop_name for shop_name, shop_platform in shop_platforms.items() if shop_platform == platform]
        if not candidate_shops:
            return ""
        configured_shop_name = str(payload.get(platform_key, "")).strip()
        if configured_shop_name and configured_shop_name in candidate_shops:
            return configured_shop_name
        legacy_default_shop_name = str(payload.get("intake_default_shop_name", "")).strip()
        if legacy_default_shop_name and shop_platforms.get(legacy_default_shop_name) == platform:
            return legacy_default_shop_name
        selected_shop_name = str(payload.get("selected_shop_name", "")).strip()
        if selected_shop_name and shop_platforms.get(selected_shop_name) == platform:
            return selected_shop_name
        selected_base_name = cls._shop_base_name(selected_shop_name)
        if selected_base_name:
            for candidate_shop_name in candidate_shops:
                if cls._shop_base_name(candidate_shop_name) == selected_base_name:
                    return candidate_shop_name
        return candidate_shops[0]

    @staticmethod
    def _shop_base_name(shop_name: str) -> str:
        base_name = str(shop_name or "").strip()
        suffixes = (
            "--微信小店",
            "--微信",
            "—微信小店",
            "—微信",
            "-微信小店",
            "-微信",
            "（微信小店）",
            "（微信）",
            "(微信小店)",
            "(微信)",
            " 微信小店",
            " 微信",
        )
        for suffix in suffixes:
            if base_name.endswith(suffix):
                return base_name[: -len(suffix)].strip()
        return base_name

    @staticmethod
    def _build_auto_order_debug_payload(
        *,
        summary: str = "",
        stage: str = "",
        updated_at: str = "",
        screenshot_path: str = "",
        steps: list[dict] | tuple[dict, ...] | None = None,
    ) -> dict:
        normalized_steps = []
        for item in list(steps or []):
            if not isinstance(item, dict):
                continue
            normalized_steps.append(
                {
                    "at": str(item.get("at", "")).strip(),
                    "text": str(item.get("text", "")).strip(),
                }
            )
        return {
            "steps": normalized_steps,
            "screenshot_path": str(screenshot_path or "").strip(),
            "updated_at": str(updated_at or "").strip(),
            "stage": str(stage or "").strip(),
            "summary": str(summary or "").strip(),
        }

    @classmethod
    def _debug_payload_from_snapshot(cls, snapshot, summary: str) -> dict:
        return cls._build_auto_order_debug_payload(
            summary=summary,
            stage=str(getattr(snapshot, "debug_stage", "")).strip() or str(getattr(snapshot, "task_status", "")).strip(),
            updated_at=str(getattr(snapshot, "debug_updated_at", "")).strip() or str(getattr(snapshot, "updated_at", "")).strip(),
            screenshot_path=str(getattr(snapshot, "debug_screenshot_path", "")).strip(),
            steps=list(getattr(snapshot, "debug_steps", ()) or ()),
        )

    @staticmethod
    def _format_auto_order_check_result(result) -> str:
        status_label = {
            "success": "成功",
            "warning": "警告",
            "failed": "失败",
        }.get(str(getattr(result, "status", "")).strip(), "失败")
        lines = [f"{status_label}：{str(getattr(result, 'message', '')).strip()}"]
        account_name = str(getattr(result, "account_name", "")).strip()
        checked_at = str(getattr(result, "checked_at", "")).strip()
        if account_name:
            lines.append(f"账号：{account_name}")
        if checked_at:
            lines.append(f"时间：{checked_at}")
        for item in list(getattr(result, "checks", ()) or ()):
            if not isinstance(item, dict):
                continue
            label = str(item.get("label", "")).strip() or "检查项"
            item_status = {
                "success": "成功",
                "warning": "警告",
                "failed": "失败",
            }.get(str(item.get("status", "")).strip(), "失败")
            message = str(item.get("message", "")).strip()
            lines.append(f"- {label}：{item_status} {message}".rstrip())
        return "\n".join(lines)

    def _request_auto_order_for_record(
        self,
        record_id: str,
        *,
        source: str,
        procurement_indices: tuple[int, ...] = (),
    ) -> None:
        if self._history_store is None:
            return
        try:
            row = self._history_store.get(record_id)
        except KeyError:
            return
        if not row_has_auto_order_scope(row):
            return
        settings_payload = self.settings_page.to_payload()
        target_indices = procurement_indices or unresolved_procurement_indices(row)
        if not target_indices:
            return
        request = self._build_auto_order_request(
            row,
            source=source,
            procurement_indices=tuple(target_indices),
            settings_payload=settings_payload,
        )
        handler = self._resolve_auto_order_handler(settings_payload)
        if self._auto_order_uses_bridge(settings_payload, handler):
            validation_message = self._validate_bridge_request(request, settings_payload)
            if validation_message:
                preferred_accounts = ready_jd_accounts(request.jd_accounts) or enabled_jd_accounts(request.jd_accounts)
                account_name = preferred_accounts[0]["name"] if preferred_accounts else ""
                failed_result = build_failed_auto_order_result(
                    request.procurement_items,
                    request.procurement_indices,
                    validation_message,
                    account_name=account_name,
                )
                self._apply_auto_order_result(
                    record_id,
                    row,
                    failed_result,
                    task_fields={
                        "auto_order_task_id": "",
                        "auto_order_task_status": AUTO_ORDER_TASK_STATUS_FAILED,
                        "auto_order_task_submitted_at": "",
                        "auto_order_task_last_polled_at": now_timestamp(),
                    },
                    debug_payload=self._build_auto_order_debug_payload(
                        summary=failed_result.message,
                        stage="提交前校验失败",
                        updated_at=now_timestamp(),
                        steps=[{"at": now_timestamp(), "text": failed_result.message}],
                    ),
                )
                self._record_auto_order_display_status(source, record_id)
                return
            if not self._ensure_auto_order_service(settings_payload):
                failed_result = build_failed_auto_order_result(
                    request.procurement_items,
                    request.procurement_indices,
                    self._auto_order_service_manager.status_text(
                        normalize_auto_order_bridge_config(settings_payload)
                    ),
                )
                self._apply_auto_order_result(
                    record_id,
                    row,
                    failed_result,
                    task_fields={
                        "auto_order_task_id": "",
                        "auto_order_task_status": AUTO_ORDER_TASK_STATUS_FAILED,
                        "auto_order_task_submitted_at": "",
                        "auto_order_task_last_polled_at": now_timestamp(),
                    },
                    debug_payload=self._build_auto_order_debug_payload(
                        summary=failed_result.message,
                        stage="服务启动失败",
                        updated_at=now_timestamp(),
                        steps=[{"at": now_timestamp(), "text": failed_result.message}],
                    ),
                )
                self._record_auto_order_display_status(source, record_id)
                return
            try:
                ticket = handler.submit(request)
            except AutoOrderBridgeError as exc:
                if self._should_restart_auto_order_service_after_failure(settings_payload, str(exc)):
                    try:
                        ticket = handler.submit(request)
                    except AutoOrderBridgeError as retry_exc:
                        exc = retry_exc
                    else:
                        exc = None
                if exc is None:
                    pass
                else:
                    preferred_accounts = ready_jd_accounts(request.jd_accounts) or enabled_jd_accounts(
                        request.jd_accounts
                    )
                    account_name = preferred_accounts[0]["name"] if preferred_accounts else ""
                    failed_result = build_failed_auto_order_result(
                        request.procurement_items,
                        request.procurement_indices,
                        str(exc),
                        account_name=account_name,
                    )
                    self._apply_auto_order_result(
                        record_id,
                        row,
                        failed_result,
                        task_fields={
                            "auto_order_task_id": "",
                            "auto_order_task_status": AUTO_ORDER_TASK_STATUS_FAILED,
                            "auto_order_task_submitted_at": "",
                            "auto_order_task_last_polled_at": now_timestamp(),
                        },
                        debug_payload=self._build_auto_order_debug_payload(
                            summary=failed_result.message,
                            stage="创建任务失败",
                            updated_at=now_timestamp(),
                            steps=[{"at": now_timestamp(), "text": failed_result.message}],
                        ),
                    )
                    self._record_auto_order_display_status(source, record_id)
                    return
            initial_result = task_snapshot_to_result(
                task_ticket_to_snapshot(ticket),
                request.procurement_indices,
                request.procurement_items,
            )
            self._apply_auto_order_result(
                record_id,
                row,
                initial_result,
                task_fields={
                    "auto_order_task_id": ticket.task_id,
                    "auto_order_task_status": ticket.task_status,
                    "auto_order_task_submitted_at": ticket.submitted_at,
                    "auto_order_task_last_polled_at": ticket.updated_at,
                },
                debug_payload=self._build_auto_order_debug_payload(
                    summary=ticket.message or "排队中",
                    stage=ticket.task_status,
                    updated_at=ticket.updated_at or ticket.submitted_at,
                    steps=[{"at": ticket.updated_at or ticket.submitted_at or now_timestamp(), "text": ticket.message or "排队中"}],
                ),
            )
            self._record_auto_order_display_status(source, record_id)
            if not hasattr(handler, "poll"):
                failed_result = build_failed_auto_order_result(
                    request.procurement_items,
                    request.procurement_indices,
                    "自动拍单桥接缺少轮询接口",
                )
                self._apply_auto_order_result(
                    record_id,
                    self._history_store.get(record_id),
                    failed_result,
                    task_fields={
                        "auto_order_task_id": ticket.task_id,
                        "auto_order_task_status": AUTO_ORDER_TASK_STATUS_FAILED,
                        "auto_order_task_submitted_at": ticket.submitted_at,
                        "auto_order_task_last_polled_at": now_timestamp(),
                    },
                    debug_payload=self._build_auto_order_debug_payload(
                        summary=failed_result.message,
                        stage="轮询配置异常",
                        updated_at=now_timestamp(),
                        steps=[{"at": now_timestamp(), "text": failed_result.message}],
                    ),
                )
                self._record_auto_order_display_status(source, record_id)
                return
            self._start_auto_order_polling(record_id, request, handler, ticket, settings_payload)
            return
        result = handler.run(request)
        self._apply_auto_order_result(
            record_id,
            row,
            result,
            task_fields={
                "auto_order_task_id": "",
                "auto_order_task_status": "",
                "auto_order_task_submitted_at": "",
                "auto_order_task_last_polled_at": "",
            },
        )
        self._record_auto_order_display_status(source, record_id)

    def _build_auto_order_request(
        self,
        row: dict,
        *,
        source: str,
        procurement_indices: tuple[int, ...],
        settings_payload: dict,
    ) -> AutoOrderRequest:
        order_snapshot = dict(row.get("order_snapshot") or {})
        address_snapshot = dict(row.get("address_snapshot") or {})
        product_presets = settings_payload.get("product_presets")
        if not product_presets:
            product_presets = settings_payload.get("global_product_library", [])
        jd_links = {}
        for item in product_presets or []:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            if not name:
                continue
            jd_links[name] = str(item.get("jd_link", "")).strip()
        procurement_items = []
        for item in normalize_procurement_items(order_snapshot.get("procurement_items")):
            normalized_item = dict(item)
            product_name = str(normalized_item.get("product_name", "")).strip()
            normalized_item["jd_link"] = str(normalized_item.get("jd_link", "")).strip() or jd_links.get(product_name, "")
            procurement_items.append(normalized_item)
        return AutoOrderRequest(
            history_record_id=str(row.get("record_id", "")).strip(),
            source=source,
            shop_name=str(row.get("shop_name", "")).strip(),
            recipient_name=str(order_snapshot.get("recipient_name", "")).strip(),
            phone_number=str(order_snapshot.get("phone_number", "")).strip(),
            address=str(order_snapshot.get("address", "")).strip(),
            delivery_note=str(order_snapshot.get("delivery_note", "")).strip(),
            address_output_one=str(address_snapshot.get("output_one", "")).strip(),
            address_output_two=str(address_snapshot.get("output_two", "")).strip(),
            procurement_indices=tuple(procurement_indices),
            procurement_items=tuple(procurement_items),
            jd_accounts=tuple(normalize_jd_accounts(settings_payload.get("jd_accounts"))),
        )

    def _resolve_auto_order_handler(self, settings_payload: dict):
        if getattr(self._auto_order_executor, "submit", None) or getattr(self._auto_order_executor, "poll", None):
            return self._auto_order_executor
        bridge_config = normalize_auto_order_bridge_config(settings_payload)
        if bridge_config["enabled"]:
            return LocalHttpAutoOrderBridge(bridge_config)
        return self._auto_order_executor

    @staticmethod
    def _auto_order_uses_bridge(settings_payload: dict, handler: object) -> bool:
        bridge_config = normalize_auto_order_bridge_config(settings_payload)
        return bool(bridge_config["enabled"] and hasattr(handler, "submit"))

    @staticmethod
    def _validate_bridge_request(request: AutoOrderRequest, settings_payload: dict) -> str:
        bridge_config = normalize_auto_order_bridge_config(settings_payload)
        missing = []
        if not bridge_config["base_url"]:
            missing.append("自动拍单服务 Base URL")
        if not bridge_config["api_key"]:
            missing.append("自动拍单服务 API Key")
        if missing:
            return f"请先在设置页填写：{'、'.join(missing)}"
        enabled_accounts = enabled_jd_accounts(request.jd_accounts)
        if not enabled_accounts:
            return "请先在设置页启用至少一个京东账号环境"
        verified_accounts = ready_jd_accounts(request.jd_accounts)
        if not verified_accounts:
            return "请先勾选至少一个京东账号的地址槽已验证，再发起真实自动拍单"
        if not str(request.address_output_one).strip():
            return "缺少地址提取结果一"
        missing_links = []
        procurement_items = normalize_procurement_items(request.procurement_items)
        for index in request.procurement_indices:
            if index < 0 or index >= len(procurement_items):
                continue
            item = procurement_items[index]
            if not str(item.get("jd_link", "")).strip():
                missing_links.append(f"采购{index + 1}未配置京东链接")
        return "；".join(missing_links)

    def _start_auto_order_polling(
        self,
        record_id: str,
        request: AutoOrderRequest,
        bridge: AutoOrderBridge,
        ticket: AutoOrderTaskTicket,
        settings_payload: dict,
    ) -> None:
        self._stop_auto_order_task(record_id)
        bridge_config = normalize_auto_order_bridge_config(settings_payload)
        interval_ms = max(1, max(0, bridge_config["poll_interval_seconds"]) * 1000)
        timeout_seconds = max(1, bridge_config["timeout_seconds"])
        thread = QThread(self)
        worker = _AutoOrderPollWorker(
            record_id,
            bridge,
            ticket,
            interval_ms,
            timeout_seconds,
        )
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.snapshot_ready.connect(self._handle_auto_order_poll_snapshot)
        worker.failed.connect(self._handle_auto_order_poll_failure)
        worker.finished.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        self._active_auto_order_tasks[record_id] = {
            "record_id": record_id,
            "request": request,
            "source": request.source,
            "bridge": bridge,
            "ticket": ticket,
            "thread": thread,
            "worker": worker,
        }
        thread.start()

    def _handle_auto_order_poll_snapshot(self, record_id: str, snapshot) -> None:
        task_state = self._active_auto_order_tasks.get(record_id)
        if task_state is None:
            return
        if self._history_store is None:
            self._stop_auto_order_task(record_id)
            return
        task_state["ticket"] = AutoOrderTaskTicket(
            task_id=snapshot.task_id,
            task_status=snapshot.task_status,
            message=snapshot.message,
            submitted_at=snapshot.submitted_at,
            updated_at=snapshot.updated_at,
        )
        try:
            row = self._history_store.get(record_id)
        except KeyError:
            self._stop_auto_order_task(record_id)
            return
        result = task_snapshot_to_result(
            snapshot,
            task_state["request"].procurement_indices,
            (row.get("order_snapshot") or {}).get("procurement_items"),
        )
        self._apply_auto_order_result(
            record_id,
            row,
            result,
            task_fields={
                "auto_order_task_id": snapshot.task_id,
                "auto_order_task_status": snapshot.task_status,
                "auto_order_task_submitted_at": snapshot.submitted_at,
                "auto_order_task_last_polled_at": snapshot.updated_at or now_timestamp(),
            },
            debug_payload=self._debug_payload_from_snapshot(snapshot, result.message),
        )
        self._record_auto_order_display_status(str(task_state.get("source", "")), record_id)
        if snapshot.task_status not in {AUTO_ORDER_TASK_STATUS_QUEUED, AUTO_ORDER_TASK_STATUS_RUNNING}:
            self._stop_auto_order_task(record_id)

    def _handle_auto_order_poll_failure(self, record_id: str, message: str, last_polled_at: str) -> None:
        task_state = self._active_auto_order_tasks.get(record_id)
        if task_state is None or self._history_store is None:
            self._stop_auto_order_task(record_id)
            return
        try:
            row = self._history_store.get(record_id)
        except KeyError:
            self._stop_auto_order_task(record_id)
            return
        request = task_state["request"]
        result = build_failed_auto_order_result(
            request.procurement_items,
            request.procurement_indices,
            message,
            last_run_at=last_polled_at,
        )
        self._apply_auto_order_result(
            record_id,
            row,
            result,
            task_fields={
                "auto_order_task_id": str(task_state["ticket"].task_id),
                "auto_order_task_status": AUTO_ORDER_TASK_STATUS_FAILED,
                "auto_order_task_submitted_at": str(task_state["ticket"].submitted_at),
                "auto_order_task_last_polled_at": last_polled_at,
            },
            debug_payload=self._build_auto_order_debug_payload(
                summary=message,
                stage="轮询失败",
                updated_at=last_polled_at,
                steps=[{"at": last_polled_at, "text": message}],
            ),
        )
        self._record_auto_order_display_status(str(task_state.get("source", "")), record_id)
        self._stop_auto_order_task(record_id)

    def _stop_auto_order_task(self, record_id: str) -> None:
        task_state = self._active_auto_order_tasks.pop(record_id, None)
        if task_state is None:
            return
        worker = task_state.get("worker")
        if worker is not None:
            worker.stop()
        thread = task_state.get("thread")
        if isinstance(thread, QThread):
            thread.quit()
            thread.wait(3000)

    def _record_auto_order_display_status(self, source: str, record_id: str) -> None:
        if source != "intake" or self._history_store is None:
            return
        display_status = row_auto_order_status(self._history_store.get(record_id))
        self.intake_page.auto_order_status_label.setText(f"已送入自动拍单：{display_status}")

    def _sync_stale_auto_order_rows(self, rows: list[dict], active_task_ids: set[str]) -> list[dict]:
        if self._history_store is None or not rows:
            return rows
        settings_payload = self.settings_page.to_payload()
        handler = self._resolve_auto_order_handler(settings_payload)
        if not self._auto_order_uses_bridge(settings_payload, handler) or not hasattr(handler, "poll"):
            return rows
        updated_any = False
        for row in rows:
            if not row_needs_manual_retry_hint(row, active_task_ids):
                continue
            record_id = str(row.get("record_id", "")).strip()
            task_id = str(row.get("auto_order_task_id", "")).strip()
            if not record_id or not task_id:
                continue
            ticket = AutoOrderTaskTicket(
                task_id=task_id,
                task_status=str(row.get("auto_order_task_status", "")).strip(),
                message=str(row.get("auto_order_message", "")).strip(),
                submitted_at=str(row.get("auto_order_task_submitted_at", "")).strip(),
                updated_at=str(row.get("auto_order_task_last_polled_at", "")).strip(),
            )
            try:
                snapshot = handler.poll(ticket)
            except AutoOrderBridgeError:
                continue
            if snapshot.task_status in {AUTO_ORDER_TASK_STATUS_QUEUED, AUTO_ORDER_TASK_STATUS_RUNNING}:
                continue
            result = task_snapshot_to_result(
                snapshot,
                unresolved_procurement_indices(row),
                (row.get("order_snapshot") or {}).get("procurement_items"),
            )
            patch = self._build_auto_order_patch(
                row,
                result,
                task_fields={
                    "auto_order_task_id": snapshot.task_id,
                    "auto_order_task_status": snapshot.task_status,
                    "auto_order_task_submitted_at": snapshot.submitted_at,
                    "auto_order_task_last_polled_at": snapshot.updated_at or now_timestamp(),
                },
                debug_payload=self._debug_payload_from_snapshot(snapshot, result.message),
            )
            self._history_store.update(record_id, patch)
            updated_any = True
        return self._history_store.list_items() if updated_any else rows

    def _build_auto_order_patch(
        self,
        row: dict,
        result: AutoOrderResult,
        *,
        task_fields: dict | None = None,
        debug_payload: dict | None = None,
    ) -> dict:
        order_snapshot = dict(row.get("order_snapshot") or {})
        updated_items = apply_auto_order_result(order_snapshot.get("procurement_items"), result)
        order_snapshot["procurement_items"] = updated_items
        order_snapshot["procurement_tracking_number"] = " / ".join(
            str(item.get("tracking_number", "")).strip()
            for item in updated_items
            if str(item.get("tracking_number", "")).strip()
        )
        auto_order_status = str(result.order_status).strip() or summarize_auto_order_status(updated_items)
        auto_order_message = str(result.message).strip() or summarize_auto_order_message(updated_items)
        patch = {
            "order_snapshot": order_snapshot,
            "auto_order_status": auto_order_status,
            "auto_order_message": auto_order_message,
            "auto_order_last_run_at": str(result.last_run_at).strip(),
        }
        patch["auto_order_debug"] = debug_payload or self._build_auto_order_debug_payload(
            summary=auto_order_message,
            stage=auto_order_status,
            updated_at=str(result.last_run_at).strip(),
        )
        if task_fields:
            patch.update(task_fields)
        return patch

    def _apply_auto_order_result(
        self,
        record_id: str,
        row: dict,
        result: AutoOrderResult,
        *,
        task_fields: dict | None = None,
        debug_payload: dict | None = None,
    ) -> None:
        patch = self._build_auto_order_patch(
            row,
            result,
            task_fields=task_fields,
            debug_payload=debug_payload,
        )
        self._update_history_snapshot(record_id, patch)

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

    def _extract_order_from_image(self, image_bytes: bytes, on_progress=None):
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
        extract_batch = getattr(pipeline, "extract_order_batch", None)
        if callable(extract_batch):
            try:
                signature = inspect.signature(extract_batch)
            except (TypeError, ValueError):
                batch_results = extract_batch(image_bytes)
            else:
                if "on_progress" in signature.parameters:
                    batch_results = extract_batch(image_bytes, on_progress=on_progress)
                else:
                    batch_results = extract_batch(image_bytes)
            successful_results = [
                item
                for item in batch_results
                if isinstance(item, dict) and item.get("ok") is not False and isinstance(item.get("order"), ParsedOrder)
            ]
            failed_messages = [
                str(item.get("error", "")).strip()
                for item in batch_results
                if isinstance(item, dict) and item.get("ok") is False and str(item.get("error", "")).strip()
            ]
            total_count = sum(1 for item in batch_results if isinstance(item, dict))
            if len(successful_results) > 1:
                if on_progress is not None:
                    on_progress("正在裁剪SKU图片...")
                recognized_orders = [
                    self._attach_sku_image_to_order_result(item, fallback_image_bytes=image_bytes)
                    for item in successful_results
                ]
                if failed_messages:
                    return {
                        "recognized_orders": recognized_orders,
                        "failed_messages": failed_messages,
                        "total_count": total_count or len(recognized_orders),
                    }
                return recognized_orders
            if len(successful_results) == 1:
                if on_progress is not None:
                    on_progress("正在裁剪SKU图片...")
                recognized_order = self._attach_sku_image_to_order_result(
                    successful_results[0],
                    fallback_image_bytes=image_bytes,
                )
                if failed_messages:
                    return {
                        "recognized_orders": [recognized_order],
                        "failed_messages": failed_messages,
                        "total_count": total_count or 1,
                    }
                return recognized_order
            errors = [
                str(item.get("error", "")).strip()
                for item in batch_results
                if isinstance(item, dict) and str(item.get("error", "")).strip()
            ]
            if errors:
                raise ValueError("；".join(errors))

        extract_order = pipeline.extract_order
        try:
            signature = inspect.signature(extract_order)
        except (TypeError, ValueError):
            order = extract_order(image_bytes)
        else:
            if "on_progress" in signature.parameters:
                order = extract_order(image_bytes, on_progress=on_progress)
            else:
                order = extract_order(image_bytes)
        if on_progress is not None:
            on_progress("正在裁剪SKU图片...")
        sku_image_path = crop_sku_image_from_order_screenshot(image_bytes, order_id=order.order_id)
        return replace(order, sku_image_path=sku_image_path)

    @staticmethod
    def _attach_sku_image_to_order_result(result: dict, *, fallback_image_bytes: bytes) -> ParsedOrder:
        order = result.get("order")
        if not isinstance(order, ParsedOrder):
            raise ValueError("missing parsed order")
        source_image_bytes = result.get("source_image_bytes")
        if not isinstance(source_image_bytes, bytes):
            source_image_bytes = fallback_image_bytes
        sku_image_path = crop_sku_image_from_order_screenshot(source_image_bytes, order_id=order.order_id)
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
            "field_aliases": self._build_feishu_field_aliases(field_mapping),
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
            jd_link = str(item.get("jd_link", "")).strip()
            procurement_items.append(
                ProcurementItem(
                    product_name,
                    (
                        quantity
                        if quantity != "1" or any((product_name, cost, tracking_number, jd_link))
                        else ""
                    ) or ("1" if any((product_name, cost, tracking_number, jd_link)) else ""),
                    cost,
                    tracking_number,
                    jd_link,
                )
            )
        while len(procurement_items) < 3:
            procurement_items.append(ProcurementItem("", "", "", "", ""))

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
        fields = dict(task["fields"])
        skipped_source_fields: tuple[str, ...] = ()
        try:
            available_fields = client.list_field_names(access_token)
        except Exception:
            available_fields = set()
        if available_fields:
            fields, skipped_source_fields = MainWindow._filter_feishu_fields_for_available_table(
                fields,
                available_fields,
                task.get("field_aliases"),
            )
            if not fields:
                skipped_text = "、".join(skipped_source_fields) if skipped_source_fields else "全部字段"
                raise ValueError(f"飞书写入失败：当前表缺少可写字段（{skipped_text}），请先检查设置")
        sync_message = "写入成功"
        feishu_record_id = str(task.get("feishu_record_id", "")).strip()
        if task.get("mode") == "update_or_create" and feishu_record_id:
            try:
                response = client.update_record(access_token, feishu_record_id, fields)
                sync_message = "已保存并同步飞书"
            except ValueError as exc:
                if not MainWindow._is_missing_record_error(str(exc)):
                    raise
                response = client.create_record(access_token, fields)
                sync_message = "原记录不存在，已自动新建"
        else:
            response = client.create_record(access_token, fields)
        if skipped_source_fields:
            sync_message += f"，已跳过缺失字段：{'、'.join(skipped_source_fields)}"
        return {
            "payload": task["payload"],
            "shop_name": task["shop_name"],
            "response": response,
            "history_record_id": task.get("history_record_id"),
            "sync_message": sync_message,
            "feishu_record_id": MainWindow._extract_feishu_record_id(response),
            "skipped_source_fields": skipped_source_fields,
            "auto_order_after_submit": bool(task.get("auto_order_after_submit")),
            "auto_order_source": str(task.get("auto_order_source", "intake")).strip() or "intake",
        }

    def _handle_submit_success(self, result: dict) -> None:
        payload = result["payload"]
        shop_name = result["shop_name"]
        history_record_id = result.get("history_record_id")
        sync_message = str(result.get("sync_message", "")).strip() or "写入成功"
        skipped_source_fields = tuple(
            str(item).strip() for item in (result.get("skipped_source_fields") or ()) if str(item).strip()
        )
        auto_order_after_submit = bool(result.get("auto_order_after_submit"))
        auto_order_source = str(result.get("auto_order_source", "intake")).strip() or "intake"
        self.intake_page.set_submit_in_progress(False)
        status_text = f"已写入飞书：{shop_name}"
        if skipped_source_fields:
            status_text += f"（跳过{len(skipped_source_fields)}个缺失字段）"
        self.intake_page.capture_widget.status_label.setText(status_text)
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
            saved_row = self._save_history_snapshot(snapshot)
            history_record_id = None if saved_row is None else saved_row.get("record_id")
        if auto_order_after_submit and history_record_id:
            self._request_auto_order_for_record(
                history_record_id,
                source=auto_order_source,
            )

    def _handle_submit_failure(self, failure: dict) -> None:
        message = str(failure.get("message", "")).strip() or "飞书写入失败"
        payload = failure.get("payload")
        history_record_id = failure.get("history_record_id")
        self.intake_page.set_submit_in_progress(False)
        self.intake_page.capture_widget.status_label.setText(message)
        self.intake_page.auto_order_status_label.clear()
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

    @staticmethod
    def _build_feishu_field_aliases(field_mapping: dict[str, str] | None) -> dict[str, str]:
        mapping = dict(DEFAULT_FEISHU_FIELD_MAPPING)
        if field_mapping:
            mapping.update(field_mapping)
        aliases: dict[str, str] = {}
        for source_name, target_name in mapping.items():
            target_text = str(target_name).strip()
            if target_text and target_text not in aliases:
                aliases[target_text] = str(source_name).strip()
        return aliases

    @staticmethod
    def _filter_feishu_fields_for_available_table(
        fields: dict[str, object],
        available_fields: set[str],
        field_aliases: dict[str, str] | None = None,
    ) -> tuple[dict[str, object], tuple[str, ...]]:
        filtered_fields: dict[str, object] = {}
        skipped_source_fields: list[str] = []
        aliases = field_aliases or {}
        for target_name, value in dict(fields).items():
            if str(target_name).strip() in available_fields:
                filtered_fields[target_name] = value
                continue
            skipped_source_fields.append(str(aliases.get(target_name, target_name)).strip() or str(target_name))
        unique_skipped = tuple(dict.fromkeys(item for item in skipped_source_fields if item))
        return filtered_fields, unique_skipped

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
        for record_id in list(self._active_auto_order_tasks.keys()):
            self._stop_auto_order_task(record_id)
        self._auto_order_service_manager.shutdown()
        self._stop_mobile_order_server()
        self._stop_wechat_service()
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
