from __future__ import annotations

APP_STYLESHEET = """
QWidget {
    color: #20304a;
    font-family: "PingFang SC", "Microsoft YaHei", "Noto Sans SC", "Segoe UI", sans-serif;
    font-size: 14px;
}

QMainWindow {
    background: #e9eef5;
}

QScrollArea,
QAbstractScrollArea {
    background: transparent;
    border: none;
}

QAbstractScrollArea::corner {
    background: #f6f8fc;
    border: none;
}

QScrollBar:horizontal {
    background: #edf2fb;
    height: 12px;
    margin: 0;
    border-radius: 6px;
}

QScrollBar::handle:horizontal {
    background: #b8c7e6;
    min-width: 44px;
    border-radius: 6px;
}

QScrollBar::handle:horizontal:hover {
    background: #9fb3df;
}

QScrollBar:vertical {
    background: #edf2fb;
    width: 12px;
    margin: 0;
    border-radius: 6px;
}

QScrollBar::handle:vertical {
    background: #b8c7e6;
    min-height: 44px;
    border-radius: 6px;
}

QScrollBar::handle:vertical:hover {
    background: #9fb3df;
}

QScrollBar::add-line,
QScrollBar::sub-line,
QScrollBar::add-page,
QScrollBar::sub-page {
    background: transparent;
    border: none;
}

QScrollArea#EntryFormRail QWidget#qt_scrollarea_viewport,
QScrollArea#ProfitDashboardScroll QWidget#qt_scrollarea_viewport,
QScrollArea#ProfitDailyScroll QWidget#qt_scrollarea_viewport,
QScrollArea#SettingsSectionScroll QWidget#qt_scrollarea_viewport {
    background: #f6f8fc;
}

QWidget#PageContent {
    background: #f6f8fc;
}

QWidget#OrderCardWorkspace {
    background: #f6f8fc;
}

QWidget#ProfitDashboardTab,
QWidget#ProfitDailyTab,
QFrame#ProfitDailyRowsPanel {
    background: #f6f8fc;
}

QFrame#WindowShell {
    background: #f4f7fb;
    border: 1px solid #d8e1ef;
    border-radius: 16px;
}

QFrame#WindowSidebar {
    background: #f8fafc;
    border-right: 1px solid #e2e8f0;
    border-bottom-left-radius: 16px;
}

QFrame#WindowContentShell,
QFrame#ShellFrame,
QFrame#EntryActionBar,
QFrame#CardFrame,
QFrame#ProfitOverviewHeader,
QFrame#ProfitTrendCard,
QFrame#ProfitInsightCard,
QFrame#ProfitMetricCard,
QFrame#ProfitSummaryChip,
QFrame#ProfitDailyFilterCard,
QFrame#ProfitDailyDayCard,
QFrame#ProfitDailyShopRow,
QFrame#ProfitDailyDetailPanel,
QFrame#OrderSummaryCard,
QFrame#OrderShippingCard,
QFrame#ProcurementSectionCard,
QFrame#FinancialSectionCard,
QFrame#ProcurementRowCard,
QFrame#IntakeSupportCard,
QFrame#EntryCaptureCard,
QFrame#EntryExtractorInputCard,
QFrame#EntryExtractorResultCard {
    background: rgba(255, 255, 255, 0.96);
    border: 1px solid #e3e9f4;
    border-radius: 24px;
}

QFrame#EntryActionBar {
    background: rgba(255, 255, 255, 0.95);
}

QFrame#HistoryListCard,
QFrame#HistoryFilterCard,
QFrame#HistoryMasterPane,
QFrame#HistoryDetailPane,
QFrame#HistoryDetailCard,
QFrame#HistoryActionCard,
QFrame#HistorySummaryCard,
QFrame#HistoryStatCard,
QFrame#HistoryMiniSummaryCard,
QFrame#HistoryStatusCard,
QFrame#HistoryStickyActionBar {
    background: rgba(255, 255, 255, 0.98);
    border: 1px solid #dbe4f2;
    border-radius: 22px;
}

QFrame#SettingsStickyActionBar,
QFrame#SettingsNavPane {
    background: rgba(255, 255, 255, 0.98);
    border: 1px solid #dbe4f2;
    border-radius: 22px;
}

QFrame#HistoryStickyActionBar {
    background: rgba(255, 255, 255, 0.96);
}

QFrame#HistoryStatusCard[active="true"] {
    background: #eef4ff;
    border: 1px solid #bdd0ff;
}

QLabel#BrandTitle {
    color: #ff4b6e;
    font-size: 26px;
    font-weight: 800;
}

QLabel#BrandSubtitle {
    color: #7e8aa5;
    font-size: 12px;
}

QListWidget {
    background: rgba(255, 255, 255, 0.98);
    border: 1px solid #dbe4f2;
    border-radius: 18px;
    padding: 6px;
    outline: none;
}

QListWidget#HistoryList {
    min-height: 360px;
}

QListWidget::item {
    padding: 9px 11px;
    margin: 2px 0;
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
    padding: 7px 11px;
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

QLineEdit, QTextEdit, QComboBox, QDateEdit {
    background: #ffffff;
    border: 1px solid #d9e2f1;
    border-radius: 10px;
    padding: 7px 10px;
    selection-background-color: #4a7cff;
    selection-color: #ffffff;
    color: #20304a;
}

QTextEdit {
    min-height: 60px;
}

QComboBox,
QDateEdit {
    padding-right: 28px;
    combobox-popup: 0;
}

QComboBox::drop-down,
QDateEdit::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 26px;
    border: none;
    background: transparent;
}

QComboBox QAbstractItemView,
QDateEdit QAbstractItemView {
    background: #ffffff;
    color: #20304a;
    border: 1px solid #d9e2f1;
    selection-background-color: #4a7cff;
    selection-color: #ffffff;
    outline: none;
}

QWidget#EntryFormViewport {
    background: #f6f8fc;
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

QTabWidget#ProfitSegmentTabs::pane {
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

QTabWidget#ProfitSegmentTabs QTabBar::tab {
    background: #eef3ff;
    color: #5f7396;
    border: 1px solid #d7e2f6;
    border-bottom: none;
    padding: 10px 22px;
    margin-right: 6px;
    border-top-left-radius: 14px;
    border-top-right-radius: 14px;
    font-weight: 700;
}

QTabWidget#ProfitSegmentTabs QTabBar::tab:selected {
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
