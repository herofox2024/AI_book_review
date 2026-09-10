"""Reusable clickable help labels for parameter controls."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QPoint, Qt
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QToolButton, QWidget


class ParameterHelp(QObject):
    def __init__(self, page: QWidget):
        super().__init__(page)
        self.page = page
        self.popup: QLabel | None = None
        app = QApplication.instance()
        if app:
            app.installEventFilter(self)

    def label(self, title: str, text: str) -> QWidget:
        host = QWidget()
        layout = QHBoxLayout(host)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(QLabel(title))
        button = QToolButton()
        button.setText("?")
        button.setFixedSize(20, 20)
        button.setToolTip("点击查看说明")
        button.clicked.connect(lambda: self.show(button, text))
        layout.addWidget(button)
        layout.addStretch(1)
        return host

    def show(self, anchor: QWidget, text: str) -> None:
        self.close()
        popup = QLabel(text, self.page, Qt.ToolTip)
        popup.setWordWrap(True)
        popup.setMaximumWidth(380)
        popup.setStyleSheet(
            "background:#fffbe6; border:1px solid #d6b656; padding:8px; color:#222;"
        )
        popup.adjustSize()
        popup.move(anchor.mapTo(self.page, anchor.rect().bottomRight()) + QPoint(6, 4))
        popup.show()
        self.popup = popup

    def close(self) -> None:
        if self.popup:
            self.popup.deleteLater()
            self.popup = None

    def eventFilter(self, obj, event):
        if event.type() == QEvent.MouseButtonPress and self.popup:
            inside = obj is self.popup or (
                isinstance(obj, QWidget) and self.popup.isAncestorOf(obj)
            )
            if not inside:
                self.close()
        return False
