from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from strawberry_order_management.ui.widgets.address_extractor_widget import (
    AddressExtractorWidget,
)
from strawberry_order_management.ui.widgets.order_card_widget import OrderCardWidget


class IntakePage(QWidget):
    submit_requested = Signal(object)

    def __init__(self, on_submit: Callable[[object], None] | None = None) -> None:
        super().__init__()
        self.order_card_widget = OrderCardWidget()
        self.address_widget = AddressExtractorWidget()
        self.submit_button = QPushButton("确认写入飞书")
        self._on_submit = on_submit
        self._current_order = None

        left_column = QVBoxLayout()
        left_column.addWidget(self.order_card_widget)
        left_column.addWidget(self.submit_button)

        right_column = QVBoxLayout()
        right_column.addWidget(self.address_widget)

        layout = QHBoxLayout(self)
        layout.addLayout(left_column, 3)
        layout.addLayout(right_column, 2)
        self.submit_button.clicked.connect(self._handle_submit)

    def show_order(self, order) -> None:
        self._current_order = order
        self.order_card_widget.load_order(order)

    def _handle_submit(self) -> None:
        if self._current_order is None:
            return
        self.submit_requested.emit(self._current_order)
        if self._on_submit is not None:
            self._on_submit(self._current_order)
