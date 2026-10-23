"""线性图标：用 QPainter 现画，颜色跟随主题，不依赖外部资源文件。

好处是深浅色/玻璃主题切换时图标自动跟着变色，打包进 exe 也不用带图片。
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap

STROKE = 1.6


def _pen(painter: QPainter, color: QColor, width: float) -> QPen:
    pen = QPen(color, width)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)
    return pen


def _sparkle(p: QPainter, cx: float, cy: float, r: float, filled: bool = False) -> None:
    """四角星（苹果常用的“生成”意象）。"""
    k = r * 0.34
    path = QPainterPath()
    path.moveTo(cx, cy - r)
    path.quadTo(cx + k, cy - k, cx + r, cy)
    path.quadTo(cx + k, cy + k, cx, cy + r)
    path.quadTo(cx - k, cy + k, cx - r, cy)
    path.quadTo(cx - k, cy - k, cx, cy - r)
    p.drawPath(path)


def _draw_compose(p: QPainter, r: QRectF, color: QColor, w: float) -> None:
    """生成书评：大星 + 小星。"""
    _sparkle(p, r.center().x() - r.width() * 0.10, r.center().y(),
             r.width() * 0.36)
    _sparkle(p, r.center().x() + r.width() * 0.32, r.center().y() - r.height() * 0.30,
             r.width() * 0.16)


def _draw_library(p: QPainter, r: QRectF, color: QColor, w: float) -> None:
    """书评库：书本轮廓 + 书脊 + 两行文字。"""
    x, y = r.left() + r.width() * 0.18, r.top() + r.height() * 0.16
    bw, bh = r.width() * 0.62, r.height() * 0.68
    p.drawRoundedRect(QRectF(x, y, bw, bh), 2.2, 2.2)
    p.drawLine(QPointF(x + bw * 0.26, y), QPointF(x + bw * 0.26, y + bh))
    p.drawLine(QPointF(x + bw * 0.46, y + bh * 0.34), QPointF(x + bw * 0.82, y + bh * 0.34))
    p.drawLine(QPointF(x + bw * 0.46, y + bh * 0.58), QPointF(x + bw * 0.70, y + bh * 0.58))


def _draw_style(p: QPainter, r: QRectF, color: QColor, w: float) -> None:
    """风格画像：三根带滑块的横线。"""
    left = r.left() + r.width() * 0.16
    right = r.left() + r.width() * 0.84
    for index, ratio in enumerate((0.68, 0.32, 0.55)):
        y = r.top() + r.height() * (0.24 + index * 0.26)
        p.drawLine(QPointF(left, y), QPointF(right, y))
        cx = left + (right - left) * ratio
        p.save()
        p.setBrush(color)
        p.drawEllipse(QPointF(cx, y), r.width() * 0.085, r.width() * 0.085)
        p.restore()


def _draw_settings(p: QPainter, r: QRectF, color: QColor, w: float) -> None:
    """设置：齿轮（圆 + 八条齿）。"""
    import math

    c = r.center()
    radius = r.width() * 0.24
    p.drawEllipse(c, radius, radius)
    outer = r.width() * 0.40
    inner = r.width() * 0.31
    for i in range(8):
        angle = math.radians(i * 45)
        dx, dy = math.cos(angle), math.sin(angle)
        p.drawLine(QPointF(c.x() + dx * inner, c.y() + dy * inner),
                   QPointF(c.x() + dx * outer, c.y() + dy * outer))


_DRAWERS = {
    "compose": _draw_compose,
    "library": _draw_library,
    "style": _draw_style,
    "settings": _draw_settings,
}


def paint_icon(painter: QPainter, name: str, rect: QRectF, color: QColor,
               width: float = STROKE) -> None:
    drawer = _DRAWERS.get(name)
    if drawer is None:
        return
    painter.save()
    painter.setRenderHint(QPainter.Antialiasing, True)
    _pen(painter, color, width)
    drawer(painter, rect, color, width)
    painter.restore()


def make_icon(name: str, color: str, size: int = 18, width: float = STROKE) -> QIcon:
    """渲染成 QIcon，供按钮/动作使用。"""
    ratio = 3
    pm = QPixmap(size * ratio, size * ratio)
    pm.fill(Qt.transparent)
    pm.setDevicePixelRatio(ratio)
    painter = QPainter(pm)
    paint_icon(painter, name, QRectF(0, 0, size, size), QColor(color), width)
    painter.end()
    return QIcon(pm)
