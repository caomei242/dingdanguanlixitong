from __future__ import annotations

from dataclasses import replace
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
from strawberry_order_management.ui.widgets.order_card_widget import OrderCardWidget
from strawberry_order_management.ui.widgets.screenshot_input_widget import (
    ScreenshotInputWidget,
)


class _ImageWorker(QObject):
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, callback: Callable[[bytes], object], image_bytes: bytes):
        super().__init__()
        self._callback = callback
        self._image_bytes = image_bytes

    def run(self) -> None:
        try:
            result = self._callback(self._image_bytes)
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.finished.emit(result)


class IntakePage(QWidget):
    submit_requested = Signal(object)
    save_history_requested = Signal(object)
    product_library_requested = Signal(str, str)
    procurement_template_requested = Signal(object)
    PLATFORM_OPTIONS = ("抖店", "微信小店")

    def __init__(
        self,
        on_submit: Callable[[object], None] | None = None,
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
        self._on_submit = on_submit
        self._on_save_history = on_save_history
        self._on_process_image = on_process_image
        self._use_background_thread = use_background_thread
        self._current_order = None
        self._current_source_label = ""
        self._thread = None
        self._worker = None
        self.shop_selector.setPlaceholderText("请选择店铺")
        self.platform_selector.addItems(list(self.PLATFORM_OPTIONS))
        self.platform_selector.setCurrentText("抖店")
        self.save_history_button.setEnabled(False)
        self.submit_button.setEnabled(False)
        extractor_input_panel, extractor_results_panel = self.address_widget.take_workspace_panels()

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

        left_column = QWidget()
        left_column.setObjectName("EntryLeftRail")
        left_column.setFixedWidth(312)
        left_column_layout = QVBoxLayout(left_column)
        left_column_layout.setContentsMargins(0, 0, 0, 0)
        left_column_layout.setSpacing(14)

        capture_card = QFrame()
        capture_card.setObjectName("EntryCaptureCard")
        capture_layout = QVBoxLayout(capture_card)
        capture_layout.setContentsMargins(16, 14, 16, 16)
        capture_layout.setSpacing(10)
        capture_layout.addWidget(self.capture_widget)

        extractor_input_card = QFrame()
        extractor_input_card.setObjectName("EntryExtractorInputCard")
        extractor_input_layout = QVBoxLayout(extractor_input_card)
        extractor_input_layout.setContentsMargins(16, 14, 16, 16)
        extractor_input_layout.setSpacing(10)
        extractor_input_layout.addWidget(extractor_input_panel)

        left_column_layout.addWidget(capture_card)
        left_column_layout.addWidget(extractor_input_card, 1)

        center_scroll = QScrollArea()
        center_scroll.setObjectName("EntryFormRail")
        center_scroll.setWidgetResizable(True)
        center_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        center_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        center_scroll.setWidget(self.order_card_widget)

        right_column = QWidget()
        right_column.setObjectName("EntryRightRail")
        right_column.setFixedWidth(312)
        right_column_layout = QVBoxLayout(right_column)
        right_column_layout.setContentsMargins(0, 0, 0, 0)
        right_column_layout.setSpacing(14)
        support_card = QFrame()
        support_card.setObjectName("EntryExtractorResultCard")
        support_layout = QVBoxLayout(support_card)
        support_layout.setContentsMargins(16, 14, 16, 16)
        support_layout.setSpacing(0)
        support_layout.addWidget(extractor_results_panel)
        right_column_layout.addWidget(support_card, 1)
        right_column_layout.addStretch(1)

        content = QWidget()
        content.setObjectName("PageContent")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(14)
        content_layout.addWidget(action_bar)

        workspace = QWidget()
        workspace_layout = QHBoxLayout(workspace)
        workspace_layout.setContentsMargins(0, 0, 0, 0)
        workspace_layout.setSpacing(16)
        workspace_layout.addWidget(left_column, 0)
        workspace_layout.addWidget(center_scroll, 1)
        workspace_layout.addWidget(right_column, 0)
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
        self.save_history_button.clicked.connect(self._handle_save_history)
        self.capture_widget.image_ready.connect(self.process_image_bytes)
        self.order_card_widget.product_library_requested.connect(self.product_library_requested.emit)
        self.order_card_widget.procurement_template_requested.connect(self.procurement_template_requested.emit)

    def show_order(self, order) -> None:
        self._current_order = order
        self.order_card_widget.load_order(order)
        platform = getattr(order, "platform", "") or "抖店"
        if self.platform_selector.findText(platform) >= 0:
            self.platform_selector.setCurrentText(platform)
        self.address_widget.load_from_order(order)
        self.save_history_button.setEnabled(True)
        self.submit_button.setEnabled(True)
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
        self.capture_widget.status_label.setText(f"{source_label}识别中...")
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

    def _handle_save_history(self) -> None:
        payload = self._build_submission_payload()
        if payload is None:
            return
        self.save_history_requested.emit(payload)
        if self._on_save_history is not None:
            self._on_save_history(payload)

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

    def set_submit_in_progress(self, in_progress: bool) -> None:
        self.submit_button.setEnabled(not in_progress)
        self.submit_button.setText("写入中..." if in_progress else "确认写入飞书")

    def _run_sync(self, image_bytes: bytes) -> None:
        try:
            order = self._on_process_image(image_bytes)
        except Exception as exc:
            self.capture_widget.status_label.setText(str(exc))
            return
        self._handle_process_success(order)

    def _start_background_job(self, image_bytes: bytes) -> None:
        self._thread = QThread(self)
        self._worker = _ImageWorker(self._on_process_image, image_bytes)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._handle_process_success)
        self._worker.failed.connect(self._handle_process_failure)
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(self._clear_worker_refs)
        self._thread.start()

    def _handle_process_success(self, order) -> None:
        self.show_order(order)
        self.capture_widget.status_label.setText(f"已完成{self._current_source_label}识别")

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
