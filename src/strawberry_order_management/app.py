from PySide6.QtWidgets import QApplication

from strawberry_order_management.config import ConfigStore, default_config_path
from strawberry_order_management.ui.main_window import MainWindow


def build_app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    app.setApplicationName("草莓订单管理系统")
    return app


def main() -> int:
    app = build_app()
    window = MainWindow(config_store=ConfigStore(default_config_path()))
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
