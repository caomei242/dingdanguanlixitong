from __future__ import annotations

from PySide6.QtWidgets import QFrame, QLabel, QListWidget, QScrollArea, QVBoxLayout, QWidget


class HistoryPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("HistoryPage")

        title = QLabel("历史")
        title.setObjectName("SectionTitle")
        subtitle = QLabel("查看最近识别、写入和失败记录")
        subtitle.setObjectName("MutedText")

        self.summary_label = QLabel("暂无记录")
        self.summary_label.setObjectName("MutedText")

        self.list_widget = QListWidget()
        self.list_widget.setObjectName("HistoryList")

        card = QFrame()
        card.setObjectName("CardFrame")
        card_layout = QVBoxLayout(card)
        card_layout.addWidget(self.summary_label)
        card_layout.addWidget(self.list_widget)

        content = QWidget()
        content.setObjectName("PageContent")
        content_layout = QVBoxLayout(content)
        content_layout.addWidget(title)
        content_layout.addWidget(subtitle)
        content_layout.addWidget(card)
        content_layout.addStretch(1)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll_area.setWidget(content)

        root = QVBoxLayout(self)
        root.addWidget(scroll_area)

    def load_rows(self, rows: list[dict]) -> None:
        self.list_widget.clear()
        self.summary_label.setText(f"共 {len(rows)} 条记录")
        if not rows:
            self.list_widget.addItem("暂无历史记录")
            return

        for row in rows:
            shop_name = self._display_value(row.get("shop_name"))
            recipient = self._display_value(row.get("recipient_name"))
            status = self._display_value(row.get("status"))
            order_id = self._display_value(row.get("order_id"))
            self.list_widget.addItem(f"{shop_name} · {recipient} · {status} · {order_id}")

    @staticmethod
    def _display_value(value) -> str:
        if value is None:
            return "-"
        text = str(value).strip()
        return text if text else "-"
