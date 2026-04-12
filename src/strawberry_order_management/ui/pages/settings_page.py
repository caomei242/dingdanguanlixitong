from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


class SettingsPage(QWidget):
    save_requested = Signal(object)

    def __init__(self, on_resolve_shop_link=None) -> None:
        super().__init__()
        self.setObjectName("SettingsPage")

        self.ocr_use_mcp_checkbox = QCheckBox("启用 MiniMax MCP OCR")
        self.ocr_mcp_command_edit = QLineEdit()
        self.ocr_base_url_edit = QLineEdit()
        self.ocr_api_key_edit = QLineEdit()
        self.helper_base_url_edit = QLineEdit()
        self.helper_api_key_edit = QLineEdit()
        self.feishu_app_id_edit = QLineEdit()
        self.feishu_app_secret_edit = QLineEdit()
        self.shop_selector = QComboBox()
        self.shop_name_edit = QLineEdit()
        self.shop_wiki_url_edit = QLineEdit()
        self.shop_app_token_edit = QLineEdit()
        self.shop_table_id_edit = QLineEdit()
        self.shop_table_name_edit = QLineEdit()
        self.add_shop_button = QPushButton("新增店铺")
        self.save_shop_button = QPushButton("保存店铺")
        self.remove_shop_button = QPushButton("删除店铺")
        self.save_button = QPushButton("保存/应用")
        self.status_label = QLabel("")
        self.status_label.setObjectName("MutedText")
        self._on_resolve_shop_link = on_resolve_shop_link
        self.ocr_mcp_command_edit.setText("uvx minimax-coding-plan-mcp -y")
        self._shops: list[dict[str, str]] = []

        header = QVBoxLayout()
        title = QLabel("设置")
        title.setObjectName("SectionTitle")
        subtitle = QLabel("配置 OCR、辅助提取和飞书写入参数")
        subtitle.setObjectName("MutedText")
        header.addWidget(title)
        header.addWidget(subtitle)

        form = QFormLayout()
        form.addRow("使用 MCP OCR", self.ocr_use_mcp_checkbox)
        form.addRow("MCP 命令", self.ocr_mcp_command_edit)
        form.addRow("OCR API Base URL", self.ocr_base_url_edit)
        form.addRow("OCR API Key", self.ocr_api_key_edit)
        form.addRow("辅助提取 API Base URL", self.helper_base_url_edit)
        form.addRow("辅助提取 API Key", self.helper_api_key_edit)
        form.addRow("飞书 App ID", self.feishu_app_id_edit)
        form.addRow("飞书 App Secret", self.feishu_app_secret_edit)

        shop_button_row = QHBoxLayout()
        shop_button_row.addWidget(self.add_shop_button)
        shop_button_row.addWidget(self.save_shop_button)
        shop_button_row.addWidget(self.remove_shop_button)

        shop_form = QFormLayout()
        shop_form.addRow("已保存店铺", self.shop_selector)
        shop_form.addRow("店铺名称", self.shop_name_edit)
        shop_form.addRow("飞书表链接", self.shop_wiki_url_edit)
        shop_form.addRow("飞书 App Token", self.shop_app_token_edit)
        shop_form.addRow("飞书 Table ID", self.shop_table_id_edit)
        shop_form.addRow("表名备注", self.shop_table_name_edit)

        card = QFrame()
        card.setObjectName("CardFrame")
        card_layout = QVBoxLayout(card)
        card_layout.addLayout(form)
        card_layout.addWidget(QLabel("店铺与 Sheet 映射"))
        card_layout.addLayout(shop_button_row)
        card_layout.addLayout(shop_form)
        card_layout.addWidget(self.status_label)
        card_layout.addWidget(self.save_button)

        content = QWidget()
        content.setObjectName("PageContent")
        content_layout = QVBoxLayout(content)
        content_layout.addLayout(header)
        content_layout.addWidget(card)
        content_layout.addStretch(1)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll_area.setWidget(content)

        root = QVBoxLayout(self)
        root.addWidget(scroll_area)
        self.save_button.clicked.connect(self._emit_save_requested)
        self.add_shop_button.clicked.connect(self._handle_add_shop)
        self.save_shop_button.clicked.connect(self._handle_save_shop)
        self.remove_shop_button.clicked.connect(self._handle_remove_shop)
        self.shop_selector.currentIndexChanged.connect(self._load_selected_shop)

    def to_payload(self) -> dict:
        return {
            "ocr_use_mcp": self.ocr_use_mcp_checkbox.isChecked(),
            "ocr_mcp_command": self.ocr_mcp_command_edit.text().strip(),
            "ocr_base_url": self.ocr_base_url_edit.text().strip(),
            "ocr_api_key": self.ocr_api_key_edit.text().strip(),
            "helper_base_url": self.helper_base_url_edit.text().strip(),
            "helper_api_key": self.helper_api_key_edit.text().strip(),
            "feishu_app_id": self.feishu_app_id_edit.text().strip(),
            "feishu_app_secret": self.feishu_app_secret_edit.text().strip(),
            "shops": [dict(shop) for shop in self._shops],
            "selected_shop_name": self.shop_selector.currentText().strip(),
        }

    def load_payload(self, payload: dict) -> None:
        self.ocr_use_mcp_checkbox.setChecked(bool(payload.get("ocr_use_mcp")))
        self.ocr_mcp_command_edit.setText(
            self._clean_text(payload.get("ocr_mcp_command"))
            or "uvx minimax-coding-plan-mcp -y"
        )
        self.ocr_base_url_edit.setText(self._clean_text(payload.get("ocr_base_url")))
        self.ocr_api_key_edit.setText(self._clean_text(payload.get("ocr_api_key")))
        self.helper_base_url_edit.setText(self._clean_text(payload.get("helper_base_url")))
        self.helper_api_key_edit.setText(self._clean_text(payload.get("helper_api_key")))
        self.feishu_app_id_edit.setText(self._clean_text(payload.get("feishu_app_id")))
        self.feishu_app_secret_edit.setText(self._clean_text(payload.get("feishu_app_secret")))
        self._shops = [
            {
                "name": self._clean_text(shop.get("name")),
                "wiki_url": self._clean_text(shop.get("wiki_url")),
                "app_token": self._clean_text(shop.get("app_token")),
                "table_id": self._clean_text(shop.get("table_id")),
                "table_name": self._clean_text(shop.get("table_name")),
            }
            for shop in payload.get("shops", [])
            if isinstance(shop, dict) and self._clean_text(shop.get("name"))
        ]
        self._refresh_shop_selector(self._clean_text(payload.get("selected_shop_name")))

    def _emit_save_requested(self) -> None:
        self.save_requested.emit(self.to_payload())

    def _handle_add_shop(self) -> None:
        self.shop_name_edit.clear()
        self.shop_wiki_url_edit.clear()
        self.shop_app_token_edit.clear()
        self.shop_table_id_edit.clear()
        self.shop_table_name_edit.clear()
        self.shop_name_edit.setFocus()
        self.status_label.setText("")

    def _handle_save_shop(self) -> None:
        shop = {
            "name": self.shop_name_edit.text().strip(),
            "wiki_url": self.shop_wiki_url_edit.text().strip(),
            "app_token": self.shop_app_token_edit.text().strip(),
            "table_id": self.shop_table_id_edit.text().strip(),
            "table_name": self.shop_table_name_edit.text().strip(),
        }
        if not shop["name"]:
            return
        if shop["wiki_url"] and self._on_resolve_shop_link is not None:
            try:
                resolved = self._on_resolve_shop_link(shop["wiki_url"])
            except Exception as exc:
                self.status_label.setText(str(exc))
                return
            shop["app_token"] = str(resolved.get("app_token", "")).strip()
            shop["table_id"] = str(resolved.get("table_id", "")).strip()
            self.shop_app_token_edit.setText(shop["app_token"])
            self.shop_table_id_edit.setText(shop["table_id"])
            self.status_label.setText("已从飞书链接解析表格信息")
        else:
            self.status_label.setText("")

        for index, existing in enumerate(self._shops):
            if existing["name"] == shop["name"]:
                self._shops[index] = shop
                break
        else:
            self._shops.append(shop)

        self._refresh_shop_selector(shop["name"])

    def _handle_remove_shop(self) -> None:
        selected_name = self.shop_selector.currentText().strip()
        if not selected_name:
            return
        self._shops = [shop for shop in self._shops if shop["name"] != selected_name]
        self._refresh_shop_selector()

    def _refresh_shop_selector(self, selected_name: str | None = None) -> None:
        self.shop_selector.blockSignals(True)
        self.shop_selector.clear()
        self.shop_selector.addItems([shop["name"] for shop in self._shops])
        if selected_name:
            index = self.shop_selector.findText(selected_name)
            if index >= 0:
                self.shop_selector.setCurrentIndex(index)
        self.shop_selector.blockSignals(False)
        self._load_selected_shop()

    def _load_selected_shop(self) -> None:
        selected_name = self.shop_selector.currentText().strip()
        for shop in self._shops:
            if shop["name"] == selected_name:
                self.shop_name_edit.setText(shop["name"])
                self.shop_wiki_url_edit.setText(shop.get("wiki_url", ""))
                self.shop_app_token_edit.setText(shop["app_token"])
                self.shop_table_id_edit.setText(shop["table_id"])
                self.shop_table_name_edit.setText(shop["table_name"])
                return
        if not selected_name:
            self.shop_name_edit.clear()
            self.shop_wiki_url_edit.clear()
            self.shop_app_token_edit.clear()
            self.shop_table_id_edit.clear()
            self.shop_table_name_edit.clear()

    @staticmethod
    def _clean_text(value) -> str:
        if value is None:
            return ""
        return str(value).strip()
