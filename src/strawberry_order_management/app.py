from PySide6.QtWidgets import QApplication


def build_app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    app.setApplicationName("草莓订单管理系统")
    return app
