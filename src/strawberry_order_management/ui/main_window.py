from __future__ import annotations

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

from strawberry_order_management.ui.pages.history_page import HistoryPage
from strawberry_order_management.ui.pages.intake_page import IntakePage
from strawberry_order_management.ui.pages.settings_page import SettingsPage
from strawberry_order_management.ui.theme import apply_theme


class MainWindow(QMainWindow):
    def __init__(self, on_settings_save=None) -> None:
        super().__init__()
        self.setWindowTitle("草莓订单管理系统")
        self._on_settings_save = on_settings_save

        self.nav = QListWidget()
        self.nav.addItems(["订单录入", "历史", "设置"])
        self.nav.setFixedWidth(180)

        self.stack = QStackedWidget()
        self.intake_page = IntakePage()
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

        apply_theme(self)

    def _handle_settings_save(self, payload: dict) -> None:
        if self._on_settings_save is not None:
            self._on_settings_save(payload)
