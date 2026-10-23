"""左侧导航的绘制代理：胶囊选中态 + 线性图标 + 主题跟随。

QListWidget 默认的 item 绘制没法同时处理圆角胶囊、图标着色和文字缩进，
所以整份交给 delegate 自己画。
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import QStyle, QStyledItemDelegate

from . import icons


class NavDelegate(QStyledItemDelegate):
    def __init__(self, theme_provider, icon_names: list[str], parent=None):
        super().__init__(parent)
        self._theme_provider = theme_provider
        self._icon_names = icon_names

    def sizeHint(self, option, index) -> QSize:  # noqa: N802
        return QSize(0, 38)

    def paint(self, painter: QPainter, option, index) -> None:  # noqa: N802
        theme = self._theme_provider()
        selected = bool(option.state & QStyle.State_Selected)
        hovered = bool(option.state & QStyle.State_MouseOver)

        rect = QRectF(option.rect).adjusted(0, 1.5, 0, -1.5)
        pill = rect.adjusted(4, 0, -4, 0)

        if selected:
            fill = QColor(theme.accent)
            ink = QColor("#FFFFFF")
        elif hovered:
            fill = QColor(theme.accent_soft)
            ink = QColor(theme.text)
        else:
            fill = None
            ink = QColor(theme.text_sub)

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)
        if fill is not None:
            painter.setPen(Qt.NoPen)
            painter.setBrush(fill)
            painter.drawRoundedRect(pill, 9, 9)

        name = self._icon_names[index.row()] if index.row() < len(self._icon_names) else ""
        icon_rect = QRectF(pill.left() + 11, pill.center().y() - 9, 18, 18)
        icons.paint_icon(painter, name, icon_rect, ink, 1.6)

        font = QFont(option.font)
        font.setPointSizeF(option.font.pointSizeF())
        font.setWeight(QFont.DemiBold if selected else QFont.Normal)
        painter.setFont(font)
        painter.setPen(ink)
        text_rect = pill.adjusted(39, 0, -10, 0)
        painter.drawText(
            text_rect, int(Qt.AlignVCenter | Qt.AlignLeft), str(index.data() or "")
        )
        painter.restore()
