from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QFrame,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class SettingsPage(QWidget):
    save_requested = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("SettingsPage")

        self.ocr_base_url_edit = QLineEdit()
        self.ocr_api_key_edit = QLineEdit()
        self.helper_base_url_edit = QLineEdit()
        self.helper_api_key_edit = QLineEdit()
        self.feishu_app_id_edit = QLineEdit()
        self.feishu_app_secret_edit = QLineEdit()
        self.feishu_table_id_edit = QLineEdit()
        self.feishu_table_name_edit = QLineEdit()
        self.save_button = QPushButton("保存/应用")

        header = QVBoxLayout()
        title = QLabel("设置")
        title.setObjectName("SectionTitle")
        subtitle = QLabel("配置 OCR、辅助提取和飞书写入参数")
        subtitle.setObjectName("MutedText")
        header.addWidget(title)
        header.addWidget(subtitle)

        form = QFormLayout()
        form.addRow("OCR API Base URL", self.ocr_base_url_edit)
        form.addRow("OCR API Key", self.ocr_api_key_edit)
        form.addRow("辅助提取 API Base URL", self.helper_base_url_edit)
        form.addRow("辅助提取 API Key", self.helper_api_key_edit)
        form.addRow("飞书 App ID", self.feishu_app_id_edit)
        form.addRow("飞书 App Secret", self.feishu_app_secret_edit)
        form.addRow("飞书表格 ID", self.feishu_table_id_edit)
        form.addRow("飞书表格名称", self.feishu_table_name_edit)

        card = QFrame()
        card.setObjectName("CardFrame")
        card_layout = QVBoxLayout(card)
        card_layout.addLayout(form)
        card_layout.addWidget(self.save_button)

        root = QVBoxLayout(self)
        root.addLayout(header)
        root.addWidget(card)
        root.addStretch(1)
        self.save_button.clicked.connect(self._emit_save_requested)

    def to_payload(self) -> dict[str, str]:
        return {
            "ocr_base_url": self.ocr_base_url_edit.text().strip(),
            "ocr_api_key": self.ocr_api_key_edit.text().strip(),
            "helper_base_url": self.helper_base_url_edit.text().strip(),
            "helper_api_key": self.helper_api_key_edit.text().strip(),
            "feishu_app_id": self.feishu_app_id_edit.text().strip(),
            "feishu_app_secret": self.feishu_app_secret_edit.text().strip(),
            "feishu_table_id": self.feishu_table_id_edit.text().strip(),
            "feishu_table_name": self.feishu_table_name_edit.text().strip(),
        }

    def load_payload(self, payload: dict) -> None:
        self.ocr_base_url_edit.setText(self._clean_text(payload.get("ocr_base_url")))
        self.ocr_api_key_edit.setText(self._clean_text(payload.get("ocr_api_key")))
        self.helper_base_url_edit.setText(self._clean_text(payload.get("helper_base_url")))
        self.helper_api_key_edit.setText(self._clean_text(payload.get("helper_api_key")))
        self.feishu_app_id_edit.setText(self._clean_text(payload.get("feishu_app_id")))
        self.feishu_app_secret_edit.setText(self._clean_text(payload.get("feishu_app_secret")))
        self.feishu_table_id_edit.setText(self._clean_text(payload.get("feishu_table_id")))
        self.feishu_table_name_edit.setText(self._clean_text(payload.get("feishu_table_name")))

    def _emit_save_requested(self) -> None:
        self.save_requested.emit(self.to_payload())

    @staticmethod
    def _clean_text(value) -> str:
        if value is None:
            return ""
        return str(value).strip()
