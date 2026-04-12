from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
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
        self.save_history_button.setEnabled(False)
        self.submit_button.setEnabled(False)

        shop_row = QHBoxLayout()
        shop_label = QLabel("店铺")
        shop_label.setObjectName("OrderFieldLabel")
        shop_row.addWidget(shop_label)
        shop_row.addWidget(self.shop_selector, 1)

        button_row = QHBoxLayout()
        button_row.addWidget(self.save_history_button)
        button_row.addWidget(self.submit_button)

        left_column = QVBoxLayout()
        left_column.addLayout(shop_row)
        left_column.addWidget(self.capture_widget)
        left_column.addWidget(self.order_card_widget)
        left_column.addLayout(button_row)

        right_column = QVBoxLayout()
        right_column.addWidget(self.address_widget)

        content = QWidget()
        content.setObjectName("PageContent")
        content_layout = QHBoxLayout(content)
        content_layout.addLayout(left_column, 3)
        content_layout.addLayout(right_column, 2)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll_area.setWidget(content)

        layout = QVBoxLayout(self)
        layout.addWidget(scroll_area)
        self.submit_button.clicked.connect(self._handle_submit)
        self.save_history_button.clicked.connect(self._handle_save_history)
        self.capture_widget.image_ready.connect(self.process_image_bytes)

    def show_order(self, order) -> None:
        self._current_order = order
        self.order_card_widget.load_order(order)
        self.address_widget.load_from_order(order)
        self.save_history_button.setEnabled(True)
        self.submit_button.setEnabled(True)

    def set_product_presets(self, product_presets: list[dict[str, str]]) -> None:
        self.order_card_widget.set_product_presets(product_presets)

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
            "order": self.order_card_widget.to_order(),
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
