from __future__ import annotations

from dataclasses import replace
import inspect
from typing import Callable

from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QFrame,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from strawberry_order_management.ui.widgets.address_extractor_widget import (
    AddressExtractorWidget,
)
from strawberry_order_management.extractors.supplemental_order import parse_supplemental_order_text
from strawberry_order_management.models import ParsedOrder, ProcurementItem
from strawberry_order_management.ui.widgets.order_card_widget import OrderCardWidget
from strawberry_order_management.ui.widgets.screenshot_input_widget import (
    ScreenshotInputWidget,
)


class _ImageWorker(QObject):
    finished = Signal(object)
    failed = Signal(str)
    progress = Signal(str)

    def __init__(self, callback: Callable[[bytes, Callable[[str], None]], object], image_bytes: bytes):
        super().__init__()
        self._callback = callback
        self._image_bytes = image_bytes

    def run(self) -> None:
        try:
            result = self._callback(self._image_bytes, self.progress.emit)
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.finished.emit(result)


class IntakePage(QWidget):
    submit_requested = Signal(object)
    submit_auto_order_requested = Signal(object)
    save_history_requested = Signal(object)
    product_library_requested = Signal(str, str)
    procurement_template_requested = Signal(object)
    PLATFORM_OPTIONS = ("抖店", "微信小店")

    def __init__(
        self,
        on_submit: Callable[[object], None] | None = None,
        on_submit_and_auto_order: Callable[[object], None] | None = None,
        on_save_history: Callable[[object], None] | None = None,
        on_process_image: Callable[[bytes], object] | None = None,
        use_background_thread: bool = True,
    ) -> None:
        super().__init__()
        self.capture_widget = ScreenshotInputWidget()
        self.order_card_widget = OrderCardWidget()
        self.address_widget = AddressExtractorWidget()
        self.shop_selector = QComboBox()
        self.platform_selector = QComboBox()
        self.save_history_button = QPushButton("仅存历史")
        self.submit_button = QPushButton("确认写入飞书")
        self.submit_auto_order_button = QPushButton("写飞书并自动拍单")
        self.auto_order_status_label = QLabel("")
        self.auto_order_status_label.setObjectName("MutedText")
        self.batch_selector_card = QFrame()
        self.batch_selector_card.setObjectName("EntryBatchSelectorCard")
        self.batch_selector_label = QLabel("")
        self.batch_selector_label.setObjectName("MutedText")
        self.batch_selector_buttons = QWidget()
        self._batch_selector_layout = QVBoxLayout(self.batch_selector_buttons)
        self._batch_selector_layout.setContentsMargins(0, 0, 0, 0)
        self._batch_selector_layout.setSpacing(6)
        self._on_submit = on_submit
        self._on_submit_and_auto_order = on_submit_and_auto_order
        self._on_save_history = on_save_history
        self._on_process_image = on_process_image
        self._use_background_thread = use_background_thread
        self._current_order = None
        self._current_source_label = ""
        self._thread = None
        self._worker = None
        self._shop_platforms: dict[str, str] = {}
        self._platform_default_shops: dict[str, str] = {}
        self._syncing_shop_platform = False
        self._recognized_orders: list[ParsedOrder] = []
        self._recognized_total_count = 0
        self._recognized_failed_messages: list[str] = []
        self._batch_base_order: ParsedOrder | None = None
        self._batch_order_buttons: list[QPushButton] = []
        self.shop_selector.setPlaceholderText("请选择店铺")
        self.platform_selector.addItems(list(self.PLATFORM_OPTIONS))
        self.platform_selector.setCurrentText("抖店")
        self.save_history_button.setEnabled(False)
        self.submit_button.setEnabled(False)
        self.submit_auto_order_button.setEnabled(False)
        extractor_input_panel, extractor_results_panel = self.address_widget.take_workspace_panels()
        self.address_widget.input_edit.setMinimumHeight(116)
        self.address_widget.input_edit.setMaximumHeight(156)
        self.address_widget.output_one.setMinimumHeight(96)
        self.address_widget.output_one.setMaximumHeight(128)
        self.address_widget.output_two.setMinimumHeight(96)
        self.address_widget.output_two.setMaximumHeight(128)

        shop_row = QHBoxLayout()
        shop_label = QLabel("店铺")
        shop_label.setObjectName("OrderFieldLabel")
        shop_row.addWidget(shop_label)
        shop_row.addWidget(self.shop_selector, 1)

        platform_row = QHBoxLayout()
        platform_label = QLabel("平台")
        platform_label.setObjectName("OrderFieldLabel")
        platform_row.addWidget(platform_label)
        platform_row.addWidget(self.platform_selector, 1)

        action_bar = QFrame()
        action_bar.setObjectName("EntryActionBar")
        action_bar_layout = QHBoxLayout(action_bar)
        action_bar_layout.setContentsMargins(16, 12, 16, 12)
        action_bar_layout.setSpacing(12)
        action_bar_layout.addLayout(shop_row, 1)
        action_bar_layout.addLayout(platform_row, 0)
        action_bar_layout.addStretch(1)
        action_bar_layout.addWidget(self.save_history_button)
        action_bar_layout.addWidget(self.submit_button)
        action_bar_layout.addWidget(self.submit_auto_order_button)

        left_column = QWidget()
        left_column.setObjectName("EntryLeftRail")
        left_column.setFixedWidth(304)
        left_column_layout = QVBoxLayout(left_column)
        left_column_layout.setContentsMargins(0, 0, 0, 0)
        left_column_layout.setSpacing(12)

        capture_card = QFrame()
        capture_card.setObjectName("EntryCaptureCard")
        capture_layout = QVBoxLayout(capture_card)
        capture_layout.setContentsMargins(16, 14, 16, 16)
        capture_layout.setSpacing(10)
        capture_layout.addWidget(self.capture_widget)
        capture_layout.addWidget(self.auto_order_status_label)
        batch_selector_layout = QVBoxLayout(self.batch_selector_card)
        batch_selector_layout.setContentsMargins(12, 10, 12, 12)
        batch_selector_layout.setSpacing(8)
        batch_selector_layout.addWidget(self.batch_selector_label)
        batch_selector_layout.addWidget(self.batch_selector_buttons)
        self.batch_selector_card.hide()

        extractor_input_card = QFrame()
        extractor_input_card.setObjectName("EntryExtractorInputCard")
        extractor_input_layout = QVBoxLayout(extractor_input_card)
        extractor_input_layout.setContentsMargins(16, 14, 16, 16)
        extractor_input_layout.setSpacing(10)
        extractor_input_layout.addWidget(extractor_input_panel)

        extractor_results_card = QFrame()
        extractor_results_card.setObjectName("EntryExtractorResultCard")
        extractor_results_layout = QVBoxLayout(extractor_results_card)
        extractor_results_layout.setContentsMargins(16, 14, 16, 16)
        extractor_results_layout.setSpacing(0)
        extractor_results_layout.addWidget(extractor_results_panel)

        left_column_layout.addWidget(capture_card)
        left_column_layout.addWidget(self.batch_selector_card)
        left_column_layout.addWidget(extractor_input_card)
        left_column_layout.addWidget(extractor_results_card)
        left_column_layout.addStretch(1)

        center_scroll = QScrollArea()
        center_scroll.setObjectName("EntryFormRail")
        center_scroll.setWidgetResizable(True)
        center_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        center_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        center_scroll.viewport().setObjectName("EntryFormViewport")
        center_scroll.setWidget(self.order_card_widget)

        content = QWidget()
        content.setObjectName("PageContent")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(16, 16, 16, 16)
        content_layout.setSpacing(14)
        content_layout.addWidget(action_bar)

        workspace = QWidget()
        workspace_layout = QHBoxLayout(workspace)
        workspace_layout.setContentsMargins(0, 0, 0, 0)
        workspace_layout.setSpacing(16)
        workspace_layout.addWidget(left_column, 0)
        workspace_layout.addWidget(center_scroll, 1)
        content_layout.addWidget(workspace, 1)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setWidget(content)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(scroll_area)
        self.submit_button.clicked.connect(self._handle_submit)
        self.submit_auto_order_button.clicked.connect(self._handle_submit_and_auto_order)
        self.save_history_button.clicked.connect(self._handle_save_history)
        self.shop_selector.currentTextChanged.connect(self._handle_shop_changed)
        self.platform_selector.currentTextChanged.connect(self._handle_platform_changed)
        self.capture_widget.image_ready.connect(self.process_image_bytes)
        self.address_widget.extracted.connect(self._handle_manual_text_extracted)
        self.order_card_widget.product_library_requested.connect(self.product_library_requested.emit)
        self.order_card_widget.procurement_template_requested.connect(self.procurement_template_requested.emit)

    def show_order(self, order) -> None:
        self._recognized_orders = []
        self._batch_base_order = None
        self._clear_batch_selector()
        self._display_order(order)

    def _display_order(self, order) -> None:
        self._current_order = order
        self.order_card_widget.load_order(order)
        platform = getattr(order, "platform", "") or "抖店"
        if self.platform_selector.findText(platform) >= 0:
            self.platform_selector.setCurrentText(platform)
        self.address_widget.load_from_order(order)
        self.save_history_button.setEnabled(True)
        self.submit_button.setEnabled(True)
        self.submit_auto_order_button.setEnabled(True)
        self.auto_order_status_label.clear()
        self._warn_for_large_quantity(order)

    def set_product_presets(self, product_presets: list[dict[str, str]]) -> None:
        self.order_card_widget.set_product_presets(product_presets)

    def set_procurement_templates(self, procurement_templates: list[dict[str, object]]) -> None:
        self.order_card_widget.set_procurement_templates(procurement_templates)

    def set_custom_cost_labels(self, labels: list[str]) -> None:
        self.order_card_widget.set_custom_cost_labels(labels)

    def process_image_bytes(self, image_bytes: bytes, source_label: str) -> None:
        if self._on_process_image is None:
            self.capture_widget.status_label.setText("请先在设置页完成 API 配置")
            return
        self._current_source_label = source_label
        self.capture_widget.status_label.setText(f"{source_label}：识别中，右侧暂时还是当前内容")
        if not self._use_background_thread:
            self._run_sync(image_bytes)
            return
        self._start_background_job(image_bytes)

    def _handle_submit(self) -> None:
        payload = self._build_submission_payload()
        if payload is None:
            return
        self.submit_requested.emit(payload)
        if self._on_submit is not None:
            self._on_submit(payload)

    def _handle_submit_and_auto_order(self) -> None:
        payload = self._build_submission_payload()
        if payload is None:
            return
        self.submit_auto_order_requested.emit(payload)
        if self._on_submit_and_auto_order is not None:
            self._on_submit_and_auto_order(payload)

    def _handle_save_history(self) -> None:
        payload = self._build_submission_payload()
        if payload is None:
            return
        self.save_history_requested.emit(payload)
        if self._on_save_history is not None:
            self._on_save_history(payload)

    def _handle_manual_text_extracted(self, raw_text: str, _payload: object) -> None:
        patch = {
            key: value
            for key, value in parse_supplemental_order_text(raw_text).items()
            if str(value).strip()
        }
        if not patch:
            return
        has_order_fields = bool(
            {
                "order_id",
                "placed_at",
                "product_name",
                "specification",
                "quantity",
                "order_amount",
                "income_amount",
            }
            & set(patch)
        )
        base_order = self.order_card_widget.to_order() if self._current_order is not None else self._blank_order()
        if "platform" not in patch:
            patch["platform"] = self.platform_selector.currentText().strip() or "抖店"
        self.show_order(replace(base_order, **patch))
        if has_order_fields:
            self.address_widget.status_label.setText("已按文字补单填入订单")
        else:
            self.address_widget.status_label.setText("已填入收货信息，订单号和商品请继续补齐")

    def set_shop_names(self, shop_names: list[str], selected_name: str | None = None) -> None:
        current = selected_name or self.shop_selector.currentText()
        self.shop_selector.blockSignals(True)
        self.shop_selector.clear()
        self.shop_selector.addItems(shop_names)
        if current:
            index = self.shop_selector.findText(current)
            if index >= 0:
                self.shop_selector.setCurrentIndex(index)
        self.shop_selector.blockSignals(False)
        self._handle_shop_changed(self.shop_selector.currentText())

    @staticmethod
    def _blank_order() -> ParsedOrder:
        return ParsedOrder(
            order_id="",
            placed_at="",
            order_status="已发货",
            product_name="",
            quantity="",
            order_amount="",
            income_amount="",
            recipient_name="",
            phone_number="",
            code="",
            address="",
            delivery_note="",
        )

    def set_shop_platforms(self, shop_platforms: dict[str, str]) -> None:
        self._shop_platforms = {
            str(name).strip(): str(platform).strip()
            for name, platform in shop_platforms.items()
            if str(name).strip()
        }
        self._handle_shop_changed(self.shop_selector.currentText())

    def set_platform_default_shops(self, platform_default_shops: dict[str, str]) -> None:
        self._platform_default_shops = {
            str(platform).strip(): str(shop_name).strip()
            for platform, shop_name in platform_default_shops.items()
            if str(platform).strip() and str(shop_name).strip()
        }

    def _build_submission_payload(self):
        if self._current_order is None:
            return None
        return {
            "shop_name": self.shop_selector.currentText().strip(),
            "order": replace(
                self.order_card_widget.to_order(),
                platform=self.platform_selector.currentText().strip() or "抖店",
            ),
        }

    def _handle_shop_changed(self, shop_name: str) -> None:
        if self._syncing_shop_platform:
            return
        platform = self._shop_platforms.get(str(shop_name).strip(), "")
        if platform and self.platform_selector.findText(platform) >= 0:
            self._syncing_shop_platform = True
            try:
                self.platform_selector.setCurrentText(platform)
            finally:
                self._syncing_shop_platform = False

    def _handle_platform_changed(self, platform: str) -> None:
        if self._syncing_shop_platform:
            return
        self._select_shop_for_platform(platform)

    def _select_shop_for_platform(self, platform: str) -> None:
        platform = str(platform).strip()
        if not platform:
            return
        current_shop = self.shop_selector.currentText().strip()
        if self._shop_platforms.get(current_shop) == platform:
            return
        target_shop = self._find_shop_for_platform(platform, current_shop)
        if not target_shop:
            return
        target_index = self.shop_selector.findText(target_shop)
        if target_index < 0:
            return
        self._syncing_shop_platform = True
        try:
            self.shop_selector.setCurrentIndex(target_index)
        finally:
            self._syncing_shop_platform = False

    def _find_shop_for_platform(self, platform: str, current_shop: str) -> str:
        candidates = [
            self.shop_selector.itemText(index).strip()
            for index in range(self.shop_selector.count())
            if self._shop_platforms.get(self.shop_selector.itemText(index).strip()) == platform
        ]
        if not candidates:
            return ""
        configured_default_shop = self._platform_default_shops.get(platform, "")
        if configured_default_shop in candidates:
            return configured_default_shop
        current_base = self._shop_base_name(current_shop)
        if current_base:
            for candidate in candidates:
                if self._shop_base_name(candidate) == current_base:
                    return candidate
        return candidates[0]

    @staticmethod
    def _shop_base_name(shop_name: str) -> str:
        base_name = str(shop_name).strip()
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

    def set_submit_in_progress(self, in_progress: bool) -> None:
        self.submit_button.setEnabled(not in_progress)
        self.submit_auto_order_button.setEnabled(not in_progress)
        self.submit_button.setText("写入中..." if in_progress else "确认写入飞书")
        self.submit_auto_order_button.setText("写入中..." if in_progress else "写飞书并自动拍单")

    def _run_sync(self, image_bytes: bytes) -> None:
        try:
            order = self._invoke_process_image(image_bytes, self._update_process_status)
        except Exception as exc:
            self.capture_widget.status_label.setText(str(exc))
            return
        self._handle_process_success(order)

    def _start_background_job(self, image_bytes: bytes) -> None:
        self._thread = QThread(self)
        self._worker = _ImageWorker(self._invoke_process_image, image_bytes)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._update_process_status)
        self._worker.finished.connect(self._handle_process_success)
        self._worker.failed.connect(self._handle_process_failure)
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(self._clear_worker_refs)
        self._thread.start()

    def _handle_process_success(self, order) -> None:
        recognized_orders, failed_messages, total_count = self._recognized_orders_from_result(order)
        if failed_messages and not recognized_orders:
            self._recognized_orders = []
            self._batch_base_order = None
            self._clear_batch_selector()
            self.capture_widget.status_label.setText("；".join(failed_messages))
            return
        if len(recognized_orders) > 1 or (recognized_orders and total_count > len(recognized_orders)):
            self._batch_base_order = self.order_card_widget.to_order() if self._current_order is not None else self._blank_order()
            self._recognized_orders = recognized_orders
            self._recognized_total_count = max(total_count, len(recognized_orders))
            self._recognized_failed_messages = failed_messages
            self._render_batch_selector()
            self._select_batch_order(0)
            return
        if len(recognized_orders) == 1:
            order = recognized_orders[0]
            self._recognized_orders = []
            self._clear_batch_selector()
            self._batch_base_order = None
        merged_order, retained_existing_values = self._merge_order_from_recognition(order)
        self._display_order(merged_order)
        if retained_existing_values:
            self.capture_widget.status_label.setText(
                f"已完成{self._current_source_label}识别，缺失字段已保留原填写内容"
            )
        else:
            self.capture_widget.status_label.setText(f"已完成{self._current_source_label}识别")

    @staticmethod
    def _recognized_orders_from_result(result: object) -> tuple[list[ParsedOrder], list[str], int]:
        if isinstance(result, dict) and "recognized_orders" in result:
            orders = [
                item
                for item in result.get("recognized_orders", [])
                if isinstance(item, ParsedOrder)
            ]
            failed_messages = [
                str(message).strip()
                for message in result.get("failed_messages", [])
                if str(message).strip()
            ]
            total_count = int(result.get("total_count") or len(orders) + len(failed_messages))
            return orders, failed_messages, total_count
        if isinstance(result, ParsedOrder):
            return [result], [], 1
        if not isinstance(result, (list, tuple)):
            return [], [], 0
        orders: list[ParsedOrder] = []
        failed_messages: list[str] = []
        for item in result:
            if isinstance(item, ParsedOrder):
                orders.append(item)
                continue
            if isinstance(item, dict):
                order = item.get("order")
                if item.get("ok") is False:
                    error_text = str(item.get("error", "")).strip()
                    if error_text:
                        failed_messages.append(error_text)
                    continue
                if isinstance(order, ParsedOrder):
                    orders.append(order)
        return orders, failed_messages, len(orders) + len(failed_messages)

    def _render_batch_selector(self) -> None:
        self._clear_batch_buttons()
        total_count = self._recognized_total_count or len(self._recognized_orders)
        failed_count = len(self._recognized_failed_messages)
        if failed_count:
            self.batch_selector_label.setText(
                f"识别到 {total_count} 单，其中 {failed_count} 单失败，点下面切换填写"
            )
        else:
            self.batch_selector_label.setText(f"识别到 {len(self._recognized_orders)} 单，点下面切换填写")
        for index, order in enumerate(self._recognized_orders):
            button = QPushButton(self._batch_button_text(index, order))
            button.setObjectName("BatchOrderButton")
            button.setCheckable(True)
            button.clicked.connect(lambda _checked=False, item_index=index: self._select_batch_order(item_index))
            self._batch_selector_layout.addWidget(button)
            self._batch_order_buttons.append(button)
        self.batch_selector_card.show()

    def _clear_batch_selector(self) -> None:
        self._clear_batch_buttons()
        self.batch_selector_label.clear()
        self._recognized_total_count = 0
        self._recognized_failed_messages = []
        self.batch_selector_card.hide()

    def _clear_batch_buttons(self) -> None:
        while self._batch_selector_layout.count():
            item = self._batch_selector_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._batch_order_buttons = []

    def _select_batch_order(self, index: int) -> None:
        if index < 0 or index >= len(self._recognized_orders):
            return
        base_order = self._batch_base_order or self._blank_order()
        merged_order, retained_existing_values = self._merge_order_from_recognition(
            self._recognized_orders[index],
            base_order=base_order,
        )
        self._display_order(merged_order)
        for button_index, button in enumerate(self._batch_order_buttons):
            button.setChecked(button_index == index)
        total_count = self._recognized_total_count or len(self._recognized_orders)
        failed_count = len(self._recognized_failed_messages)
        if failed_count:
            status_text = (
                f"已完成{self._current_source_label}识别，识别到 {total_count} 单，"
                f"其中 {failed_count} 单失败，当前第 {index + 1} 个成功订单"
            )
        else:
            status_text = f"已完成{self._current_source_label}识别，识别到 {len(self._recognized_orders)} 单，当前第 {index + 1} 单"
        if retained_existing_values:
            status_text += "，缺失字段已保留原填写内容"
        self.capture_widget.status_label.setText(status_text)

    @staticmethod
    def _batch_button_text(index: int, order: ParsedOrder) -> str:
        recipient = str(order.recipient_name or "未识别收件人").strip()
        income = str(order.income_amount or "").strip()
        suffix = f" · 收入 {income}" if income else ""
        return f"第{index + 1}单 {recipient}{suffix}"

    def _handle_process_failure(self, message: str) -> None:
        self.capture_widget.status_label.setText(message)

    def _clear_worker_refs(self) -> None:
        self._thread = None
        self._worker = None

    def shutdown_background_job(self) -> None:
        thread = self._thread
        if thread is None:
            return
        thread.quit()
        thread.wait(3000)
        self._clear_worker_refs()

    def closeEvent(self, event) -> None:
        self.shutdown_background_job()
        super().closeEvent(event)

    def _warn_for_large_quantity(self, order) -> None:
        if not self.isVisible():
            return
        quantity_text = str(getattr(order, "quantity", "")).strip()
        try:
            quantity = float(quantity_text)
        except ValueError:
            return
        if quantity <= 1:
            return
        QMessageBox.warning(
            self,
            "数量提醒",
            "当前订单数量大于 1，请确认采购数量不要和实际订单数量不一致。",
        )

    def _invoke_process_image(
        self,
        image_bytes: bytes,
        on_progress: Callable[[str], None],
    ):
        callback = self._on_process_image
        if callback is None:
            raise ValueError("请先在设置页完成 API 配置")
        try:
            signature = inspect.signature(callback)
        except (TypeError, ValueError):
            return callback(image_bytes)
        parameters = list(signature.parameters.values())
        if any(parameter.kind == inspect.Parameter.VAR_POSITIONAL for parameter in parameters):
            return callback(image_bytes, on_progress)
        if "on_progress" in signature.parameters:
            return callback(image_bytes, on_progress=on_progress)
        positional_count = sum(
            parameter.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
            for parameter in parameters
        )
        if positional_count >= 2:
            return callback(image_bytes, on_progress)
        return callback(image_bytes)

    def _update_process_status(self, message: str) -> None:
        text = str(message or "").strip()
        if not text:
            return
        source_label = str(self._current_source_label or "").strip()
        if source_label:
            self.capture_widget.status_label.setText(f"{source_label}：{text}")
            return
        self.capture_widget.status_label.setText(text)

    def _merge_order_from_recognition(
        self,
        recognized_order: ParsedOrder,
        *,
        base_order: ParsedOrder | None = None,
    ) -> tuple[ParsedOrder, bool]:
        if base_order is None:
            base_order = self.order_card_widget.to_order() if self._current_order is not None else self._blank_order()
        retained_existing_values = self._has_retained_existing_values(base_order, recognized_order)
        merged_order = ParsedOrder(
            order_id=self._prefer_recognized_text(base_order.order_id, recognized_order.order_id),
            placed_at=self._prefer_recognized_text(base_order.placed_at, recognized_order.placed_at),
            order_status=self._prefer_recognized_text(base_order.order_status, recognized_order.order_status),
            product_name=self._prefer_recognized_text(base_order.product_name, recognized_order.product_name),
            specification=self._prefer_recognized_text(base_order.specification, recognized_order.specification),
            sku=self._prefer_recognized_text(base_order.sku, recognized_order.sku),
            sku_image_path=str(recognized_order.sku_image_path or "").strip(),
            quantity=self._prefer_recognized_text(base_order.quantity, recognized_order.quantity),
            order_amount=self._prefer_recognized_text(base_order.order_amount, recognized_order.order_amount),
            income_amount=self._prefer_recognized_text(base_order.income_amount, recognized_order.income_amount),
            recipient_name=self._prefer_recognized_text(base_order.recipient_name, recognized_order.recipient_name),
            phone_number=self._prefer_recognized_text(base_order.phone_number, recognized_order.phone_number),
            code=self._prefer_recognized_text(base_order.code, recognized_order.code),
            address=self._prefer_recognized_text(base_order.address, recognized_order.address),
            delivery_note=self._prefer_recognized_text(base_order.delivery_note, recognized_order.delivery_note),
            procurement_tracking_number=self._prefer_recognized_text(
                base_order.procurement_tracking_number,
                recognized_order.procurement_tracking_number,
            ),
            platform=self.platform_selector.currentText().strip() or base_order.platform or recognized_order.platform or "抖店",
            platform_fee_rate=self._prefer_recognized_text(base_order.platform_fee_rate, recognized_order.platform_fee_rate),
            platform_fee_amount=self._prefer_recognized_text(
                base_order.platform_fee_amount,
                recognized_order.platform_fee_amount,
            ),
            other_cost=self._prefer_recognized_text(base_order.other_cost, recognized_order.other_cost),
            procurement_total_cost=self._prefer_recognized_text(
                base_order.procurement_total_cost,
                recognized_order.procurement_total_cost,
            ),
            gross_profit=self._prefer_recognized_text(base_order.gross_profit, recognized_order.gross_profit),
            custom_cost_labels=self._merge_text_tuple(
                base_order.custom_cost_labels,
                recognized_order.custom_cost_labels,
            ),
            custom_cost_values=self._merge_text_tuple(
                base_order.custom_cost_values,
                recognized_order.custom_cost_values,
            ),
            procurement_items=self._merge_procurement_items(
                base_order.procurement_items,
                recognized_order.procurement_items,
            ),
        )
        return merged_order, retained_existing_values

    @staticmethod
    def _prefer_recognized_text(existing_value: str, recognized_value: str) -> str:
        recognized_text = str(recognized_value or "").strip()
        if recognized_text:
            return recognized_text
        return str(existing_value or "").strip()

    def _merge_text_tuple(
        self,
        existing_values: tuple[str, str, str],
        recognized_values: tuple[str, str, str],
    ) -> tuple[str, str, str]:
        merged: list[str] = []
        for index in range(3):
            existing_text = existing_values[index] if index < len(existing_values) else ""
            recognized_text = recognized_values[index] if index < len(recognized_values) else ""
            merged.append(self._prefer_recognized_text(existing_text, recognized_text))
        return tuple(merged)

    def _merge_procurement_items(
        self,
        existing_items: tuple[ProcurementItem, ProcurementItem, ProcurementItem],
        recognized_items: tuple[ProcurementItem, ProcurementItem, ProcurementItem],
    ) -> tuple[ProcurementItem, ProcurementItem, ProcurementItem]:
        merged: list[ProcurementItem] = []
        for index in range(3):
            existing_item = existing_items[index] if index < len(existing_items) else ProcurementItem("", "", "", "", "")
            recognized_item = recognized_items[index] if index < len(recognized_items) else ProcurementItem("", "", "", "", "")
            merged.append(
                ProcurementItem(
                    product_name=self._prefer_recognized_text(existing_item.product_name, recognized_item.product_name),
                    quantity=self._prefer_recognized_text(existing_item.quantity, recognized_item.quantity),
                    cost=self._prefer_recognized_text(existing_item.cost, recognized_item.cost),
                    tracking_number=self._prefer_recognized_text(
                        existing_item.tracking_number,
                        recognized_item.tracking_number,
                    ),
                    jd_link=self._prefer_recognized_text(existing_item.jd_link, recognized_item.jd_link),
                )
            )
        return tuple(merged)

    def _has_retained_existing_values(self, base_order: ParsedOrder, recognized_order: ParsedOrder) -> bool:
        comparable_pairs = (
            (base_order.order_id, recognized_order.order_id),
            (base_order.placed_at, recognized_order.placed_at),
            (base_order.order_status, recognized_order.order_status),
            (base_order.product_name, recognized_order.product_name),
            (base_order.specification, recognized_order.specification),
            (base_order.quantity, recognized_order.quantity),
            (base_order.order_amount, recognized_order.order_amount),
            (base_order.income_amount, recognized_order.income_amount),
            (base_order.recipient_name, recognized_order.recipient_name),
            (base_order.phone_number, recognized_order.phone_number),
            (base_order.code, recognized_order.code),
            (base_order.address, recognized_order.address),
            (base_order.delivery_note, recognized_order.delivery_note),
        )
        for existing_value, recognized_value in comparable_pairs:
            if str(existing_value or "").strip() and not str(recognized_value or "").strip():
                return True
        return any(
            str(existing_item_field or "").strip() and not str(recognized_item_field or "").strip()
            for existing_item, recognized_item in zip(base_order.procurement_items, recognized_order.procurement_items)
            for existing_item_field, recognized_item_field in (
                (existing_item.product_name, recognized_item.product_name),
                (existing_item.quantity, recognized_item.quantity),
                (existing_item.cost, recognized_item.cost),
                (existing_item.tracking_number, recognized_item.tracking_number),
                (existing_item.jd_link, recognized_item.jd_link),
            )
        )
