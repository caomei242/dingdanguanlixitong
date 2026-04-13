from __future__ import annotations

APP_STYLESHEET = """
QWidget {
    color: #20304a;
    font-family: "PingFang SC", "Microsoft YaHei", "Noto Sans SC", "Segoe UI", sans-serif;
    font-size: 14px;
}

QMainWindow {
    background: #f6f8fc;
}

QScrollArea {
    background: transparent;
    border: none;
}

QWidget#PageContent {
    background: #f6f8fc;
}

QFrame#ShellFrame,
QFrame#CardFrame,
QFrame#OrderSummaryCard,
QFrame#OrderShippingCard,
QFrame#ProcurementSectionCard,
QFrame#ProcurementRowCard,
QFrame#IntakeSupportCard {
    background: rgba(255, 255, 255, 0.96);
    border: 1px solid #e3e9f4;
    border-radius: 24px;
}

QFrame#HistoryListCard,
QFrame#HistoryDetailCard,
QFrame#HistoryActionCard,
QFrame#HistorySummaryCard,
QFrame#HistoryStatCard,
QFrame#HistoryMiniSummaryCard {
    background: rgba(255, 255, 255, 0.98);
    border: 1px solid #dbe4f2;
    border-radius: 22px;
}

QLabel#BrandTitle {
    color: #ff4b6e;
    font-size: 24px;
    font-weight: 800;
}

QLabel#BrandSubtitle {
    color: #7e8aa5;
    font-size: 12px;
}

QListWidget {
    background: #ffffff;
    border: 1px solid #dbe4f2;
    border-radius: 18px;
    padding: 8px;
    outline: none;
}

QListWidget#HistoryList {
    min-height: 360px;
}

QListWidget::item {
    padding: 11px 13px;
    margin: 3px 0;
    border-radius: 14px;
}

QListWidget::item:selected {
    background: #4a7cff;
    color: #ffffff;
}

QPushButton {
    background: #4a7cff;
    color: white;
    border: none;
    border-radius: 14px;
    padding: 8px 12px;
    font-weight: 600;
}

QPushButton:hover {
    background: #3d70f0;
}

QPushButton:disabled {
    background: #c9d4ea;
    color: #f7f9fd;
}

QPushButton#SecondaryActionButton {
    background: #eef4ff;
    color: #3f67d9;
    border: 1px solid #cddcff;
}

QPushButton#SecondaryActionButton:hover {
    background: #e3ecff;
}

QPushButton#DangerActionButton {
    background: #fff0f2;
    color: #d6455d;
    border: 1px solid #f2c3cb;
}

QPushButton#DangerActionButton:hover {
    background: #ffe3e8;
}

QLineEdit, QTextEdit, QComboBox {
    background: #ffffff;
    border: 1px solid #d9e2f1;
    border-radius: 10px;
    padding: 7px 10px;
    selection-background-color: #4a7cff;
}

QTextEdit {
    min-height: 60px;
}

QComboBox {
    padding-right: 28px;
}

QLabel#SectionTitle {
    font-size: 16px;
    font-weight: 700;
    color: #1f2b44;
}

QTabWidget::pane {
    border: none;
    background: transparent;
}

QTabBar::tab {
    background: #edf2ff;
    color: #5a6f96;
    border: 1px solid #d9e2f4;
    border-bottom: none;
    padding: 10px 18px;
    margin-right: 8px;
    border-top-left-radius: 14px;
    border-top-right-radius: 14px;
    font-weight: 600;
}

QTabBar::tab:selected {
    background: #ffffff;
    color: #1f2b44;
}

QLabel#MutedText {
    color: #74829a;
}

QLabel#HistoryDetailTitle {
    font-size: 20px;
    font-weight: 800;
    color: #1c2740;
}

QLabel#HistoryDetailMeta {
    color: #6f7f99;
}

QTextEdit#HistoryDetailValue {
    color: #17253d;
    background: #fcfdff;
    border: 1px solid #dbe4f4;
    border-radius: 14px;
}

QLabel#HistoryStatTitle,
QLabel#HistoryMiniSummaryTitle {
    color: #7a89a6;
    font-size: 12px;
    font-weight: 600;
}

QLabel#HistoryStatValue {
    color: #1b2a45;
    font-size: 22px;
    font-weight: 800;
}

QLabel#HistoryMiniSummaryValue {
    color: #1b2a45;
    font-size: 14px;
    font-weight: 700;
}

QLabel#OrderFieldLabel {
    color: #7c8aa6;
    font-weight: 600;
}

QLineEdit#OrderValueEdit,
QTextEdit#OrderValueEdit {
    color: #17253d;
    background: #fcfdff;
    border: 1px solid #dbe4f4;
}

QTextEdit#HighlightedValueEdit {
    color: #15233d;
    background: #f7faff;
    border: 1px solid #c7d7ff;
}
"""


def apply_theme(widget) -> None:
    widget.setStyleSheet(APP_STYLESHEET)
