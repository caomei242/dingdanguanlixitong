from PySide6.QtWidgets import QApplication

from strawberry_order_management.ui.blueprint_window import BlueprintWindow


def build_preview_app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    app.setApplicationName("草莓订单管理系统 UI 蓝图预览")
    return app


def main() -> int:
    app = build_preview_app()
    window = BlueprintWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
