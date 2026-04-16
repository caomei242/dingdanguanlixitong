from PySide6.QtWidgets import QApplication

from strawberry_order_management.config import ConfigStore, default_config_path
from strawberry_order_management.expenses import ExpenseStore, default_expense_path
from strawberry_order_management.history import HistoryStore, default_history_path
from strawberry_order_management.ui.main_window import MainWindow
from strawberry_order_management.ui.app_icon import load_app_icon


def build_app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    app.setApplicationName("草莓订单管理系统")
    app.setWindowIcon(load_app_icon())
    return app


def main() -> int:
    app = build_app()
    window = MainWindow(
        config_store=ConfigStore(default_config_path()),
        history_store=HistoryStore(default_history_path()),
        expense_store=ExpenseStore(default_expense_path()),
    )
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
