"""微交互：卡片悬停浮起、页面淡入、按钮按压回弹。

都用 Qt 属性动画实现，时长控制在 140-200ms，保证「跟手」而不是拖沓。
所有函数都必须能安全地在任何控件上调用（重复调用不会叠加效果）。
"""

from __future__ import annotations

from PySide6.QtCore import (
    QEasingCurve, QEvent, QObject, QPropertyAnimation, QVariantAnimation, Qt,
)
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractButton, QGraphicsDropShadowEffect, QGraphicsEffect, QWidget,
)

FAST = 130
NORMAL = 180


# ---------- 页面淡入 ----------
def fade_in(widget: QWidget | None, ms: int = NORMAL) -> None:
    """切换页面时淡入。动画结束后立刻摘掉效果，避免常驻开销。"""
    if widget is None:
        return
    from PySide6.QtWidgets import QGraphicsOpacityEffect

    effect = QGraphicsOpacityEffect(widget)
    effect.setOpacity(0.0)
    widget.setGraphicsEffect(effect)

    anim = QPropertyAnimation(effect, b"opacity", widget)
    anim.setDuration(ms)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.OutCubic)

    def _cleanup() -> None:
        if widget.graphicsEffect() is effect:
            widget.setGraphicsEffect(None)

    anim.finished.connect(_cleanup)
    anim.start(QPropertyAnimation.DeleteWhenStopped)
    widget._fade_anim = anim  # type: ignore[attr-defined]


# ---------- 卡片悬停浮起 ----------
class _HoverLift(QObject):
    """给控件挂一层阴影，hover 时模糊半径和位移变大，视觉上「浮起来」。"""

    def __init__(self, widget: QWidget, blur: int, lift: int, color: QColor):
        super().__init__(widget)
        self.widget = widget
        self.base_blur = blur
        self.base_lift = max(1, lift // 2)
        self.hover_blur = blur + 12
        self.hover_lift = lift + 4

        effect = QGraphicsDropShadowEffect(widget)
        effect.setColor(color)
        effect.setBlurRadius(self.base_blur)
        effect.setOffset(0, self.base_lift)
        widget.setGraphicsEffect(effect)
        self.effect = effect

        self.anim_blur = QPropertyAnimation(effect, b"blurRadius", self)
        self.anim_blur.setDuration(NORMAL)
        self.anim_blur.setEasingCurve(QEasingCurve.OutCubic)
        self.anim_offset = QPropertyAnimation(effect, b"offset", self)
        self.anim_offset.setDuration(NORMAL)
        self.anim_offset.setEasingCurve(QEasingCurve.OutCubic)
        widget.installEventFilter(self)

    def eventFilter(self, obj, event):
        if obj is self.widget:
            if event.type() == QEvent.Enter:
                self._to(self.hover_blur, self.hover_lift)
            elif event.type() == QEvent.Leave:
                self._to(self.base_blur, self.base_lift)
        return False

    def _to(self, blur: float, lift: float) -> None:
        for anim in (self.anim_blur, self.anim_offset):
            anim.stop()
        self.anim_blur.setStartValue(self.effect.blurRadius())
        self.anim_blur.setEndValue(blur)
        self.anim_offset.setStartValue(self.effect.offset())
        from PySide6.QtCore import QPointF

        self.anim_offset.setEndValue(QPointF(0, lift))
        self.anim_blur.start()
        self.anim_offset.start()


def attach_hover_lift(widget: QWidget, *, blur: int = 8, lift: int = 4,
                      color: QColor | None = None) -> None:
    if getattr(widget, "_hover_lift", None) is not None:
        return
    if widget.graphicsEffect() is not None:
        return  # 已经有别的效果（比如淡入），不叠加
    color = color or QColor(0, 0, 0, 38)
    widget._hover_lift = _HoverLift(widget, blur, lift, color)  # type: ignore[attr-defined]


# ---------- 按钮按压回弹 ----------
class _PressBounce(QObject):
    """按压时把按钮几何围绕中心缩小，松开回弹（OutBack 略有回弹过冲）。

    刻意不用 QGraphicsEffect：自定义 effect 必须走 sourcePixmap()，而它在
    QWidget.grab()/render() 期间会重入 —— 实测直接 0xC0000005 崩溃，
    而 grab 正是测试和截图要用的路径。
    """

    def __init__(self, button: QAbstractButton, scale: float = 0.94):
        super().__init__(button)
        self.button = button
        self.press_scale = scale
        self.base: "QRect | None" = None
        self._t = 1.0

        self.anim = QVariantAnimation(self)
        self.anim.setDuration(FAST)
        self.anim.valueChanged.connect(self._apply)

    def _apply(self, value) -> None:
        if self.base is None:
            return
        self._t = float(value)
        b = self.base
        w = max(1, int(round(b.width() * self._t)))
        h = max(1, int(round(b.height() * self._t)))
        self.button.setGeometry(
            b.x() + (b.width() - w) // 2, b.y() + (b.height() - h) // 2, w, h
        )

    def _to(self, target: float, curve: QEasingCurve.Type) -> None:
        self.anim.stop()
        self.anim.setEasingCurve(curve)
        self.anim.setStartValue(self._t)
        self.anim.setEndValue(target)
        self.anim.start()

    def eventFilter(self, obj, event):
        etype = event.type()
        if etype == QEvent.MouseButtonPress:
            self.base = self.button.geometry()
            self._to(self.press_scale, QEasingCurve.OutCubic)
        elif etype in (QEvent.MouseButtonRelease, QEvent.Leave):
            if self.base is not None:
                self._to(1.0, QEasingCurve.OutBack)
        elif etype == QEvent.Resize and self.base is not None:
            # 窗口尺寸变了就别再拿旧几何去弹，直接复位
            self.anim.stop()
            self.base = None
            self._t = 1.0
        return False


def attach_press_bounce(button: QAbstractButton, *, scale: float = 0.94) -> None:
    if getattr(button, "_press_bounce", None) is not None:
        return
    bounce = _PressBounce(button, scale)
    button._press_bounce = bounce  # type: ignore[attr-defined]
    button.installEventFilter(bounce)
