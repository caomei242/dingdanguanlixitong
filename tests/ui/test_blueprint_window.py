from PySide6.QtWidgets import QApplication, QComboBox, QListWidget, QStackedWidget, QWidget

from strawberry_order_management.ui.blueprint_window import BlueprintWindow
from strawberry_order_management.preview_app import build_preview_app


def test_build_preview_app_reuses_qapplication_instance():
    app = build_preview_app()

    assert isinstance(app, QApplication)
    assert app.applicationName() == "草莓订单管理系统 UI 蓝图预览"
    assert build_preview_app() is app


def test_blueprint_window_renders_four_modules_and_preview_shell(qtbot):
    window = BlueprintWindow()
    qtbot.addWidget(window)

    assert window.windowTitle() == "草莓订单管理系统 UI 蓝图预览"
    assert [window.nav.item(index).text() for index in range(window.nav.count())] == [
        "订单录入",
        "历史订单",
        "财务报表",
        "设置",
    ]
    assert window.stack.count() == 4

    assert window.findChild(QWidget, "BlueprintEntryLeftRail") is not None
    assert window.findChild(QWidget, "BlueprintEntryFormRail") is not None
    assert window.findChild(QWidget, "BlueprintEntryResultRail") is not None
    assert window.findChild(QWidget, "BlueprintHistoryMasterPane") is not None
    assert window.findChild(QWidget, "BlueprintHistoryDetailPane") is not None
    assert window.findChild(QStackedWidget, "BlueprintProfitTabs") is not None
    assert window.findChild(QListWidget, "BlueprintSettingsSubnav") is not None
    assert window.findChild(QStackedWidget, "BlueprintSettingsStack") is not None


def test_blueprint_window_profit_and_settings_controls_match_blueprint(qtbot):
    window = BlueprintWindow()
    qtbot.addWidget(window)

    profit_tabs = window.findChild(QStackedWidget, "BlueprintProfitTabs")
    assert profit_tabs is not None
    assert profit_tabs.count() == 2

    metric_combo = window.findChild(QComboBox, "BlueprintTrendMetricCombo")
    assert metric_combo is not None
    assert [metric_combo.itemText(index) for index in range(metric_combo.count())] == [
        "收入",
        "毛利润",
        "支出",
    ]

    settings_subnav = window.findChild(QListWidget, "BlueprintSettingsSubnav")
    assert settings_subnav is not None
    assert [settings_subnav.item(index).text() for index in range(settings_subnav.count())] == [
        "接口配置",
        "商品库",
        "店铺映射",
        "更新日志",
    ]
