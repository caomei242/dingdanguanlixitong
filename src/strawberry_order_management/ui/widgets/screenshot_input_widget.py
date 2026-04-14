from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QByteArray, QBuffer, QIODevice, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QGuiApplication, QImage, QPixmap
from PySide6.QtWidgets import QFileDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout


class ScreenshotInputWidget(QFrame):
    image_ready = Signal(bytes, str)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("CardFrame")
        self.setAcceptDrops(True)

        title = QLabel("拍单识别")
        title.setObjectName("SectionTitle")
        subtitle = QLabel("支持粘贴截图、拖拽图片或选择图片，识别后自动生成订单卡")
        subtitle.setObjectName("MutedText")
        self.status_label = QLabel("等待截图")
        self.status_label.setObjectName("MutedText")
        self.choose_button = QPushButton("选择图片")
        self.paste_button = QPushButton("粘贴截图")

        button_row = QHBoxLayout()
        button_row.addWidget(self.paste_button)
        button_row.addWidget(self.choose_button)
        button_row.addStretch(1)

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addLayout(button_row)
        layout.addWidget(self.status_label)

        self.paste_button.clicked.connect(self.paste_from_clipboard)
        self.choose_button.clicked.connect(self.choose_image)

    def choose_image(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择订单截图",
            "",
            "图片文件 (*.png *.jpg *.jpeg *.webp *.bmp)",
        )
        if not file_path:
            return

        self._emit_image_bytes(Path(file_path).read_bytes(), f"图片文件：{Path(file_path).name}")

    def paste_from_clipboard(self) -> None:
        image = QGuiApplication.clipboard().image()
        if image.isNull():
            self.status_label.setText("剪贴板里没有图片")
            return

        self._emit_image_bytes(self._image_to_png_bytes(image), "剪贴板截图")

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        mime_data = event.mimeData()
        if mime_data.hasImage() or mime_data.hasUrls():
            event.acceptProposedAction()
            return
        event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        mime_data = event.mimeData()
        if mime_data.hasImage():
            image_data = mime_data.imageData()
            if isinstance(image_data, QImage) and not image_data.isNull():
                self._emit_image_bytes(self._image_to_png_bytes(image_data), "拖拽图片")
                event.acceptProposedAction()
                return
            if isinstance(image_data, QPixmap) and not image_data.isNull():
                self._emit_image_bytes(
                    self._image_to_png_bytes(image_data.toImage()),
                    "拖拽图片",
                )
                event.acceptProposedAction()
                return

            clipboard_image = QGuiApplication.clipboard().image()
            if not clipboard_image.isNull():
                self._emit_image_bytes(self._image_to_png_bytes(clipboard_image), "拖拽图片")
                event.acceptProposedAction()
                return

        if mime_data.hasUrls():
            local_path = mime_data.urls()[0].toLocalFile()
            if local_path:
                self._emit_image_bytes(Path(local_path).read_bytes(), f"拖拽图片：{Path(local_path).name}")
                event.acceptProposedAction()
                return

        event.ignore()

    def _emit_image_bytes(self, image_bytes: bytes, source_label: str) -> None:
        self.status_label.setText(f"已读取{source_label}")
        self.image_ready.emit(image_bytes, source_label)

    @staticmethod
    def _image_to_png_bytes(image: QImage) -> bytes:
        byte_array = QByteArray()
        buffer = QBuffer(byte_array)
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        image.save(buffer, "PNG")
        return bytes(byte_array)
