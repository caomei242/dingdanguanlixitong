from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QMainWindow,
)


BLUEPRINT_STYLESHEET = """
QMainWindow {
    background: #e9eef5;
}

QWidget {
    color: #1e293b;
    font-family: "PingFang SC", "Microsoft YaHei", "Noto Sans SC", sans-serif;
    font-size: 14px;
}

QFrame#BlueprintShell {
    background: #f4f7fb;
    border: 1px solid #d8e1ef;
    border-radius: 14px;
}

QFrame#BlueprintTitleBar {
    background: rgba(255, 255, 255, 0.98);
    border-bottom: 1px solid #e2e8f0;
}

QFrame#BlueprintSidebar {
    background: #f8fafc;
    border-right: 1px solid #e2e8f0;
}

QFrame#BlueprintPage {
    background: transparent;
}

QFrame#BlueprintCard,
QFrame#BlueprintListCard,
QFrame#BlueprintHistoryMasterPane,
QFrame#BlueprintDetailCard,
QFrame#BlueprintStickyBar,
QFrame#BlueprintMetricCard,
QFrame#BlueprintSegmentWrap,
QFrame#BlueprintKpiStrip {
    background: rgba(255, 255, 255, 0.98);
    border: 1px solid #dbe4f0;
    border-radius: 14px;
}

QFrame#BlueprintStickyBar {
    background: rgba(255, 255, 255, 0.96);
}

QLabel#BlueprintBrandTitle {
    color: #ff4b6e;
    font-size: 26px;
    font-weight: 800;
}

QLabel#BlueprintBrandSubtitle,
QLabel#BlueprintMuted,
QLabel#BlueprintFieldLabel {
    color: #7b8aa5;
}

QLabel#BlueprintPageTitle {
    color: #172033;
    font-size: 22px;
    font-weight: 800;
}

QLabel#BlueprintSectionTitle {
    color: #1f2a44;
    font-size: 15px;
    font-weight: 700;
}

QLabel#BlueprintCardValue {
    color: #16233d;
    font-size: 24px;
    font-weight: 800;
}

QListWidget {
    background: transparent;
    border: none;
    outline: none;
}

QListWidget#BlueprintNav {
    background: transparent;
}

QListWidget#BlueprintNav::item {
    padding: 12px 14px;
    margin: 2px 0;
    border-radius: 12px;
    color: #5f708f;
    font-weight: 600;
}

QListWidget#BlueprintNav::item:selected {
    background: #4a7cff;
    color: #ffffff;
}

QListWidget#BlueprintMasterList::item,
QListWidget#BlueprintSettingsSubnav::item {
    padding: 12px 14px;
    margin: 3px 0;
    border-radius: 12px;
    color: #42526d;
}

QListWidget#BlueprintMasterList::item:selected,
QListWidget#BlueprintSettingsSubnav::item:selected {
    background: #eef4ff;
    color: #214fcb;
    border: 1px solid #c8d8ff;
}

QPushButton, QToolButton {
    background: #4a7cff;
    color: white;
    border: none;
    border-radius: 10px;
    padding: 8px 14px;
    font-weight: 600;
}

QPushButton:hover, QToolButton:hover {
    background: #3d70f0;
}

QPushButton#GhostButton, QToolButton#GhostButton {
    background: #edf3ff;
    color: #4269d5;
    border: 1px solid #cfdbff;
}

QPushButton#GhostButton:hover, QToolButton#GhostButton:hover {
    background: #e4edff;
}

QPushButton#DangerButton {
    background: #fff1f3;
    color: #d44b62;
    border: 1px solid #f1c7d0;
}

QPushButton#DangerButton:hover {
    background: #ffe5ea;
}

QLineEdit, QTextEdit, QComboBox {
    background: #ffffff;
    border: 1px solid #dbe4f0;
    border-radius: 8px;
    padding: 7px 10px;
    selection-background-color: #4a7cff;
}

QTextEdit {
    min-height: 60px;
}
"""


def _make_card(title: str, subtitle: str | None = None) -> tuple[QFrame, QVBoxLayout]:
    card = QFrame()
    card.setObjectName("BlueprintCard")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(16, 14, 16, 16)
    layout.setSpacing(12)
    title_label = QLabel(title)
    title_label.setObjectName("BlueprintSectionTitle")
    layout.addWidget(title_label)
    if subtitle:
        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("BlueprintMuted")
        subtitle_label.setWordWrap(True)
        layout.addWidget(subtitle_label)
    return card, layout


def _field(label: str, editor: QWidget, *, row_span: int = 1) -> tuple[QWidget, int]:
    wrapper = QWidget()
    layout = QVBoxLayout(wrapper)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)
    field_label = QLabel(label)
    field_label.setObjectName("BlueprintFieldLabel")
    layout.addWidget(field_label)
    layout.addWidget(editor)
    return wrapper, row_span


def _input(text: str = "") -> QLineEdit:
    edit = QLineEdit()
    edit.setText(text)
    return edit


def _text(text: str = "", *, height: int = 64) -> QTextEdit:
    edit = QTextEdit()
    edit.setPlainText(text)
    edit.setMinimumHeight(height)
    return edit


class _TrafficLights(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setFixedSize(54, 14)

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        colors = ["#ff5f56", "#ffbd2e", "#27c93f"]
        borders = ["#e0443e", "#dea123", "#1aab29"]
        for index, (fill, border) in enumerate(zip(colors, borders)):
            painter.setPen(QPen(QColor(border), 1))
            painter.setBrush(QColor(fill))
            painter.drawEllipse(1 + index * 18, 1, 12, 12)


class _TrendPreview(QFrame):
    def __init__(self) -> None:
        super().__init__()
        self.setMinimumHeight(250)

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QColor("#ffffff"))
        rect = self.rect().adjusted(22, 18, -18, -30)
        if rect.width() <= 0 or rect.height() <= 0:
            return

        grid_pen = QPen(QColor("#e5edf9"))
        grid_pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(grid_pen)
        for step in range(5):
            y = rect.top() + int(rect.height() * step / 4)
            painter.drawLine(rect.left(), y, rect.right(), y)

        values = [0, 0, 0, 0, 150, 110, 305, 260, 466, 0, 0, 0]
        labels = ["04/01", "04/08", "04/16", "04/30"]
        max_value = max(values) or 1
        points = []
        step_x = rect.width() / max(len(values) - 1, 1)
        for idx, value in enumerate(values):
            x = rect.left() + step_x * idx
            y = rect.bottom() - rect.height() * (value / max_value)
            points.append((x, y))

        painter.setPen(QPen(QColor("#4f7cff"), 2.4))
        for idx in range(len(points) - 1):
            painter.drawLine(int(points[idx][0]), int(points[idx][1]), int(points[idx + 1][0]), int(points[idx + 1][1]))

        painter.setPen(QPen(QColor("#4f7cff"), 1.4))
        painter.setBrush(QColor("#ffffff"))
        for x, y in points:
            painter.drawEllipse(int(x) - 3, int(y) - 3, 6, 6)

        painter.setPen(QPen(QColor("#8a99b6")))
        for idx, text in enumerate(labels):
            x = rect.left() + rect.width() * idx / max(len(labels) - 1, 1)
            painter.drawText(int(x) - 18, rect.bottom() + 18, text)


class _OverviewMetricCard(QFrame):
    def __init__(self, title: str, value: str, accent: str | None = None) -> None:
        super().__init__()
        self.setObjectName("BlueprintMetricCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)
        title_label = QLabel(title)
        title_label.setObjectName("BlueprintMuted")
        value_label = QLabel(value)
        value_label.setObjectName("BlueprintCardValue")
        if accent:
            value_label.setStyleSheet(f"color: {accent};")
        layout.addWidget(title_label)
        layout.addWidget(value_label)


class BlueprintWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("草莓订单管理系统 UI 蓝图预览")
        self.resize(1540, 980)

        shell = QFrame()
        shell.setObjectName("BlueprintShell")

        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)

        title_bar = QFrame()
        title_bar.setObjectName("BlueprintTitleBar")
        title_bar_layout = QHBoxLayout(title_bar)
        title_bar_layout.setContentsMargins(16, 10, 16, 10)
        title_bar_layout.setSpacing(12)
        title_bar_layout.addWidget(_TrafficLights(), 0, Qt.AlignmentFlag.AlignLeft)
        title = QLabel("草莓订单管理系统 · UI 蓝图预览")
        title.setObjectName("BlueprintMuted")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_bar_layout.addWidget(title, 1)
        title_bar_layout.addSpacing(54)
        shell_layout.addWidget(title_bar)

        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("BlueprintSidebar")
        sidebar.setFixedWidth(208)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(20, 18, 20, 18)
        sidebar_layout.setSpacing(14)
        brand = QLabel("草莓")
        brand.setObjectName("BlueprintBrandTitle")
        subtitle = QLabel("订单管理系统")
        subtitle.setObjectName("BlueprintBrandSubtitle")
        sidebar_layout.addWidget(brand)
        sidebar_layout.addWidget(subtitle)
        self.nav = QListWidget()
        self.nav.setObjectName("BlueprintNav")
        for label in ("订单录入", "历史订单", "财务报表", "设置"):
            QListWidgetItem(label, self.nav)
        self.nav.setCurrentRow(0)
        sidebar_layout.addWidget(self.nav, 1)
        body_layout.addWidget(sidebar)

        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_entry_page())
        self.stack.addWidget(self._build_history_page())
        self.stack.addWidget(self._build_profit_page())
        self.stack.addWidget(self._build_settings_page())
        body_layout.addWidget(self.stack, 1)

        shell_layout.addWidget(body, 1)
        self.setCentralWidget(shell)
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.setStyleSheet(BLUEPRINT_STYLESHEET)

    def _wrap_page(self, title_text: str, subtitle_text: str, content: QWidget) -> QWidget:
        page = QWidget()
        page.setObjectName("BlueprintPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)
        title = QLabel(title_text)
        title.setObjectName("BlueprintPageTitle")
        subtitle = QLabel(subtitle_text)
        subtitle.setObjectName("BlueprintMuted")
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(content, 1)
        return page

    def _sticky_bar(self, left: QWidget, right: QWidget) -> QFrame:
        bar = QFrame()
        bar.setObjectName("BlueprintStickyBar")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)
        layout.addWidget(left, 1)
        layout.addWidget(right, 0)
        return bar

    def _build_entry_page(self) -> QWidget:
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(12)

        left_controls = QWidget()
        left_controls_layout = QHBoxLayout(left_controls)
        left_controls_layout.setContentsMargins(0, 0, 0, 0)
        left_controls_layout.setSpacing(10)
        left_controls_layout.addWidget(QLabel("店铺"))
        shop = QComboBox()
        shop.addItems(["乐宝零食店", "欢宝零食店", "灵宝零食店"])
        left_controls_layout.addWidget(shop)
        left_controls_layout.addSpacing(8)
        left_controls_layout.addWidget(QLabel("平台"))
        platform = QComboBox()
        platform.addItems(["抖店", "微信小店"])
        left_controls_layout.addWidget(platform)

        right_actions = QWidget()
        right_actions_layout = QHBoxLayout(right_actions)
        right_actions_layout.setContentsMargins(0, 0, 0, 0)
        right_actions_layout.setSpacing(8)
        save_history = QPushButton("仅存历史")
        save_history.setObjectName("GhostButton")
        submit = QPushButton("确认写入飞书")
        right_actions_layout.addWidget(save_history)
        right_actions_layout.addWidget(submit)

        content_layout.addWidget(self._sticky_bar(left_controls, right_actions))

        workspace = QWidget()
        workspace_layout = QHBoxLayout(workspace)
        workspace_layout.setContentsMargins(0, 0, 0, 0)
        workspace_layout.setSpacing(14)

        left_col = QWidget()
        left_col.setObjectName("BlueprintEntryLeftRail")
        left_col.setFixedWidth(300)
        left_col_layout = QVBoxLayout(left_col)
        left_col_layout.setContentsMargins(0, 0, 0, 0)
        left_col_layout.setSpacing(12)

        capture_card, capture_layout = _make_card("拍单识别", "支持粘贴截图、拖拽图片或选择图片，识别后自动生成订单卡。")
        capture_buttons = QWidget()
        capture_buttons_layout = QHBoxLayout(capture_buttons)
        capture_buttons_layout.setContentsMargins(0, 0, 0, 0)
        capture_buttons_layout.setSpacing(8)
        capture_buttons_layout.addWidget(QPushButton("粘贴截图"))
        capture_buttons_layout.addWidget(QPushButton("选择图片"))
        capture_layout.addWidget(capture_buttons)
        waiting = QFrame()
        waiting.setObjectName("BlueprintCard")
        waiting.setMinimumHeight(138)
        waiting_layout = QVBoxLayout(waiting)
        waiting_layout.addStretch(1)
        waiting_layout.addWidget(QLabel("等待截图"), 0, Qt.AlignmentFlag.AlignCenter)
        waiting_layout.addStretch(1)
        capture_layout.addWidget(waiting)

        extractor_card, extractor_layout = _make_card("文本提取", "左侧负责输入、提取和复制，不与主录单表单混在一起。")
        extractor_layout.addWidget(_text("", height=120))
        extractor_layout.addWidget(QPushButton("一键提取"))
        result_one = _text("何女士15781304332四川省成都市金牛区营门口街道友谊花园9-2304", height=72)
        result_one.setReadOnly(True)
        result_two = _text("请电话送货上门谢谢【3612】", height=64)
        result_two.setReadOnly(True)
        extractor_layout.addWidget(QLabel("提取结果一"))
        extractor_layout.addWidget(result_one)
        extractor_layout.addWidget(QLabel("提取结果二"))
        extractor_layout.addWidget(result_two)

        left_col_layout.addWidget(capture_card)
        left_col_layout.addWidget(extractor_card, 1)

        center_scroll = QScrollArea()
        center_scroll.setObjectName("BlueprintEntryFormRail")
        center_scroll.setWidgetResizable(True)
        center_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        center_widget = QWidget()
        center_layout = QVBoxLayout(center_widget)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(12)

        order_card, order_layout = _make_card("订单概览", "编号、状态和金额放在一起，减少纵向滚动。")
        order_grid = QGridLayout()
        order_grid.setContentsMargins(0, 0, 0, 0)
        order_grid.setHorizontalSpacing(12)
        order_grid.setVerticalSpacing(10)
        for row, (label, editor, col, span) in enumerate(
            [
                ("下单时间", _input("2026-04-11 20:57:15"), 0, 1),
                ("订单状态", QComboBox(), 1, 1),
                ("数量", _input("1"), 0, 1),
                ("订单金额", _input("405.00"), 1, 1),
            ]
        ):
            if isinstance(editor, QComboBox):
                editor.addItems(["已发货", "待发货", "已拍单未发货"])
            field, _ = _field(label, editor)
            order_grid.addWidget(field, row // 2, col, 1, span)
        product_field, _ = _field("商品名称", _text("【明日达】赵露思同款27000澳大利亚进口婴儿水宝宝水高端矿泉水", height=74))
        spec_field, _ = _field("规格", _input("1L/瓶*12袋(赵露思同款 澳洲版)"))
        sku_image = QFrame()
        sku_image.setObjectName("BlueprintCard")
        sku_image.setMinimumHeight(92)
        sku_image_layout = QVBoxLayout(sku_image)
        sku_image_layout.addStretch(1)
        sku_image_layout.addWidget(QLabel("SKU 图片区域"), 0, Qt.AlignmentFlag.AlignCenter)
        sku_image_layout.addStretch(1)
        sku_field, _ = _field("SKU 图片", sku_image)
        income_field, _ = _field("商家收入", _input("162.00"))
        order_grid.addWidget(product_field, 2, 0, 1, 2)
        order_grid.addWidget(spec_field, 3, 0, 1, 2)
        order_grid.addWidget(sku_field, 4, 0, 1, 1)
        order_grid.addWidget(income_field, 4, 1, 1, 1)
        order_layout.addLayout(order_grid)

        shipping_card, shipping_layout = _make_card("收件信息", "收件人、电话、地址与备注单独收拢。")
        shipping_grid = QGridLayout()
        shipping_grid.setContentsMargins(0, 0, 0, 0)
        shipping_grid.setHorizontalSpacing(12)
        shipping_grid.setVerticalSpacing(10)
        shipping_items = [
            ("收件人", _input("何女士"), 0, 0, 1, 1),
            ("手机号", _input("15781304332"), 0, 1, 1, 1),
            ("编号", _input("3612"), 1, 0, 1, 1),
            ("收货地址", _text("四川省成都市金牛区营门口街道友谊花园9-2304", height=82), 1, 1, 2, 1),
            ("备注", _text("", height=70), 2, 0, 1, 1),
        ]
        for label, editor, row, col, row_span, col_span in shipping_items:
            field, _ = _field(label, editor)
            shipping_grid.addWidget(field, row, col, row_span, col_span)
        shipping_layout.addLayout(shipping_grid)

        procurement_card, procurement_layout = _make_card("采购信息", "采购槽位压缩为更紧凑横向布局，减少页面高度。")
        for index, name in enumerate(["采购1", "采购2", "采购3"], start=1):
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(8)
            tag = QLabel(name)
            tag.setObjectName("BlueprintMuted")
            combo = QComboBox()
            combo.addItems(["", "27000-澳洲版-1升装", "康兴-瓶盖-粉色"])
            combo.setCurrentText("27000-澳洲版-1升装" if index == 1 else "")
            qty = _input("1" if index == 1 else "")
            cost = _input("109" if index == 1 else "")
            action = QPushButton("入库")
            action.setObjectName("GhostButton")
            row_layout.addWidget(tag)
            row_layout.addWidget(combo, 2)
            row_layout.addWidget(qty, 1)
            row_layout.addWidget(cost, 1)
            row_layout.addWidget(action)
            procurement_layout.addWidget(row)

        finance_card, finance_layout = _make_card("财务信息", "补平台扣点、自定义成本，并自动计算采购总成本和毛利润。")
        finance_grid = QGridLayout()
        finance_grid.setContentsMargins(0, 0, 0, 0)
        finance_grid.setHorizontalSpacing(12)
        finance_grid.setVerticalSpacing(10)
        finance_pairs = [
            ("平台扣点比例", _input("0.06")),
            ("平台扣点金额", _input("9.72")),
            ("其他成本", _input("")),
            ("采购总成本", _input("122.80")),
            ("毛利润", _input("29.48")),
        ]
        for idx, (label, editor) in enumerate(finance_pairs):
            field, _ = _field(label, editor)
            if idx < 4:
                finance_grid.addWidget(field, idx // 2, idx % 2)
            else:
                finance_grid.addWidget(field, 2, 0, 1, 2)
        finance_layout.addLayout(finance_grid)

        center_layout.addWidget(order_card)
        center_layout.addWidget(shipping_card)
        center_layout.addWidget(procurement_card)
        center_layout.addWidget(finance_card)
        center_layout.addStretch(1)
        center_scroll.setWidget(center_widget)

        right_col = QWidget()
        right_col.setObjectName("BlueprintEntryResultRail")
        right_col.setFixedWidth(300)
        right_col_layout = QVBoxLayout(right_col)
        right_col_layout.setContentsMargins(0, 0, 0, 0)
        right_col_layout.setSpacing(12)
        support_card, support_layout = _make_card("提取结果", "右侧单独承载地址提取和识别反馈，主录单区更专注。")
        sync_box = _text("已同步订单地址结果", height=140)
        sync_box.setReadOnly(True)
        support_layout.addWidget(QLabel("结果一"))
        support_layout.addWidget(_text("何女士15781304332四川省成都市金牛区营门口街道友谊花园9-2304", height=84))
        support_layout.addWidget(QLabel("结果二"))
        support_layout.addWidget(_text("请电话送货上门谢谢【3612】", height=74))
        support_layout.addWidget(sync_box)
        right_col_layout.addWidget(support_card, 1)

        workspace_layout.addWidget(left_col)
        workspace_layout.addWidget(center_scroll, 1)
        workspace_layout.addWidget(right_col)
        content_layout.addWidget(workspace, 1)

        return self._wrap_page("订单录入蓝图", "三栏工作台：左提取、中录单、右结果。这里先只展示新 UI 架构，不接管正式业务页。", content)

    def _build_history_page(self) -> QWidget:
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(12)

        filter_left = QWidget()
        filter_left_layout = QHBoxLayout(filter_left)
        filter_left_layout.setContentsMargins(0, 0, 0, 0)
        filter_left_layout.setSpacing(8)
        for label in ("今天", "昨天", "近7天", "全部"):
            button = QPushButton(label)
            button.setObjectName("GhostButton")
            filter_left_layout.addWidget(button)
        search = _input()
        search.setPlaceholderText("搜订单号 / 收件人 / 手机号 / 快递单号")
        filter_left_layout.addWidget(search, 1)
        filter_left_layout.addWidget(QLabel("日期"))
        date_combo = QComboBox()
        date_combo.addItems(["2026-04-14"])
        filter_left_layout.addWidget(date_combo)
        filter_left_layout.addWidget(QLabel("店铺"))
        shop_combo = QComboBox()
        shop_combo.addItems(["全部店铺", "乐宝零食店", "欢宝零食店"])
        filter_left_layout.addWidget(shop_combo)
        filter_left_layout.addWidget(QLabel("状态"))
        status_combo = QComboBox()
        status_combo.addItems(["全部状态", "已发货", "待发货", "已拍单未发货"])
        filter_left_layout.addWidget(status_combo)

        filter_actions = QWidget()
        filter_actions_layout = QHBoxLayout(filter_actions)
        filter_actions_layout.setContentsMargins(0, 0, 0, 0)
        filter_actions_layout.setSpacing(8)
        filter_actions_layout.addWidget(QPushButton("应用筛选"))
        clear_button = QPushButton("清空")
        clear_button.setObjectName("GhostButton")
        filter_actions_layout.addWidget(clear_button)

        content_layout.addWidget(self._sticky_bar(filter_left, filter_actions))

        kpi_row = QWidget()
        kpi_layout = QGridLayout(kpi_row)
        kpi_layout.setContentsMargins(0, 0, 0, 0)
        kpi_layout.setHorizontalSpacing(10)
        for idx, (title, value) in enumerate([("全部订单", "10"), ("已发货", "10"), ("待发货", "0"), ("已拍单未发货", "0")]):
            kpi_layout.addWidget(_OverviewMetricCard(title, value), 0, idx)
        content_layout.addWidget(kpi_row)

        workspace = QWidget()
        workspace_layout = QHBoxLayout(workspace)
        workspace_layout.setContentsMargins(0, 0, 0, 0)
        workspace_layout.setSpacing(12)

        master = QFrame()
        master.setObjectName("BlueprintHistoryMasterPane")
        master.setFixedWidth(340)
        master_layout = QVBoxLayout(master)
        master_layout.setContentsMargins(0, 0, 0, 0)
        master_layout.setSpacing(0)
        master_top = QLabel("共 10 条记录")
        master_top.setObjectName("BlueprintMuted")
        master_top.setContentsMargins(14, 12, 14, 12)
        master_layout.addWidget(master_top)
        master_list = QListWidget()
        master_list.setObjectName("BlueprintMasterList")
        for text in (
            "君宝零食店 · 彭柏棋 · 已写入飞书 · 695190981...",
            "君宝零食店 · 狗屎 · 已写入飞书 · 692549595...",
            "乐宝零食店 · 何女士 · 已写入飞书 · 695200343...",
        ):
            QListWidgetItem(text, master_list)
        master_list.setCurrentRow(0)
        master_layout.addWidget(master_list, 1)

        detail_scroll = QScrollArea()
        detail_scroll.setObjectName("BlueprintHistoryDetailPane")
        detail_scroll.setWidgetResizable(True)
        detail_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        detail_body = QWidget()
        detail_layout = QVBoxLayout(detail_body)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        detail_layout.setSpacing(12)

        detail_header_left = QWidget()
        detail_header_left_layout = QVBoxLayout(detail_header_left)
        detail_header_left_layout.setContentsMargins(0, 0, 0, 0)
        detail_header_left_layout.setSpacing(2)
        detail_header_left_layout.addWidget(QLabel("君宝零食店"))
        detail_header_left_layout.itemAt(0).widget().setObjectName("BlueprintPageTitle")
        subtitle = QLabel("确认写入飞书 · 已写入飞书")
        subtitle.setObjectName("BlueprintMuted")
        detail_header_left_layout.addWidget(subtitle)

        detail_header_right = QWidget()
        detail_header_right_layout = QHBoxLayout(detail_header_right)
        detail_header_right_layout.setContentsMargins(0, 0, 0, 0)
        detail_header_right_layout.setSpacing(8)
        save_button = QPushButton("保存修改并重新写入飞书")
        save_button.setObjectName("GhostButton")
        delete_button = QPushButton("删除")
        delete_button.setObjectName("DangerButton")
        detail_header_right_layout.addWidget(save_button)
        detail_header_right_layout.addWidget(delete_button)
        detail_layout.addWidget(self._sticky_bar(detail_header_left, detail_header_right))

        summary_row = QWidget()
        summary_layout = QGridLayout(summary_row)
        summary_layout.setContentsMargins(0, 0, 0, 0)
        summary_layout.setHorizontalSpacing(10)
        summary_layout.addWidget(_OverviewMetricCard("收入", "122.00"), 0, 0)
        summary_layout.addWidget(_OverviewMetricCard("订单金额", "305.00"), 0, 1)
        summary_layout.addWidget(_OverviewMetricCard("商品概要", "【明日达】赵露丝同款27000...", accent="#1f2a44"), 0, 2)
        summary_layout.addWidget(_OverviewMetricCard("采购概要", "27000-国产版-1升装 / 1 / 89", accent="#1f2a44"), 0, 3)
        detail_layout.addWidget(summary_row)

        detail_grid = QGridLayout()
        detail_grid.setContentsMargins(0, 0, 0, 0)
        detail_grid.setHorizontalSpacing(12)
        detail_grid.setVerticalSpacing(12)

        left_card, left_layout = _make_card("订单基础信息")
        left_grid = QGridLayout()
        left_grid.setContentsMargins(0, 0, 0, 0)
        left_grid.setHorizontalSpacing(10)
        left_grid.setVerticalSpacing(10)
        base_fields = [
            ("订单编号", _input("6951909811798676570"), 0, 0, 1, 2),
            ("下单时间", _input("2026-04-08 18:02:10"), 1, 0, 1, 2),
            ("平台", _input("抖音"), 2, 0, 1, 1),
            ("订单状态", QComboBox(), 2, 1, 1, 1),
            ("商品名称", _text("【明日达】赵露丝同款27000澳大利亚进口婴儿水宝宝水高端矿泉水", height=70), 3, 0, 1, 2),
            ("规格", _input("1L/瓶*12瓶(赵露丝同款)x1"), 4, 0, 1, 2),
            ("SKU 图片", QLabel("SKU 图片预览"), 5, 0, 1, 2),
            ("数量", _input("1"), 6, 0, 1, 1),
            ("订单金额", _input("305.00"), 6, 1, 1, 1),
            ("收入", _input("122.00"), 7, 0, 1, 1),
            ("收件人", _input("彭柏棋"), 7, 1, 1, 1),
            ("手机号", _input("15781259851"), 8, 0, 1, 1),
            ("编号", _input("5857"), 8, 1, 1, 1),
            ("收货地址", _text("浙江省嘉兴市嘉善县魏塘街道 解放东路龙光·玖宸佳苑8号楼602室", height=70), 9, 0, 1, 2),
            ("备注", _text("", height=64), 10, 0, 1, 2),
        ]
        for label, editor, row, col, row_span, col_span in base_fields:
            if isinstance(editor, QComboBox):
                editor.addItems(["已发货", "待发货", "已拍单未发货"])
            if isinstance(editor, QLabel):
                editor.setObjectName("BlueprintMuted")
                editor.setAlignment(Qt.AlignmentFlag.AlignCenter)
                preview = QFrame()
                preview.setObjectName("BlueprintCard")
                preview_layout = QVBoxLayout(preview)
                preview_layout.setContentsMargins(0, 20, 0, 20)
                preview_layout.addWidget(editor)
                field, _ = _field(label, preview)
            else:
                field, _ = _field(label, editor)
            left_grid.addWidget(field, row, col, row_span, col_span)
        left_layout.addLayout(left_grid)

        right_card, right_layout = _make_card("采购 / 财务 / 地址 / 同步")
        right_grid = QGridLayout()
        right_grid.setContentsMargins(0, 0, 0, 0)
        right_grid.setHorizontalSpacing(10)
        right_grid.setVerticalSpacing(10)
        purchase_fields = [
            ("采购 1 商品", QComboBox()),
            ("采购 1 数量", _input("1")),
            ("采购 1 成本", _input("89")),
            ("采购 1 快递单号", _input("")),
            ("采购 2 商品", QComboBox()),
            ("采购 2 数量", _input("")),
            ("采购 2 成本", _input("")),
            ("采购 2 快递单号", _input("")),
            ("采购 3 商品", QComboBox()),
            ("采购 3 数量", _input("")),
            ("采购 3 成本", _input("")),
            ("采购 3 快递单号", _input("")),
            ("平台扣点比例", _input("0.06")),
            ("平台扣点金额", _input("7.32")),
            ("其他成本", _input("")),
            ("采购总成本", _input("89.00")),
            ("毛利润", _input("25.68")),
            ("结果一", _text("彭柏棋15781259851浙江省嘉兴市嘉善县魏塘街道解放东路龙光·玖宸佳苑8号楼602室", height=70)),
            ("结果二", _text("请电话送货上门谢谢【5857】", height=64)),
            ("同步方式", _input("确认写入飞书")),
            ("当前状态", _input("已写入飞书")),
            ("最后状态说明", _input("写入成功")),
        ]
        for idx, (label, editor) in enumerate(purchase_fields):
            if isinstance(editor, QComboBox):
                editor.addItems(["", "27000-国产版-1升装", "康兴-瓶盖-粉色"])
            field, _ = _field(label, editor)
            if label in {"结果一", "结果二", "毛利润"}:
                right_grid.addWidget(field, idx, 0, 1, 2)
            else:
                row = idx // 2
                col = idx % 2
                right_grid.addWidget(field, row, col)
        right_layout.addLayout(right_grid)

        detail_grid.addWidget(left_card, 0, 0)
        detail_grid.addWidget(right_card, 0, 1)
        detail_layout.addLayout(detail_grid)
        detail_layout.addStretch(1)
        detail_scroll.setWidget(detail_body)

        workspace_layout.addWidget(master)
        workspace_layout.addWidget(detail_scroll, 1)
        content_layout.addWidget(workspace, 1)

        return self._wrap_page("历史工作台蓝图", "主从结构、吸顶筛选和右侧详情摘要都独立出来，避免巨型长表单。", content)

    def _build_profit_page(self) -> QWidget:
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(12)

        top = QWidget()
        top_layout = QHBoxLayout(top)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(10)
        segment = QFrame()
        segment.setObjectName("BlueprintSegmentWrap")
        segment_layout = QHBoxLayout(segment)
        segment_layout.setContentsMargins(6, 6, 6, 6)
        segment_layout.setSpacing(6)
        overview_btn = QToolButton()
        overview_btn.setText("大盘概览")
        overview_btn.setCheckable(True)
        overview_btn.setChecked(True)
        daily_btn = QToolButton()
        daily_btn.setText("每日账目明细")
        daily_btn.setCheckable(True)
        group = QButtonGroup(self)
        group.setExclusive(True)
        group.addButton(overview_btn, 0)
        group.addButton(daily_btn, 1)
        for button in (overview_btn, daily_btn):
            button.setAutoRaise(False)
            button.setObjectName("GhostButton")
            segment_layout.addWidget(button)
        top_layout.addWidget(segment)
        top_layout.addStretch(1)
        top_layout.addWidget(QLabel("结算月份"))
        month = QComboBox()
        month.addItems(["2026-04", "2026-03"])
        top_layout.addWidget(month)
        content_layout.addWidget(self._sticky_bar(top, QWidget()))

        profit_tabs = QStackedWidget()
        profit_tabs.setObjectName("BlueprintProfitTabs")

        overview_view = QWidget()
        overview_layout = QVBoxLayout(overview_view)
        overview_layout.setContentsMargins(0, 0, 0, 0)
        overview_layout.setSpacing(12)
        metrics = QWidget()
        metrics_layout = QGridLayout(metrics)
        metrics_layout.setContentsMargins(0, 0, 0, 0)
        metrics_layout.setHorizontalSpacing(10)
        metrics_layout.setVerticalSpacing(10)
        metric_defs = [
            ("月毛利润", "272.00", "#10b981"),
            ("利润率", "18.63%", "#2563eb"),
            ("总收入", "1460.00", None),
            ("订单数", "10", None),
            ("总支出", "1188.00", None),
            ("出单店铺", "2", None),
        ]
        for idx, (title, value, accent) in enumerate(metric_defs):
            metrics_layout.addWidget(_OverviewMetricCard(title, value, accent), 0, idx)
        overview_layout.addWidget(metrics)

        trend_card, trend_layout = _make_card("收入趋势", "默认看收入，可切换到毛利润和支出。保留 hover 提示与竖向辅助线的预期位置。")
        trend_header = QWidget()
        trend_header_layout = QHBoxLayout(trend_header)
        trend_header_layout.setContentsMargins(0, 0, 0, 0)
        trend_header_layout.setSpacing(8)
        trend_header_layout.addStretch(1)
        trend_header_layout.addWidget(QLabel("指标"))
        metric_switch = QComboBox()
        metric_switch.setObjectName("BlueprintTrendMetricCombo")
        metric_switch.addItems(["收入", "毛利润", "支出"])
        trend_header_layout.addWidget(metric_switch)
        trend_layout.addWidget(trend_header)
        trend_layout.addWidget(_TrendPreview())
        overview_layout.addWidget(trend_card)

        lower = QWidget()
        lower_layout = QGridLayout(lower)
        lower_layout.setContentsMargins(0, 0, 0, 0)
        lower_layout.setHorizontalSpacing(12)
        lower_layout.setVerticalSpacing(12)
        blocks = [
            ("同比 / 环比", ["环比毛利：--", "同比毛利：--"]),
            ("支出构成", ["平台扣点金额：87.60", "采购总成本：1100.40", "其他成本：0.00"]),
            ("店铺利润排行", ["1. 乐宝零食店 毛利 220.64 利润率 18.14%", "2. 君宝零食店 毛利 51.36 利润率 21.05%"]),
            ("订单状态", ["已发货：10", "待发货：0", "已拍单未发货：0"]),
        ]
        for idx, (title, lines) in enumerate(blocks):
            card, card_layout = _make_card(title)
            for line in lines:
                label = QLabel(line)
                label.setWordWrap(True)
                card_layout.addWidget(label)
            lower_layout.addWidget(card, idx // 2, idx % 2)
        overview_layout.addWidget(lower)
        overview_layout.addStretch(1)
        profit_tabs.addWidget(overview_view)

        daily_view = QWidget()
        daily_layout = QVBoxLayout(daily_view)
        daily_layout.setContentsMargins(0, 0, 0, 0)
        daily_layout.setSpacing(12)
        filter_card, filter_card_layout = _make_card("每日筛选")
        filter_row = QHBoxLayout()
        filter_row.setContentsMargins(0, 0, 0, 0)
        filter_row.setSpacing(8)
        for label, items in (
            ("月份", ["2026-04"]),
            ("店铺", ["全部店铺", "乐宝零食店"]),
            ("平台", ["全部平台", "抖店", "微信小店"]),
            ("状态", ["全部状态", "已发货", "待发货"]),
        ):
            wrap = QWidget()
            wrap_layout = QVBoxLayout(wrap)
            wrap_layout.setContentsMargins(0, 0, 0, 0)
            wrap_layout.setSpacing(4)
            lab = QLabel(label)
            lab.setObjectName("BlueprintFieldLabel")
            combo = QComboBox()
            combo.addItems(items)
            wrap_layout.addWidget(lab)
            wrap_layout.addWidget(combo)
            filter_row.addWidget(wrap)
        filter_card_layout.addLayout(filter_row)
        daily_layout.addWidget(filter_card)
        for title, shop, income, expense, profit, margin in (
            ("2026-04-13", "乐宝零食店", "466.00", "396.36", "69.64", "14.94%"),
            ("2026-04-13", "欢宝零食店", "0.00", "0.00", "0.00", "--"),
        ):
            row_card = QFrame()
            row_card.setObjectName("BlueprintCard")
            row_layout = QVBoxLayout(row_card)
            row_layout.setContentsMargins(16, 14, 16, 16)
            row_layout.setSpacing(10)
            header = QHBoxLayout()
            header.setContentsMargins(0, 0, 0, 0)
            header.addWidget(QLabel(title))
            header.addSpacing(16)
            header.addWidget(QLabel(shop))
            header.addStretch(1)
            expand = QPushButton("展开明细")
            expand.setObjectName("GhostButton")
            header.addWidget(expand)
            row_layout.addLayout(header)
            metrics_row = QGridLayout()
            metrics_row.setContentsMargins(0, 0, 0, 0)
            metrics_row.setHorizontalSpacing(14)
            for idx, (label, value) in enumerate([("总收入", income), ("总支出", expense), ("毛利", profit), ("利润率", margin)]):
                chip = QFrame()
                chip.setObjectName("BlueprintKpiStrip")
                chip_layout = QVBoxLayout(chip)
                chip_layout.setContentsMargins(12, 10, 12, 10)
                chip_layout.addWidget(QLabel(label))
                value_label = QLabel(value)
                value_label.setObjectName("BlueprintSectionTitle")
                chip_layout.addWidget(value_label)
                metrics_row.addWidget(chip, 0, idx)
            row_layout.addLayout(metrics_row)
            detail_row = QGridLayout()
            detail_row.setContentsMargins(0, 0, 0, 0)
            detail_row.setHorizontalSpacing(12)
            income_card, income_layout = _make_card("收入明细")
            for line in ("单店总收入：466.00", "货款收入：466.00"):
                income_layout.addWidget(QLabel(line))
            expense_card, expense_layout = _make_card("支出明细")
            for line in ("单店总支出：396.36", "商品支出：388.64", "平台扣点：7.72", "人工成本：0.00"):
                expense_layout.addWidget(QLabel(line))
            detail_row.addWidget(income_card, 0, 0)
            detail_row.addWidget(expense_card, 0, 1)
            row_layout.addLayout(detail_row)
            daily_layout.addWidget(row_card)
        daily_layout.addStretch(1)
        profit_tabs.addWidget(daily_view)

        group.idClicked.connect(profit_tabs.setCurrentIndex)
        content_layout.addWidget(profit_tabs, 1)

        return self._wrap_page("利润计算蓝图", "大盘和每日账目明细拆成双 Tab 工作台，先看驾驶舱，再看分日条目。", content)

    def _build_settings_page(self) -> QWidget:
        content = QWidget()
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(14)

        subnav = QFrame()
        subnav.setObjectName("BlueprintListCard")
        subnav.setFixedWidth(180)
        subnav_layout = QVBoxLayout(subnav)
        subnav_layout.setContentsMargins(14, 14, 14, 14)
        subnav_layout.setSpacing(10)
        nav_title = QLabel("设置中心")
        nav_title.setObjectName("BlueprintSectionTitle")
        subnav_layout.addWidget(nav_title)
        subnav_list = QListWidget()
        subnav_list.setObjectName("BlueprintSettingsSubnav")
        for label in ("接口配置", "商品库", "店铺映射", "更新日志"):
            QListWidgetItem(label, subnav_list)
        subnav_list.setCurrentRow(2)
        subnav_layout.addWidget(subnav_list, 1)

        settings_stack = QStackedWidget()
        settings_stack.setObjectName("BlueprintSettingsStack")

        api_page = QWidget()
        api_layout = QVBoxLayout(api_page)
        api_layout.setContentsMargins(0, 0, 0, 0)
        api_layout.setSpacing(12)
        api_header = self._sticky_bar(QLabel("接口配置"), QPushButton("保存/应用"))
        api_layout.addWidget(api_header)
        api_card, api_card_layout = _make_card("基础参数")
        api_form = QGridLayout()
        api_form.setContentsMargins(0, 0, 0, 0)
        api_form.setHorizontalSpacing(12)
        api_form.setVerticalSpacing(10)
        api_fields = [
            ("使用 MCP OCR", QComboBox()),
            ("MCP 命令", _input("uvx minimax-coding-plan-mcp -y")),
            ("OCR API Base URL", _input("https://api.minimaxi.com/v1")),
            ("OCR API Key", _input("sk-***")),
            ("辅助提取 API Base URL", _input("https://api.minimaxi.com/v1")),
            ("辅助提取 API Key", _input("sk-***")),
            ("飞书 App ID", _input("cli_xxx")),
            ("飞书 App Secret", _input("***")),
        ]
        for idx, (label, editor) in enumerate(api_fields):
            if isinstance(editor, QComboBox):
                editor.addItems(["启用", "关闭"])
            field, _ = _field(label, editor)
            api_form.addWidget(field, idx // 2, idx % 2)
        api_card_layout.addLayout(api_form)
        api_layout.addWidget(api_card)
        api_layout.addStretch(1)
        settings_stack.addWidget(api_page)

        goods_page = QWidget()
        goods_layout = QVBoxLayout(goods_page)
        goods_layout.setContentsMargins(0, 0, 0, 0)
        goods_layout.setSpacing(12)
        goods_layout.addWidget(self._sticky_bar(QLabel("商品库"), QPushButton("保存商品")))
        goods_card, goods_card_layout = _make_card("全局商品库")
        goods_form = QGridLayout()
        goods_form.setContentsMargins(0, 0, 0, 0)
        goods_form.setHorizontalSpacing(12)
        goods_form.setVerticalSpacing(10)
        goods_fields = [
            ("已保存商品", QComboBox()),
            ("商品名称", _input("27000-澳洲版-1升装")),
            ("默认成本", _input("109")),
            ("自定义字段1", _input("")),
            ("自定义字段2", _input("")),
            ("自定义字段3", _input("")),
        ]
        for idx, (label, editor) in enumerate(goods_fields):
            if isinstance(editor, QComboBox):
                editor.addItems(["27000-澳洲版-1升装", "康兴-瓶盖-粉色"])
            field, _ = _field(label, editor)
            goods_form.addWidget(field, idx // 2, idx % 2)
        goods_buttons = QWidget()
        goods_buttons_layout = QHBoxLayout(goods_buttons)
        goods_buttons_layout.setContentsMargins(0, 0, 0, 0)
        goods_buttons_layout.setSpacing(8)
        for text in ("新增商品", "保存商品", "删除商品"):
            goods_buttons_layout.addWidget(QPushButton(text))
        goods_card_layout.addLayout(goods_form)
        goods_card_layout.addWidget(goods_buttons)
        goods_layout.addWidget(goods_card)
        goods_layout.addStretch(1)
        settings_stack.addWidget(goods_page)

        mapping_page = QWidget()
        mapping_layout = QVBoxLayout(mapping_page)
        mapping_layout.setContentsMargins(0, 0, 0, 0)
        mapping_layout.setSpacing(12)
        header_left = QLabel("店铺与 Sheet 映射")
        header_right = QWidget()
        header_right_layout = QHBoxLayout(header_right)
        header_right_layout.setContentsMargins(0, 0, 0, 0)
        header_right_layout.setSpacing(8)
        for text in ("新增店铺", "保存店铺", "检测总表字段", "删除店铺"):
            button = QPushButton(text)
            if text != "检测总表字段":
                button.setObjectName("GhostButton")
            header_right_layout.addWidget(button)
        mapping_layout.addWidget(self._sticky_bar(header_left, header_right))
        base_card, base_card_layout = _make_card("总表基础信息")
        base_grid = QGridLayout()
        base_grid.setContentsMargins(0, 0, 0, 0)
        base_grid.setHorizontalSpacing(12)
        base_grid.setVerticalSpacing(10)
        base_fields = [
            ("已保存店铺", QComboBox()),
            ("店铺名称", _input("乐宝零食店")),
            ("总表链接", _input("view5iZdMqj")),
            ("总表 App Token", _input("gs15macOmDcnbf")),
            ("总表 Table ID", _input("iWZDrx4gqXpc5M")),
            ("总表备注", _input("乐宝零食店")),
        ]
        for idx, (label, editor) in enumerate(base_fields):
            if isinstance(editor, QComboBox):
                editor.addItems(["乐宝零食店", "欢宝零食店"])
            field, _ = _field(label, editor)
            base_grid.addWidget(field, idx // 2, idx % 2)
        base_card_layout.addLayout(base_grid)
        mapping_layout.addWidget(base_card)
        mapping_card, mapping_card_layout = _make_card("字段映射（三列压缩版）")
        mapping_grid = QGridLayout()
        mapping_grid.setContentsMargins(0, 0, 0, 0)
        mapping_grid.setHorizontalSpacing(12)
        mapping_grid.setVerticalSpacing(10)
        mapping_fields = [
            "店铺", "订单编号", "订单日期", "订单状态", "规格", "SKU 图片",
            "平台", "备注", "下单时间", "商品名称", "数量", "收入",
            "发货地址", "采购快递单号1", "采购快递单号2", "采购快递单号3",
            "平台扣点比例", "平台扣点金额", "其他成本", "采购总成本", "毛利润",
            "采购商品1", "采购数量1", "采购成本1", "采购商品2", "采购数量2", "采购成本2",
            "采购商品3", "采购数量3", "采购成本3",
        ]
        for idx, label in enumerate(mapping_fields):
            field, _ = _field(f"{label} 映射", _input(label))
            mapping_grid.addWidget(field, idx // 3, idx % 3)
        mapping_card_layout.addLayout(mapping_grid)
        mapping_layout.addWidget(mapping_card)
        mapping_layout.addStretch(1)
        settings_stack.addWidget(mapping_page)

        logs_page = QWidget()
        logs_layout = QHBoxLayout(logs_page)
        logs_layout.setContentsMargins(0, 0, 0, 0)
        logs_layout.setSpacing(12)
        logs_master = QFrame()
        logs_master.setObjectName("BlueprintListCard")
        logs_master.setFixedWidth(340)
        logs_master_layout = QVBoxLayout(logs_master)
        logs_master_layout.setContentsMargins(0, 0, 0, 0)
        logs_master_layout.setSpacing(0)
        logs_title = QLabel("开发更新记录")
        logs_title.setObjectName("BlueprintSectionTitle")
        logs_title.setContentsMargins(14, 12, 14, 12)
        logs_master_layout.addWidget(logs_title)
        logs_list = QListWidget()
        logs_list.setObjectName("BlueprintMasterList")
        for text in (
            "[设置] 新增更新日志页签 · 2026-04-14 12:30:00",
            "[录单] 支持规格模板预填采购明细 · 2026-04-14 12:10:00",
            "[利润计算] 新增利润计算页面 · 2026-04-14 10:40:00",
        ):
            QListWidgetItem(text, logs_list)
        logs_list.setCurrentRow(0)
        logs_master_layout.addWidget(logs_list, 1)
        logs_detail = QWidget()
        logs_detail_layout = QVBoxLayout(logs_detail)
        logs_detail_layout.setContentsMargins(0, 0, 0, 0)
        logs_detail_layout.setSpacing(12)
        logs_detail_actions = QWidget()
        logs_detail_actions_layout = QHBoxLayout(logs_detail_actions)
        logs_detail_actions_layout.setContentsMargins(0, 0, 0, 0)
        logs_detail_actions_layout.setSpacing(8)
        for text in ("新增日志", "保存修改", "删除日志"):
            button = QPushButton(text)
            if text != "删除日志":
                button.setObjectName("GhostButton")
            else:
                button.setObjectName("DangerButton")
            logs_detail_actions_layout.addWidget(button)
        detail_card, detail_card_layout = _make_card("日志详情")
        detail_form = QGridLayout()
        detail_form.setContentsMargins(0, 0, 0, 0)
        detail_form.setHorizontalSpacing(12)
        detail_form.setVerticalSpacing(10)
        for idx, (label, editor) in enumerate(
            [
                ("最后更新时间", _input("2026-04-14 12:30:00")),
                ("模块", _input("设置")),
                ("标题", _input("新增更新日志页签")),
                ("内容", _text("在设置页增加更新日志模块，支持查看、编辑、删除开发更新记录，并为后续开发沉淀统一入口。", height=140)),
            ]
        ):
            field, _ = _field(label, editor)
            if label == "内容":
                detail_form.addWidget(field, 2, 0, 1, 2)
            else:
                detail_form.addWidget(field, idx // 2, idx % 2)
        detail_card_layout.addWidget(logs_detail_actions)
        detail_card_layout.addLayout(detail_form)
        logs_detail_layout.addWidget(detail_card)
        logs_detail_layout.addStretch(1)
        logs_layout.addWidget(logs_master)
        logs_layout.addWidget(logs_detail, 1)
        settings_stack.addWidget(logs_page)

        subnav_list.currentRowChanged.connect(settings_stack.setCurrentIndex)
        content_layout.addWidget(subnav)
        content_layout.addWidget(settings_stack, 1)

        return self._wrap_page("系统设置蓝图", "左侧子导航切页，右侧内容区集中显示，店铺映射改成三列压缩布局。", content)
