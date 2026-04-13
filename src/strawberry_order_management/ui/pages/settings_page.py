from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)


class SettingsPage(QWidget):
    save_requested = Signal(object)
    FIELD_MAPPING_KEYS = (
        "备注",
        "订单日期",
        "下单时间",
        "订单状态",
        "收入",
        "发货地址",
        "价格",
        "采购商品1",
        "采购数量1",
        "采购成本1",
        "采购商品2",
        "采购数量2",
        "采购成本2",
        "采购商品3",
        "采购数量3",
        "采购成本3",
    )
    FIELD_MAPPING_ALIASES = {
        "remark": "备注",
        "order_date": "订单日期",
        "order_time": "下单时间",
        "order_status": "订单状态",
        "income": "收入",
        "shipping_address": "发货地址",
        "price": "价格",
        "purchase_item_1": "采购商品1",
        "purchase_quantity_1": "采购数量1",
        "purchase_cost_1": "采购成本1",
        "purchase_item_2": "采购商品2",
        "purchase_quantity_2": "采购数量2",
        "purchase_cost_2": "采购成本2",
        "purchase_item_3": "采购商品3",
        "purchase_quantity_3": "采购数量3",
        "purchase_cost_3": "采购成本3",
    }

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
        self.product_selector = QComboBox()
        self.product_name_edit = QLineEdit()
        self.product_cost_edit = QLineEdit()
        self.product_default_cost_edit = self.product_cost_edit
        self.add_product_button = QPushButton("新增商品")
        self.save_product_button = QPushButton("保存商品")
        self.remove_product_button = QPushButton("删除商品")
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
        self._product_presets: list[dict[str, str]] = []
        self._shops: list[dict[str, str]] = []
        self.mapping_edits: dict[str, QLineEdit] = {
            key: QLineEdit() for key in self.FIELD_MAPPING_KEYS
        }
        self.shop_mapping_edits: dict[str, QLineEdit] = {
            alias: self.mapping_edits[key]
            for alias, key in self.FIELD_MAPPING_ALIASES.items()
        }

        header = QVBoxLayout()
        title = QLabel("设置")
        title.setObjectName("SectionTitle")
        subtitle = QLabel("配置 OCR、辅助提取和飞书写入参数")
        subtitle.setObjectName("MutedText")
        header.addWidget(title)
        header.addWidget(subtitle)

        api_form = QFormLayout()
        api_form.addRow("使用 MCP OCR", self.ocr_use_mcp_checkbox)
        api_form.addRow("MCP 命令", self.ocr_mcp_command_edit)
        api_form.addRow("OCR API Base URL", self.ocr_base_url_edit)
        api_form.addRow("OCR API Key", self.ocr_api_key_edit)
        api_form.addRow("辅助提取 API Base URL", self.helper_base_url_edit)
        api_form.addRow("辅助提取 API Key", self.helper_api_key_edit)
        api_form.addRow("飞书 App ID", self.feishu_app_id_edit)
        api_form.addRow("飞书 App Secret", self.feishu_app_secret_edit)

        product_button_row = QHBoxLayout()
        product_button_row.addWidget(self.add_product_button)
        product_button_row.addWidget(self.save_product_button)
        product_button_row.addWidget(self.remove_product_button)

        product_form = QFormLayout()
        product_form.addRow("已保存商品", self.product_selector)
        product_form.addRow("商品名称", self.product_name_edit)
        product_form.addRow("默认成本", self.product_cost_edit)

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
        mapping_grid = QGridLayout()
        mapping_grid.setHorizontalSpacing(16)
        mapping_grid.setVerticalSpacing(10)
        for index, key in enumerate(self.FIELD_MAPPING_KEYS):
            row = index // 2
            column = (index % 2) * 2
            mapping_grid.addWidget(QLabel(f"{key} 映射"), row, column)
            mapping_grid.addWidget(self.mapping_edits[key], row, column + 1)

        self.tabs = QTabWidget()
        self.tabs.setObjectName("SettingsTabs")
        self.tabs.addTab(self._build_tab_card("接口配置", api_form), "接口配置")
        self.tabs.addTab(
            self._build_tab_card("全局商品库", product_form, product_button_row),
            "商品库",
        )
        self.tabs.addTab(
            self._build_tab_card("店铺与 Sheet 映射", shop_form, shop_button_row, mapping_grid),
            "店铺映射",
        )

        content = QWidget()
        content.setObjectName("PageContent")
        content_layout = QVBoxLayout(content)
        content_layout.addLayout(header)
        content_layout.addWidget(self.tabs)
        content_layout.addWidget(self.status_label)
        content_layout.addWidget(self.save_button)
        content_layout.addStretch(1)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll_area.setWidget(content)

        root = QVBoxLayout(self)
        root.addWidget(scroll_area)
        self.save_button.clicked.connect(self._emit_save_requested)
        self.add_product_button.clicked.connect(self._handle_add_product)
        self.save_product_button.clicked.connect(self._handle_save_product)
        self.remove_product_button.clicked.connect(self._handle_remove_product)
        self.add_shop_button.clicked.connect(self._handle_add_shop)
        self.save_shop_button.clicked.connect(self._handle_save_shop)
        self.remove_shop_button.clicked.connect(self._handle_remove_shop)
        self.product_selector.currentIndexChanged.connect(self._load_selected_product)
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
            "product_presets": [dict(item) for item in self._product_presets],
            "global_product_library": [dict(item) for item in self._product_presets],
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
        product_presets = payload.get("product_presets")
        if not product_presets:
            product_presets = payload.get("global_product_library", [])
        self._product_presets = [
            {
                "name": self._clean_text(item.get("name")),
                "default_cost": self._clean_text(item.get("default_cost")),
            }
            for item in product_presets
            if isinstance(item, dict) and self._clean_text(item.get("name"))
        ]
        self._shops = [
            {
                "name": self._clean_text(shop.get("name")),
                "wiki_url": self._clean_text(shop.get("wiki_url")),
                "app_token": self._clean_text(shop.get("app_token")),
                "table_id": self._clean_text(shop.get("table_id")),
                "table_name": self._clean_text(shop.get("table_name")),
                "field_mapping": self._clean_field_mapping(shop.get("field_mapping")),
            }
            for shop in payload.get("shops", [])
            if isinstance(shop, dict) and self._clean_text(shop.get("name"))
        ]
        self._refresh_product_selector()
        self._refresh_shop_selector(self._clean_text(payload.get("selected_shop_name")))

    def _emit_save_requested(self) -> None:
        self.save_requested.emit(self.to_payload())

    def _handle_add_product(self) -> None:
        self.product_name_edit.clear()
        self.product_cost_edit.clear()
        self.product_name_edit.setFocus()
        self.status_label.setText("")

    def _handle_save_product(self) -> None:
        if not self.upsert_product_preset(
            self.product_name_edit.text().strip(),
            self.product_cost_edit.text().strip(),
        ):
            self.status_label.setText("请先填写商品名称")
            return
        self.status_label.setText("已保存商品预设")

    def _handle_remove_product(self) -> None:
        selected_name = self.product_selector.currentText().strip()
        if not selected_name:
            return
        self._product_presets = [
            product for product in self._product_presets if product["name"] != selected_name
        ]
        self._refresh_product_selector()
        self.status_label.setText("已删除商品预设")

    def _handle_add_shop(self) -> None:
        self.shop_name_edit.clear()
        self.shop_wiki_url_edit.clear()
        self.shop_app_token_edit.clear()
        self.shop_table_id_edit.clear()
        self.shop_table_name_edit.clear()
        for edit in self.mapping_edits.values():
            edit.clear()
        self.shop_name_edit.setFocus()
        self.status_label.setText("")

    def _handle_save_shop(self) -> None:
        shop = {
            "name": self.shop_name_edit.text().strip(),
            "wiki_url": self.shop_wiki_url_edit.text().strip(),
            "app_token": self.shop_app_token_edit.text().strip(),
            "table_id": self.shop_table_id_edit.text().strip(),
            "table_name": self.shop_table_name_edit.text().strip(),
            "field_mapping": self._current_field_mapping(),
        }
        if not shop["name"]:
            self.status_label.setText("请先填写店铺名称")
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

    def upsert_product_preset(self, name: str, default_cost: str) -> bool:
        product = {
            "name": name.strip(),
            "default_cost": default_cost.strip(),
        }
        if not product["name"]:
            return False

        for index, existing in enumerate(self._product_presets):
            if existing["name"] == product["name"]:
                if existing == product:
                    self._refresh_product_selector(product["name"])
                    return False
                self._product_presets[index] = product
                self._refresh_product_selector(product["name"])
                return True
        else:
            self._product_presets.append(product)
        self._refresh_product_selector(product["name"])
        return True

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

    def _refresh_product_selector(self, selected_name: str | None = None) -> None:
        self.product_selector.blockSignals(True)
        self.product_selector.clear()
        self.product_selector.addItems([item["name"] for item in self._product_presets])
        if selected_name:
            index = self.product_selector.findText(selected_name)
            if index >= 0:
                self.product_selector.setCurrentIndex(index)
        self.product_selector.blockSignals(False)
        self._load_selected_product()

    def _load_selected_product(self) -> None:
        selected_name = self.product_selector.currentText().strip()
        for item in self._product_presets:
            if item["name"] == selected_name:
                self.product_name_edit.setText(item["name"])
                self.product_cost_edit.setText(item["default_cost"])
                return
        if not selected_name:
            self.product_name_edit.clear()
            self.product_cost_edit.clear()

    def _load_selected_shop(self) -> None:
        selected_name = self.shop_selector.currentText().strip()
        for shop in self._shops:
            if shop["name"] == selected_name:
                self.shop_name_edit.setText(shop["name"])
                self.shop_wiki_url_edit.setText(shop.get("wiki_url", ""))
                self.shop_app_token_edit.setText(shop["app_token"])
                self.shop_table_id_edit.setText(shop["table_id"])
                self.shop_table_name_edit.setText(shop["table_name"])
                self._load_field_mapping(shop.get("field_mapping"))
                return
        if not selected_name:
            self.shop_name_edit.clear()
            self.shop_wiki_url_edit.clear()
            self.shop_app_token_edit.clear()
            self.shop_table_id_edit.clear()
            self.shop_table_name_edit.clear()
            self._load_field_mapping({})

    @staticmethod
    def _build_tab_card(title: str, *layouts) -> QWidget:
        container = QFrame()
        container.setObjectName("CardFrame")
        layout = QVBoxLayout(container)
        section_title = QLabel(title)
        section_title.setObjectName("SectionTitle")
        layout.addWidget(section_title)
        for child in layouts:
            if child is None:
                continue
            if isinstance(child, QWidget):
                layout.addWidget(child)
            else:
                layout.addLayout(child)
        layout.addStretch(1)
        return container

    def _current_field_mapping(self) -> dict[str, str]:
        return {
            key: edit.text().strip()
            for key, edit in self.mapping_edits.items()
            if edit.text().strip()
        }

    def _load_field_mapping(self, mapping: dict | None) -> None:
        cleaned_mapping = self._clean_field_mapping(mapping)
        for key, edit in self.mapping_edits.items():
            edit.setText(cleaned_mapping.get(key, ""))

    @classmethod
    def _clean_field_mapping(cls, mapping) -> dict[str, str]:
        if not isinstance(mapping, dict):
            return {}
        cleaned: dict[str, str] = {}
        for key in cls.FIELD_MAPPING_KEYS:
            cleaned[key] = cls._clean_text(mapping.get(key))
        for alias, key in cls.FIELD_MAPPING_ALIASES.items():
            if not cleaned[key]:
                cleaned[key] = cls._clean_text(mapping.get(alias))
        return cleaned

    @staticmethod
    def _clean_text(value) -> str:
        if value is None:
            return ""
        return str(value).strip()
