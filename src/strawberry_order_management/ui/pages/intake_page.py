from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from strawberry_order_management.ui.widgets.address_extractor_widget import (
    AddressExtractorWidget,
)
from strawberry_order_management.ui.widgets.order_card_widget import OrderCardWidget
from strawberry_order_management.ui.widgets.screenshot_input_widget import (
    ScreenshotInputWidget,
)


class IntakePage(QWidget):
    submit_requested = Signal(object)

    def __init__(
        self,
        on_submit: Callable[[object], None] | None = None,
        on_process_image: Callable[[bytes], object] | None = None,
    ) -> None:
        super().__init__()
        self.capture_widget = ScreenshotInputWidget()
        self.order_card_widget = OrderCardWidget()
        self.address_widget = AddressExtractorWidget()
        self.submit_button = QPushButton("确认写入飞书")
        self._on_submit = on_submit
        self._on_process_image = on_process_image
        self._current_order = None
        self.submit_button.setEnabled(False)

        left_column = QVBoxLayout()
        left_column.addWidget(self.capture_widget)
        left_column.addWidget(self.order_card_widget)
        left_column.addWidget(self.submit_button)

        right_column = QVBoxLayout()
        right_column.addWidget(self.address_widget)

        layout = QHBoxLayout(self)
        layout.addLayout(left_column, 3)
        layout.addLayout(right_column, 2)
        self.submit_button.clicked.connect(self._handle_submit)
        self.capture_widget.image_ready.connect(self.process_image_bytes)

    def show_order(self, order) -> None:
        self._current_order = order
        self.order_card_widget.load_order(order)
        self.address_widget.load_from_order(order)
        self.submit_button.setEnabled(True)

    def process_image_bytes(self, image_bytes: bytes, source_label: str) -> None:
        if self._on_process_image is None:
            self.capture_widget.status_label.setText("请先在设置页完成 API 配置")
            return
        try:
            order = self._on_process_image(image_bytes)
        except Exception as exc:
            self.capture_widget.status_label.setText(str(exc))
            return

        self.show_order(order)
        self.capture_widget.status_label.setText(f"已完成{source_label}识别")

    def _handle_submit(self) -> None:
        if self._current_order is None:
            return
        self.submit_requested.emit(self._current_order)
        if self._on_submit is not None:
            self._on_submit(self._current_order)
