from __future__ import annotations

import shlex
import shutil
from pathlib import Path

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


def _preferred_mcp_command() -> str:
    local_binary = shutil.which("minimax-coding-plan-mcp")
    if local_binary:
        return local_binary
    return "uvx minimax-coding-plan-mcp -y"


def _is_legacy_uvx_command(command: str) -> bool:
    try:
        args = shlex.split(command)
    except ValueError:
        return False
    if len(args) < 2:
        return False
    return Path(args[0]).name == "uvx" and args[1] == "minimax-coding-plan-mcp"


def _normalize_mcp_command(command: str) -> str:
    cleaned = command.strip()
    if not cleaned:
        return _preferred_mcp_command()
    if _is_legacy_uvx_command(cleaned):
        preferred = _preferred_mcp_command()
        if preferred:
            return preferred
    return cleaned


class SettingsPage(QWidget):
    save_requested = Signal(object)
    DEFAULT_SHOPS = (
        "乐宝零食店",
        "欢宝零食店",
        "灵宝零食店",
        "君宝零食店",
        "珍宝零食店",
        "悦宝零食店",
    )
    DEFAULT_SELECTED_SHOP = "乐宝零食店"
    RECOMMENDED_FIELD_MAPPING = {
        "店铺": "店铺",
        "平台": "平台",
        "订单编号": "订单编号",
        "备注": "备注",
        "订单日期": "订单日期",
        "下单时间": "下单时间",
        "订单状态": "订单状态",
        "商品名称": "商品名称",
        "数量": "数量",
        "收件人": "收件人",
        "手机号": "手机号",
        "编号": "编号",
        "收入": "收入",
        "发货地址": "发货地址",
        "平台扣点比例": "平台扣点比例",
        "平台扣点金额": "平台扣点金额",
        "其他成本": "其他成本",
        "采购总成本": "采购总成本",
        "毛利润": "毛利润",
        "自定义字段1": "自定义字段1",
        "自定义字段2": "自定义字段2",
        "自定义字段3": "自定义字段3",
        "同步方式": "同步方式",
        "同步状态": "同步状态",
        "同步说明": "同步说明",
        "录入时间": "录入时间",
        "采购商品1": "采购商品1",
        "采购数量1": "采购数量1",
        "采购成本1": "采购成本1",
        "采购商品2": "采购商品2",
        "采购数量2": "采购数量2",
        "采购成本2": "采购成本2",
        "采购商品3": "采购商品3",
        "采购数量3": "采购数量3",
        "采购成本3": "采购成本3",
    }
    FIELD_MAPPING_KEYS = (
        "店铺",
        "平台",
        "订单编号",
        "备注",
        "订单日期",
        "下单时间",
        "订单状态",
        "商品名称",
        "数量",
        "收件人",
        "手机号",
        "编号",
        "收入",
        "发货地址",
        "价格",
        "平台扣点比例",
        "平台扣点金额",
        "其他成本",
        "采购总成本",
        "毛利润",
        "自定义字段1",
        "自定义字段2",
        "自定义字段3",
        "同步方式",
        "同步状态",
        "同步说明",
        "录入时间",
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
        "shop_name": "店铺",
        "platform": "平台",
        "order_id": "订单编号",
        "remark": "备注",
        "order_date": "订单日期",
        "order_time": "下单时间",
        "order_status": "订单状态",
        "product_name": "商品名称",
        "quantity": "数量",
        "recipient_name": "收件人",
        "phone_number": "手机号",
        "code": "编号",
        "income": "收入",
        "shipping_address": "发货地址",
        "price": "价格",
        "platform_fee_rate": "平台扣点比例",
        "platform_fee_amount": "平台扣点金额",
        "other_cost": "其他成本",
        "procurement_total_cost": "采购总成本",
        "gross_profit": "毛利润",
        "custom_cost_1": "自定义字段1",
        "custom_cost_2": "自定义字段2",
        "custom_cost_3": "自定义字段3",
        "sync_source": "同步方式",
        "sync_status": "同步状态",
        "sync_message": "同步说明",
        "recorded_at": "录入时间",
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

    def __init__(self, on_resolve_shop_link=None, on_inspect_table_fields=None) -> None:
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
        self.check_table_fields_button = QPushButton("检测总表字段")
        self.remove_shop_button = QPushButton("删除店铺")
        self.save_button = QPushButton("保存/应用")
        self.status_label = QLabel("")
        self.status_label.setObjectName("MutedText")
        self.custom_cost_label_edits = [QLineEdit() for _ in range(3)]
        self.show_enabled_only_checkbox = QCheckBox("仅显示启用字段")
        self._on_resolve_shop_link = on_resolve_shop_link
        self._on_inspect_table_fields = on_inspect_table_fields
        self.ocr_mcp_command_edit.setText(_preferred_mcp_command())
        self._product_presets: list[dict[str, str]] = []
        self._shops: list[dict[str, str]] = [
            {"name": name} for name in self.DEFAULT_SHOPS
        ]
        self.mapping_edits: dict[str, QLineEdit] = {
            key: QLineEdit() for key in self.FIELD_MAPPING_KEYS
        }
        self.mapping_row_widgets: dict[str, QWidget] = {}
        self.mapping_row_labels: dict[str, QLabel] = {}
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
        custom_cost_form = QFormLayout()
        custom_cost_form.addRow("自定义字段1", self.custom_cost_label_edits[0])
        custom_cost_form.addRow("自定义字段2", self.custom_cost_label_edits[1])
        custom_cost_form.addRow("自定义字段3", self.custom_cost_label_edits[2])

        shop_button_row = QHBoxLayout()
        shop_button_row.addWidget(self.add_shop_button)
        shop_button_row.addWidget(self.save_shop_button)
        shop_button_row.addWidget(self.check_table_fields_button)
        shop_button_row.addWidget(self.remove_shop_button)

        shop_form = QFormLayout()
        shop_form.addRow("已保存店铺", self.shop_selector)
        shop_form.addRow("店铺名称", self.shop_name_edit)
        shop_form.addRow("总表链接", self.shop_wiki_url_edit)
        shop_form.addRow("总表 App Token", self.shop_app_token_edit)
        shop_form.addRow("总表 Table ID", self.shop_table_id_edit)
        shop_form.addRow("总表备注", self.shop_table_name_edit)
        mapping_grid = QGridLayout()
        mapping_grid.setHorizontalSpacing(16)
        mapping_grid.setVerticalSpacing(10)
        for index, key in enumerate(self.FIELD_MAPPING_KEYS):
            row = index // 2
            column = index % 2
            row_widget = self._build_mapping_row(key, self.mapping_edits[key])
            self.mapping_row_widgets[key] = row_widget
            mapping_grid.addWidget(row_widget, row, column)

        self.tabs = QTabWidget()
        self.tabs.setObjectName("SettingsTabs")
        self.tabs.addTab(self._build_tab_card("接口配置", api_form), "接口配置")
        self.tabs.addTab(
            self._build_tab_card("全局商品库", product_form, custom_cost_form, product_button_row),
            "商品库",
        )
        self.tabs.addTab(
            self._build_tab_card(
                "店铺与 Sheet 映射",
                shop_form,
                self.show_enabled_only_checkbox,
                shop_button_row,
                mapping_grid,
            ),
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
        self.check_table_fields_button.clicked.connect(self._handle_check_table_fields)
        self.remove_shop_button.clicked.connect(self._handle_remove_shop)
        self.product_selector.currentIndexChanged.connect(self._load_selected_product)
        self.shop_selector.currentIndexChanged.connect(self._load_selected_shop)
        self.show_enabled_only_checkbox.toggled.connect(self._update_mapping_visibility)
        for edit in self.mapping_edits.values():
            edit.textChanged.connect(self._update_mapping_visibility)
        for index, edit in enumerate(self.custom_cost_label_edits):
            edit.textChanged.connect(lambda _text, idx=index: self._handle_custom_cost_label_changed(idx))
        self._load_field_mapping(None, use_defaults=True)
        for index in range(3):
            self._handle_custom_cost_label_changed(index)
        self._refresh_shop_selector(self.DEFAULT_SELECTED_SHOP)

    def to_payload(self) -> dict:
        return {
            "ocr_use_mcp": self.ocr_use_mcp_checkbox.isChecked(),
            "ocr_mcp_command": _normalize_mcp_command(self.ocr_mcp_command_edit.text()),
            "ocr_base_url": self.ocr_base_url_edit.text().strip(),
            "ocr_api_key": self.ocr_api_key_edit.text().strip(),
            "helper_base_url": self.helper_base_url_edit.text().strip(),
            "helper_api_key": self.helper_api_key_edit.text().strip(),
            "feishu_app_id": self.feishu_app_id_edit.text().strip(),
            "feishu_app_secret": self.feishu_app_secret_edit.text().strip(),
            "feishu_table_wiki_url": self.shop_wiki_url_edit.text().strip(),
            "feishu_table_app_token": self.shop_app_token_edit.text().strip(),
            "feishu_table_id": self.shop_table_id_edit.text().strip(),
            "feishu_table_name": self.shop_table_name_edit.text().strip(),
            "feishu_field_mapping": self._current_field_mapping(),
            "custom_cost_labels": [edit.text().strip() for edit in self.custom_cost_label_edits],
            "show_only_enabled_mappings": self.show_enabled_only_checkbox.isChecked(),
            "product_presets": [dict(item) for item in self._product_presets],
            "global_product_library": [dict(item) for item in self._product_presets],
            "shops": [{"name": shop["name"]} for shop in self._shops],
            "selected_shop_name": self.shop_selector.currentText().strip() or self.DEFAULT_SELECTED_SHOP,
        }

    def load_payload(self, payload: dict) -> None:
        self.ocr_use_mcp_checkbox.setChecked(bool(payload.get("ocr_use_mcp")))
        self.ocr_mcp_command_edit.setText(_normalize_mcp_command(self._clean_text(payload.get("ocr_mcp_command"))))
        self.ocr_base_url_edit.setText(self._clean_text(payload.get("ocr_base_url")))
        self.ocr_api_key_edit.setText(self._clean_text(payload.get("ocr_api_key")))
        self.helper_base_url_edit.setText(self._clean_text(payload.get("helper_base_url")))
        self.helper_api_key_edit.setText(self._clean_text(payload.get("helper_api_key")))
        self.feishu_app_id_edit.setText(self._clean_text(payload.get("feishu_app_id")))
        self.feishu_app_secret_edit.setText(self._clean_text(payload.get("feishu_app_secret")))
        custom_cost_labels = payload.get("custom_cost_labels") or ["", "", ""]
        for index, edit in enumerate(self.custom_cost_label_edits):
            value = custom_cost_labels[index] if index < len(custom_cost_labels) else ""
            edit.setText(self._clean_text(value))
        self.show_enabled_only_checkbox.setChecked(bool(payload.get("show_only_enabled_mappings")))
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
        legacy_shop = next(
            (
                shop
                for shop in payload.get("shops", [])
                if isinstance(shop, dict) and self._clean_text(shop.get("name"))
            ),
            {},
        )
        self.shop_wiki_url_edit.setText(
            self._clean_text(payload.get("feishu_table_wiki_url"))
            or self._clean_text(legacy_shop.get("wiki_url"))
        )
        self.shop_app_token_edit.setText(
            self._clean_text(payload.get("feishu_table_app_token"))
            or self._clean_text(legacy_shop.get("app_token"))
        )
        self.shop_table_id_edit.setText(
            self._clean_text(payload.get("feishu_table_id"))
            or self._clean_text(legacy_shop.get("table_id"))
        )
        self.shop_table_name_edit.setText(
            self._clean_text(payload.get("feishu_table_name"))
            or self._clean_text(legacy_shop.get("table_name"))
        )
        loaded_shops = [
            {"name": self._clean_text(shop.get("name"))}
            for shop in payload.get("shops", [])
            if isinstance(shop, dict) and self._clean_text(shop.get("name"))
        ]
        self._shops = self._normalize_shops(loaded_shops)
        stored_mapping = payload.get("feishu_field_mapping")
        if stored_mapping is None:
            stored_mapping = legacy_shop.get("field_mapping")
        self._load_field_mapping(stored_mapping, use_defaults=not bool(stored_mapping))
        for index in range(3):
            self._handle_custom_cost_label_changed(index)
        self._clear_missing_field_highlight()
        self._refresh_product_selector()
        self._refresh_shop_selector(
            self._clean_text(payload.get("selected_shop_name")) or self.DEFAULT_SELECTED_SHOP
        )

    def _emit_save_requested(self) -> None:
        if self.shop_wiki_url_edit.text().strip() and self._on_resolve_shop_link is not None:
            try:
                resolved = self._on_resolve_shop_link(self.shop_wiki_url_edit.text().strip())
            except Exception as exc:
                self.status_label.setText(str(exc))
                return
            self.shop_app_token_edit.setText(str(resolved.get("app_token", "")).strip())
            self.shop_table_id_edit.setText(str(resolved.get("table_id", "")).strip())
            self.status_label.setText("已从飞书链接解析表格信息")
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
        self._load_field_mapping(None, use_defaults=True)
        self.shop_name_edit.setFocus()
        self.status_label.setText("")

    def _handle_save_shop(self) -> None:
        shop_name = self.shop_name_edit.text().strip()
        if not shop_name:
            self.status_label.setText("请先填写店铺名称")
            return
        for index, existing in enumerate(self._shops):
            if existing["name"] == shop_name:
                self._shops[index] = {"name": shop_name}
                break
        else:
            self._shops.append({"name": shop_name})

        self._shops = self._normalize_shops(self._shops)
        self._refresh_shop_selector(shop_name)
        self.status_label.setText("已保存店铺")

    def _handle_remove_shop(self) -> None:
        selected_name = self.shop_selector.currentText().strip()
        if not selected_name:
            return
        self._shops = [shop for shop in self._shops if shop["name"] != selected_name]
        self._shops = self._normalize_shops(self._shops)
        self._refresh_shop_selector()

    def _handle_check_table_fields(self) -> None:
        self._clear_missing_field_highlight()
        if self._on_inspect_table_fields is None:
            self.status_label.setText("当前环境未启用飞书字段检测")
            return
        try:
            field_names = set(self._on_inspect_table_fields(self.to_payload()))
        except Exception as exc:
            self.status_label.setText(str(exc))
            return
        required_targets = sorted(
            {
                edit.text().strip()
                for edit in self.mapping_edits.values()
                if edit.text().strip()
            }
        )
        missing_fields = [name for name in required_targets if name not in field_names]
        self._apply_missing_field_highlight(set(missing_fields))
        if missing_fields:
            self.status_label.setText(f"总表缺少字段：{'、'.join(missing_fields)}")
            return
        self.status_label.setText("总表字段检测通过")

    def _handle_custom_cost_label_changed(self, index: int) -> None:
        key = f"自定义字段{index + 1}"
        label_widget = self.mapping_row_labels.get(key)
        if label_widget is None:
            return
        display_name = self._custom_mapping_display_name(key)
        previous_name = label_widget.text().removesuffix(" 映射")
        label_widget.setText(f"{display_name} 映射")
        edit = self.mapping_edits[key]
        current_value = edit.text().strip()
        if current_value in {key, previous_name}:
            edit.setText(display_name)
        self._update_mapping_visibility()

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
        target = selected_name or self.DEFAULT_SELECTED_SHOP
        if target:
            index = self.shop_selector.findText(target)
            if index >= 0:
                self.shop_selector.setCurrentIndex(index)
            elif self.shop_selector.count() > 0:
                self.shop_selector.setCurrentIndex(0)
        self.shop_selector.blockSignals(False)
        self._load_selected_shop()
        self._update_mapping_visibility()

    @classmethod
    def _normalize_shops(cls, shops: list[dict[str, str]]) -> list[dict[str, str]]:
        normalized: list[dict[str, str]] = []
        seen: set[str] = set()
        for name in cls.DEFAULT_SHOPS:
            normalized.append({"name": name})
            seen.add(name)
        for shop in shops:
            name = cls._clean_text(shop.get("name"))
            if not name or name == "草莓店" or name in seen:
                continue
            normalized.append({"name": name})
            seen.add(name)
        return normalized

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
                return
        if not selected_name:
            self.shop_name_edit.clear()

    def _apply_missing_field_highlight(self, missing_fields: set[str]) -> None:
        for edit in self.mapping_edits.values():
            target_name = edit.text().strip()
            if target_name and target_name in missing_fields:
                edit.setStyleSheet("border: 1px solid #ff6b6b;")
            else:
                edit.setStyleSheet("")

    def _clear_missing_field_highlight(self) -> None:
        self._apply_missing_field_highlight(set())

    def _update_mapping_visibility(self) -> None:
        enabled_only = self.show_enabled_only_checkbox.isChecked()
        for key, row_widget in self.mapping_row_widgets.items():
            has_value = bool(self.mapping_edits[key].text().strip())
            row_widget.setVisible((not enabled_only) or has_value)

    def _build_mapping_row(self, key: str, edit: QLineEdit) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        label = QLabel(f"{self._custom_mapping_display_name(key)} 映射")
        label.setMinimumWidth(96)
        self.mapping_row_labels[key] = label
        layout.addWidget(label)
        layout.addWidget(edit, 1)
        return row

    def _custom_mapping_display_name(self, key: str) -> str:
        if key == "自定义字段1":
            return self.custom_cost_label_edits[0].text().strip() or key
        if key == "自定义字段2":
            return self.custom_cost_label_edits[1].text().strip() or key
        if key == "自定义字段3":
            return self.custom_cost_label_edits[2].text().strip() or key
        return key

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
        }

    def _load_field_mapping(self, mapping: dict | None, *, use_defaults: bool = False) -> None:
        raw_mapping = mapping if isinstance(mapping, dict) else {}
        cleaned_mapping = self._clean_field_mapping(mapping)
        for key, default_value in self.RECOMMENDED_FIELD_MAPPING.items():
            if key not in raw_mapping and not use_defaults:
                cleaned_mapping[key] = default_value
        if use_defaults:
            cleaned_mapping = self._mapping_with_recommended_defaults(cleaned_mapping)
        for key, edit in self.mapping_edits.items():
            edit.setText(cleaned_mapping.get(key, ""))
        self._update_mapping_visibility()

    @classmethod
    def _mapping_with_recommended_defaults(cls, mapping: dict[str, str]) -> dict[str, str]:
        merged = {key: mapping.get(key, "") for key in cls.FIELD_MAPPING_KEYS}
        for key, value in cls.RECOMMENDED_FIELD_MAPPING.items():
            if not merged[key]:
                merged[key] = value
        return merged

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
