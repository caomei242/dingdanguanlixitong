from __future__ import annotations

import re
import shlex
import shutil
import uuid
from datetime import datetime
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
    QListWidget,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QTextEdit,
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


def _now_timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _parse_timestamp(value: str) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


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
        "规格": "规格",
        "SKU": "",
        "SKU 图片": "SKU图片",
        "数量": "数量",
        "收件人": "收件人",
        "手机号": "手机号",
        "编号": "编号",
        "收入": "收入",
        "发货地址": "发货地址",
        "采购快递单号": "采购快递单号",
        "采购快递单号1": "采购快递单号1",
        "采购快递单号2": "采购快递单号2",
        "采购快递单号3": "采购快递单号3",
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
    ALWAYS_HIDDEN_FIELD_MAPPING_KEYS = frozenset(
        {
            "订单编号",
            "SKU",
            "SKU 图片",
            "采购快递单号",
            "价格",
            "自定义字段1",
            "自定义字段2",
            "自定义字段3",
            "同步方式",
            "同步状态",
            "同步说明",
            "录入时间",
        }
    )
    FIELD_MAPPING_KEYS = (
        "店铺",
        "平台",
        "订单编号",
        "备注",
        "订单日期",
        "下单时间",
        "订单状态",
        "商品名称",
        "规格",
        "SKU",
        "SKU 图片",
        "数量",
        "收件人",
        "手机号",
        "编号",
        "收入",
        "发货地址",
        "采购快递单号",
        "采购快递单号1",
        "采购快递单号2",
        "采购快递单号3",
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
        "specification": "规格",
        "sku": "SKU",
        "sku_image": "SKU 图片",
        "quantity": "数量",
        "recipient_name": "收件人",
        "phone_number": "手机号",
        "code": "编号",
        "income": "收入",
        "shipping_address": "发货地址",
        "procurement_tracking_number": "采购快递单号",
        "procurement_tracking_number_1": "采购快递单号1",
        "procurement_tracking_number_2": "采购快递单号2",
        "procurement_tracking_number_3": "采购快递单号3",
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
    DEFAULT_UPDATE_LOGS = (
        {
            "id": "seed-2026-04-14-update-log",
            "created_at": "2026-04-14 12:30:00",
            "updated_at": "2026-04-14 12:30:00",
            "module": "设置",
            "title": "新增更新日志页签",
            "content": "在设置页增加更新日志板块，支持查看、编辑、删除开发更新记录，并为后续开发沉淀统一入口。",
        },
        {
            "id": "seed-2026-04-14-procurement-template",
            "created_at": "2026-04-14 12:10:00",
            "updated_at": "2026-04-14 12:10:00",
            "module": "录单",
            "title": "支持规格模板预填采购明细",
            "content": "相同规格的订单可以自动预填采购商品、数量和成本，快递单号不跟随模板预填。",
        },
        {
            "id": "seed-2026-04-14-tracking-number",
            "created_at": "2026-04-14 11:50:00",
            "updated_at": "2026-04-14 11:50:00",
            "module": "历史",
            "title": "采购快递单号升级为三条采购位",
            "content": "采购1、采购2、采购3分别支持填写快递单号，历史页可以直接按这些单号搜索订单。",
        },
        {
            "id": "seed-2026-04-14-profit-page",
            "created_at": "2026-04-14 10:40:00",
            "updated_at": "2026-04-14 10:40:00",
            "module": "利润计算",
            "title": "新增利润计算页面",
            "content": "新增大盘和每日账目明细两个 tab，用历史数据展示收入、支出、毛利、利润率、同比和环比。",
        },
        {
            "id": "seed-2026-04-13-history-edit",
            "created_at": "2026-04-13 21:30:00",
            "updated_at": "2026-04-13 21:30:00",
            "module": "历史",
            "title": "历史记录支持编辑后覆盖飞书",
            "content": "历史页可直接修改订单内容，保存后优先更新飞书原记录，找不到对应记录时自动新建。",
        },
        {
            "id": "seed-2026-04-13-finance",
            "created_at": "2026-04-13 20:10:00",
            "updated_at": "2026-04-13 20:10:00",
            "module": "录单",
            "title": "补齐财务信息自动计算",
            "content": "支持平台扣点比例、平台扣点金额、采购总成本、毛利润联动计算，并默认平台扣点比例为 0.06。",
        },
        {
            "id": "seed-2026-04-13-feishu",
            "created_at": "2026-04-13 18:50:00",
            "updated_at": "2026-04-13 18:50:00",
            "module": "飞书同步",
            "title": "总表模式和多店铺预设落地",
            "content": "店铺统一写入订单总表，通过店铺字段区分不同店铺，并预置乐宝、欢宝、灵宝、君宝、珍宝、悦宝六家店。",
        },
        {
            "id": "seed-2026-04-13-ocr-address",
            "created_at": "2026-04-13 17:20:00",
            "updated_at": "2026-04-13 17:20:00",
            "module": "录单",
            "title": "地址提取和识图流程整合",
            "content": "支持截图/粘贴识别订单，同时生成地址提取结果，录单前先展示订单卡供确认。",
        },
    )
    KNOWN_UPDATE_LOG_TIMESTAMPS = {
        ("设置", "新增更新日志页签"): "2026-04-14 12:30:00",
        ("录单", "支持规格模板预填采购明细"): "2026-04-14 12:10:00",
        ("历史", "采购快递单号升级为三条采购位"): "2026-04-14 11:50:00",
        ("利润计算", "新增利润计算页面"): "2026-04-14 10:40:00",
        ("历史", "历史记录支持编辑后覆盖飞书"): "2026-04-13 21:30:00",
        ("录单", "补齐财务信息自动计算"): "2026-04-13 20:10:00",
        ("飞书同步", "总表模式和多店铺预设落地"): "2026-04-13 18:50:00",
        ("录单", "地址提取和识图流程整合"): "2026-04-13 17:20:00",
        ("UI重构", "全局壳子升级为 Mac 视窗风格"): "2026-04-14 20:40:00",
        ("订单录入", "录单页升级为三栏工作台"): "2026-04-14 21:05:00",
        ("历史", "修复历史备注清空与界面整理"): "2026-04-14 21:30:00",
        ("利润计算", "利润页升级为双 Tab 驾驶舱"): "2026-04-14 21:45:00",
        ("设置", "设置页升级为左导航工作台"): "2026-04-14 22:00:00",
        ("UI重构", "补齐侧栏命名与财务大盘分层"): "2026-04-14 22:10:00",
        ("录单", "规格模板联动升级为自动沉淀"): "2026-04-16 10:30:00",
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
        self.intake_default_shop_selector = QComboBox()
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
        self.update_log_list = QListWidget()
        self.update_log_list.setObjectName("HistoryList")
        self.update_log_time_label = QLabel("—")
        self.update_log_time_label.setObjectName("MutedText")
        self.update_log_module_edit = QLineEdit()
        self.update_log_title_edit = QLineEdit()
        self.update_log_content_edit = QTextEdit()
        self.add_update_log_button = QPushButton("新增日志")
        self.save_update_log_button = QPushButton("保存修改")
        self.delete_update_log_button = QPushButton("删除日志")
        self.custom_cost_label_edits = [QLineEdit() for _ in range(3)]
        self.show_enabled_only_checkbox = QCheckBox("仅显示启用字段")
        self._on_resolve_shop_link = on_resolve_shop_link
        self._on_inspect_table_fields = on_inspect_table_fields
        self.ocr_mcp_command_edit.setText(_preferred_mcp_command())
        self._product_presets: list[dict[str, str]] = []
        self._procurement_templates: list[dict[str, object]] = []
        self._update_logs: list[dict[str, str]] = []
        self._update_logs_initialized = False
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
        shop_form.addRow("录单默认店铺", self.intake_default_shop_selector)
        shop_form.addRow("店铺名称", self.shop_name_edit)
        shop_form.addRow("总表链接", self.shop_wiki_url_edit)
        shop_form.addRow("总表 App Token", self.shop_app_token_edit)
        shop_form.addRow("总表 Table ID", self.shop_table_id_edit)
        shop_form.addRow("总表备注", self.shop_table_name_edit)
        mapping_grid = QGridLayout()
        mapping_grid.setHorizontalSpacing(16)
        mapping_grid.setVerticalSpacing(10)
        self.mapping_grid_layout = mapping_grid
        for index, key in enumerate(self.FIELD_MAPPING_KEYS):
            row = index // 3
            column = index % 3
            row_widget = self._build_mapping_row(key, self.mapping_edits[key])
            self.mapping_row_widgets[key] = row_widget
            mapping_grid.addWidget(row_widget, row, column)

        title = QLabel("设置")
        title.setObjectName("SectionTitle")
        title_box = QVBoxLayout()
        title_box.setContentsMargins(0, 0, 0, 0)
        title_box.setSpacing(4)
        title_box.addWidget(title)

        action_box = QVBoxLayout()
        action_box.setContentsMargins(0, 0, 0, 0)
        action_box.setSpacing(8)
        action_box.addWidget(self.status_label, 0)
        action_box.addWidget(self.save_button, 0)

        header_bar = QFrame()
        header_bar.setObjectName("SettingsStickyActionBar")
        header_layout = QHBoxLayout(header_bar)
        header_layout.setContentsMargins(16, 14, 16, 14)
        header_layout.setSpacing(12)
        header_layout.addLayout(title_box, 1)
        header_layout.addLayout(action_box, 0)

        api_section = self._build_settings_section(
            "接口配置",
            "",
            self._build_tab_card("接口参数", api_form),
        )
        product_section = self._build_settings_section(
            "商品库",
            "",
            self._build_tab_card("全局商品库", product_form, product_button_row),
            self._build_tab_card("自定义费用字段", custom_cost_form),
        )
        mapping_section = self._build_settings_section(
            "店铺映射",
            "",
            self._build_tab_card("店铺与总表信息", shop_form, shop_button_row),
            self._build_tab_card("字段映射", self.show_enabled_only_checkbox, mapping_grid),
        )
        update_log_section = self._build_settings_section(
            "更新日志",
            "",
            self._build_update_log_tab(),
        )

        self.section_nav = QListWidget()
        self.section_nav.setObjectName("SettingsSectionNav")
        self.section_nav.setFixedWidth(156)
        self.section_nav.addItems(["接口配置", "商品库", "店铺映射", "更新日志"])

        nav_frame = QFrame()
        nav_frame.setObjectName("SettingsNavPane")
        nav_layout = QVBoxLayout(nav_frame)
        nav_layout.setContentsMargins(14, 14, 14, 14)
        nav_layout.setSpacing(10)
        nav_layout.addWidget(self.section_nav, 1)

        self.section_stack = QStackedWidget()
        self.section_stack.setObjectName("SettingsSectionStack")
        self.section_stack.addWidget(api_section)
        self.section_stack.addWidget(product_section)
        self.section_stack.addWidget(mapping_section)
        self.section_stack.addWidget(update_log_section)

        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(14)
        body_layout.addWidget(nav_frame, 0)
        body_layout.addWidget(self.section_stack, 1)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)
        root.addWidget(header_bar)
        root.addWidget(body, 1)
        self.save_button.clicked.connect(self._emit_save_requested)
        self.add_product_button.clicked.connect(self._handle_add_product)
        self.save_product_button.clicked.connect(self._handle_save_product)
        self.remove_product_button.clicked.connect(self._handle_remove_product)
        self.add_shop_button.clicked.connect(self._handle_add_shop)
        self.save_shop_button.clicked.connect(self._handle_save_shop)
        self.check_table_fields_button.clicked.connect(self._handle_check_table_fields)
        self.remove_shop_button.clicked.connect(self._handle_remove_shop)
        self.add_update_log_button.clicked.connect(self._handle_add_update_log)
        self.save_update_log_button.clicked.connect(self._handle_save_update_log)
        self.delete_update_log_button.clicked.connect(self._handle_remove_update_log)
        self.update_log_list.currentRowChanged.connect(self._load_selected_update_log)
        self.product_selector.currentIndexChanged.connect(self._load_selected_product)
        self.shop_selector.currentIndexChanged.connect(self._load_selected_shop)
        self.section_nav.currentRowChanged.connect(self.section_stack.setCurrentIndex)
        self.show_enabled_only_checkbox.toggled.connect(self._update_mapping_visibility)
        for edit in self.mapping_edits.values():
            edit.textChanged.connect(self._update_mapping_visibility)
        for index, edit in enumerate(self.custom_cost_label_edits):
            edit.textChanged.connect(lambda _text, idx=index: self._handle_custom_cost_label_changed(idx))
        self.section_nav.setCurrentRow(0)
        self._load_field_mapping(None, use_defaults=True)
        for index in range(3):
            self._handle_custom_cost_label_changed(index)
        self._refresh_shop_selector(self.DEFAULT_SELECTED_SHOP)
        self._refresh_intake_default_shop_selector(self.DEFAULT_SELECTED_SHOP)

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
            "procurement_templates": [self._copy_procurement_template(item) for item in self._procurement_templates],
            "update_logs_initialized": self._update_logs_initialized,
            "update_logs": [self._copy_update_log(item) for item in self._update_logs],
            "shops": [{"name": shop["name"]} for shop in self._shops],
            "selected_shop_name": self.shop_selector.currentText().strip() or self.DEFAULT_SELECTED_SHOP,
            "intake_default_shop_name": self.intake_default_shop_selector.currentText().strip() or self.DEFAULT_SELECTED_SHOP,
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
        self._procurement_templates = [
            self._normalize_procurement_template(item)
            for item in payload.get("procurement_templates", [])
            if isinstance(item, dict)
        ]
        self._procurement_templates = [
            item for item in self._procurement_templates if item["specification"]
        ]
        self._update_logs_initialized = bool(payload.get("update_logs_initialized"))
        self._update_logs = [
            self._normalize_update_log(item)
            for item in payload.get("update_logs", [])
            if isinstance(item, dict)
        ]
        self._update_logs = [item for item in self._update_logs if item["id"]]
        if not self._update_logs_initialized:
            self._update_logs = [self._copy_update_log(item) for item in self.DEFAULT_UPDATE_LOGS]
            self._update_logs_initialized = True
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
        self._refresh_intake_default_shop_selector(
            self._clean_text(payload.get("intake_default_shop_name"))
            or self._clean_text(payload.get("selected_shop_name"))
            or self.DEFAULT_SELECTED_SHOP
        )
        self._refresh_update_log_list()

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
        self._refresh_intake_default_shop_selector(self.intake_default_shop_selector.currentText().strip() or shop_name)
        self.status_label.setText("已保存店铺")

    def _handle_remove_shop(self) -> None:
        selected_name = self.shop_selector.currentText().strip()
        if not selected_name:
            return
        self._shops = [shop for shop in self._shops if shop["name"] != selected_name]
        self._shops = self._normalize_shops(self._shops)
        self._refresh_shop_selector()
        self._refresh_intake_default_shop_selector()

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

    def upsert_procurement_template(self, specification: str, procurement_items: list[dict[str, str]]) -> bool:
        template = self._normalize_procurement_template(
            {"specification": specification, "procurement_items": procurement_items}
        )
        if not template["specification"]:
            return False
        template_key = self._normalize_specification_key(template["specification"])
        for index, existing in enumerate(self._procurement_templates):
            if self._normalize_specification_key(existing["specification"]) == template_key:
                if existing == template:
                    return False
                self._procurement_templates[index] = template
                return True
        self._procurement_templates.append(template)
        return True

    def procurement_templates(self) -> list[dict[str, object]]:
        return [self._copy_procurement_template(item) for item in self._procurement_templates]

    def append_update_log(self, module: str, title: str, content: str, *, created_at: str | None = None) -> bool:
        normalized = self._normalize_update_log(
            {
                "id": str(uuid.uuid4()),
                "created_at": created_at or _now_timestamp(),
                "updated_at": created_at or _now_timestamp(),
                "module": module,
                "title": title,
                "content": content,
            }
        )
        if not normalized["title"]:
            return False
        self._update_logs.insert(0, normalized)
        self._update_logs_initialized = True
        self._refresh_update_log_list(select_id=normalized["id"])
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

    def _refresh_intake_default_shop_selector(self, selected_name: str | None = None) -> None:
        self.intake_default_shop_selector.blockSignals(True)
        self.intake_default_shop_selector.clear()
        self.intake_default_shop_selector.addItems([shop["name"] for shop in self._shops])
        target = selected_name or self.DEFAULT_SELECTED_SHOP
        if target:
            index = self.intake_default_shop_selector.findText(target)
            if index >= 0:
                self.intake_default_shop_selector.setCurrentIndex(index)
            elif self.intake_default_shop_selector.count() > 0:
                self.intake_default_shop_selector.setCurrentIndex(0)
        self.intake_default_shop_selector.blockSignals(False)

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
            if key in self.ALWAYS_HIDDEN_FIELD_MAPPING_KEYS:
                row_widget.setVisible(False)
                continue
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

    def _build_update_log_tab(self) -> QWidget:
        actions = QHBoxLayout()
        actions.addWidget(self.add_update_log_button)
        actions.addWidget(self.save_update_log_button)
        actions.addWidget(self.delete_update_log_button)
        actions.addStretch(1)

        detail_form = QFormLayout()
        detail_form.addRow("最后更新时间", self.update_log_time_label)
        detail_form.addRow("模块", self.update_log_module_edit)
        detail_form.addRow("标题", self.update_log_title_edit)
        detail_form.addRow("内容", self.update_log_content_edit)

        content = QWidget()
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(12)

        list_card = QFrame()
        list_card.setObjectName("HistoryListCard")
        list_layout = QVBoxLayout(list_card)
        list_layout.setContentsMargins(12, 12, 12, 12)
        list_layout.addWidget(self.update_log_list, 1)

        detail_card = QFrame()
        detail_card.setObjectName("HistoryDetailCard")
        detail_layout = QVBoxLayout(detail_card)
        detail_layout.setContentsMargins(12, 12, 12, 12)
        detail_layout.addLayout(actions)
        detail_layout.addLayout(detail_form)

        content_layout.addWidget(list_card, 2)
        content_layout.addWidget(detail_card, 3)
        return self._build_tab_card("", content)

    @staticmethod
    def _build_settings_section(title: str, subtitle: str, *widgets: QWidget) -> QScrollArea:
        content = QWidget()
        content.setObjectName("PageContent")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        title_label = QLabel(title)
        title_label.setObjectName("SectionTitle")
        layout.addWidget(title_label)
        if subtitle:
            subtitle_label = QLabel(subtitle)
            subtitle_label.setObjectName("MutedText")
            layout.addWidget(subtitle_label)
        for widget in widgets:
            layout.addWidget(widget)
        layout.addStretch(1)

        scroll_area = QScrollArea()
        scroll_area.setObjectName("SettingsSectionScroll")
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll_area.setWidget(content)
        return scroll_area

    def _custom_mapping_display_name(self, key: str) -> str:
        if key == "自定义字段1":
            return self.custom_cost_label_edits[0].text().strip() or key
        if key == "自定义字段2":
            return self.custom_cost_label_edits[1].text().strip() or key
        if key == "自定义字段3":
            return self.custom_cost_label_edits[2].text().strip() or key
        return key

    def _refresh_update_log_list(self, select_id: str | None = None) -> None:
        previous_id = select_id or self._current_update_log_id()
        self._update_logs.sort(
            key=lambda item: (
                item.get("updated_at", ""),
                item.get("created_at", ""),
                item.get("id", ""),
            ),
            reverse=True,
        )
        self.update_log_list.blockSignals(True)
        self.update_log_list.clear()
        for item in self._update_logs:
            summary = f"[{item['module'] or '未分类'}] {item['title']} · {item['updated_at']}"
            self.update_log_list.addItem(summary)
        self.update_log_list.blockSignals(False)
        target_index = 0
        if previous_id:
            for index, item in enumerate(self._update_logs):
                if item["id"] == previous_id:
                    target_index = index
                    break
        if self._update_logs:
            self.update_log_list.setCurrentRow(target_index)
        else:
            self._clear_update_log_editor()

    def _load_selected_update_log(self, index: int) -> None:
        if index < 0 or index >= len(self._update_logs):
            self._clear_update_log_editor()
            return
        item = self._update_logs[index]
        self.update_log_time_label.setText(item["updated_at"] or item["created_at"] or "—")
        self.update_log_module_edit.setText(item["module"])
        self.update_log_title_edit.setText(item["title"])
        self.update_log_content_edit.setPlainText(item["content"])

    def _handle_add_update_log(self) -> None:
        now = _now_timestamp()
        item = self._normalize_update_log(
            {
                "id": str(uuid.uuid4()),
                "created_at": now,
                "updated_at": now,
                "module": "",
                "title": "",
                "content": "",
            }
        )
        self._update_logs.insert(0, item)
        self._update_logs_initialized = True
        self._refresh_update_log_list(select_id=item["id"])
        self.update_log_module_edit.setFocus()
        self.status_label.setText("已新增一条更新日志")

    def _handle_save_update_log(self) -> None:
        row = self.update_log_list.currentRow()
        if row < 0 or row >= len(self._update_logs):
            self.status_label.setText("请先选择一条更新日志")
            return
        title = self.update_log_title_edit.text().strip()
        if not title:
            self.status_label.setText("请先填写日志标题")
            return
        self._update_logs[row].update(
            {
                "module": self.update_log_module_edit.text().strip(),
                "title": title,
                "content": self.update_log_content_edit.toPlainText().strip(),
                "updated_at": _now_timestamp(),
            }
        )
        self._update_logs_initialized = True
        self._refresh_update_log_list(select_id=self._update_logs[row]["id"])
        self.status_label.setText("已保存更新日志")

    def _handle_remove_update_log(self) -> None:
        row = self.update_log_list.currentRow()
        if row < 0 or row >= len(self._update_logs):
            return
        del self._update_logs[row]
        self._update_logs_initialized = True
        self._refresh_update_log_list()
        self.status_label.setText("已删除更新日志")

    def _current_update_log_id(self) -> str:
        row = self.update_log_list.currentRow()
        if 0 <= row < len(self._update_logs):
            return self._update_logs[row]["id"]
        return ""

    def _clear_update_log_editor(self) -> None:
        self.update_log_time_label.setText("—")
        self.update_log_module_edit.clear()
        self.update_log_title_edit.clear()
        self.update_log_content_edit.clear()

    @classmethod
    def _normalize_procurement_template(cls, template: dict[str, object]) -> dict[str, object]:
        specification = cls._clean_text(template.get("specification"))
        raw_items = template.get("procurement_items")
        items: list[dict[str, str]] = []
        if isinstance(raw_items, list):
            source_items = raw_items
        else:
            source_items = []
        for index in range(3):
            item = source_items[index] if index < len(source_items) and isinstance(source_items[index], dict) else {}
            product_name = cls._clean_text(item.get("product_name"))
            quantity = cls._clean_text(item.get("quantity"))
            cost = cls._clean_text(item.get("cost"))
            items.append(
                {
                    "product_name": product_name,
                    "quantity": (
                        quantity
                        if quantity != "1" or any((product_name, cost))
                        else ""
                    ) or ("1" if any((product_name, cost)) else ""),
                    "cost": cost,
                }
            )
        return {"specification": specification, "procurement_items": items}

    @staticmethod
    def _copy_procurement_template(template: dict[str, object]) -> dict[str, object]:
        return {
            "specification": str(template.get("specification", "")).strip(),
            "procurement_items": [
                {
                    "product_name": str(item.get("product_name", "")).strip(),
                    "quantity": (
                        (
                            str(item.get("quantity", "")).strip()
                            if str(item.get("quantity", "")).strip() != "1"
                            or any(
                                (
                                    str(item.get("product_name", "")).strip(),
                                    str(item.get("cost", "")).strip(),
                                )
                            )
                            else ""
                        )
                        or (
                            "1"
                            if any(
                                (
                                    str(item.get("product_name", "")).strip(),
                                    str(item.get("cost", "")).strip(),
                                )
                            )
                            else ""
                        )
                    ),
                    "cost": str(item.get("cost", "")).strip(),
                }
                for item in list(template.get("procurement_items") or [])[:3]
            ],
        }

    @staticmethod
    def _normalize_update_log(item: dict[str, object]) -> dict[str, str]:
        created_at = str(item.get("created_at", "")).strip() or _now_timestamp()
        updated_at = str(item.get("updated_at", "")).strip() or created_at
        module = str(item.get("module", "")).strip()
        title = str(item.get("title", "")).strip()
        key = (module, title)
        known_timestamp = SettingsPage.KNOWN_UPDATE_LOG_TIMESTAMPS.get(key, "")
        now = datetime.now()
        created_dt = _parse_timestamp(created_at)
        updated_dt = _parse_timestamp(updated_at)
        known_dt = _parse_timestamp(known_timestamp)
        if known_dt is not None:
            if created_dt is not None and created_dt > now:
                created_at = known_timestamp
                created_dt = known_dt
            if updated_dt is not None and updated_dt > now:
                updated_at = known_timestamp
        elif created_dt is not None and created_dt > now:
            created_at = now.strftime("%Y-%m-%d %H:%M:%S")
        if updated_dt is not None and updated_dt > now and not known_dt:
            updated_at = created_at
        if not updated_at:
            updated_at = created_at
        return {
            "id": str(item.get("id", "")).strip() or str(uuid.uuid4()),
            "created_at": created_at,
            "updated_at": updated_at,
            "module": module,
            "title": title,
            "content": str(item.get("content", "")).strip(),
        }

    @staticmethod
    def _copy_update_log(item: dict[str, object]) -> dict[str, str]:
        return {
            "id": str(item.get("id", "")).strip(),
            "created_at": str(item.get("created_at", "")).strip(),
            "updated_at": str(item.get("updated_at", "")).strip(),
            "module": str(item.get("module", "")).strip(),
            "title": str(item.get("title", "")).strip(),
            "content": str(item.get("content", "")).strip(),
        }

    @staticmethod
    def _build_tab_card(title: str, *layouts) -> QWidget:
        container = QFrame()
        container.setObjectName("CardFrame")
        layout = QVBoxLayout(container)
        if title:
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

    @staticmethod
    def _normalize_specification_key(specification: str) -> str:
        compact = re.sub(r"\s+", "", str(specification or "").strip())
        return re.sub(r"(?:[xX×＊*]1)$", "", compact)
