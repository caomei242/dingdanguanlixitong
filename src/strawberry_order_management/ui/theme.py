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
QFrame#CardFrame {
    background: rgba(255, 255, 255, 0.96);
    border: 1px solid #e3e9f4;
    border-radius: 24px;
}

QLabel#BrandTitle {
    color: #ff4b6e;
    font-size: 30px;
    font-weight: 800;
}

QLabel#BrandSubtitle {
    color: #7e8aa5;
    font-size: 13px;
}

QListWidget {
    background: #ffffff;
    border: 1px solid #dbe4f2;
    border-radius: 18px;
    padding: 8px;
    outline: none;
}

QListWidget::item {
    padding: 14px 16px;
    margin: 4px 0;
    border-radius: 12px;
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
    padding: 10px 16px;
    font-weight: 600;
}

QPushButton:hover {
    background: #3d70f0;
}

QPushButton:disabled {
    background: #c9d4ea;
    color: #f7f9fd;
}

QLineEdit, QTextEdit, QComboBox {
    background: #ffffff;
    border: 1px solid #d9e2f1;
    border-radius: 12px;
    padding: 10px 12px;
    selection-background-color: #4a7cff;
}

QTextEdit {
    min-height: 84px;
}

QComboBox {
    padding-right: 28px;
}

QLabel#SectionTitle {
    font-size: 18px;
    font-weight: 700;
    color: #1f2b44;
}

QLabel#MutedText {
    color: #74829a;
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
