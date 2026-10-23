"""无边框窗口的自定义标题栏：苹果风红黄绿三点 + 拖动 + 双击最大化。

只在毛玻璃主题下显示；普通有边框主题用系统原生标题栏。
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QMainWindow, QToolButton, QWidget

# (objectName, 颜色, 悬停色, 提示, 作用)
TRAFFIC_LIGHTS = (
    ("winClose", "#FF5F57", "#E0443E", "关闭"),
    ("winMin", "#FEBC2E", "#DEA123", "最小化"),
    ("winMax", "#28C840", "#1DAD2B", "最大化"),
)


class TitleBar(QWidget):
    """苹果风标题栏。拖动、双击最大化都由它自己处理。"""

    def __init__(self, window: QMainWindow):
        super().__init__(window)
        self._win = window
        self._drag_offset: QPoint | None = None
        self.setObjectName("titleBar")
        self.setFixedHeight(38)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 0, 14, 0)
        lay.setSpacing(8)

        self.btn_close = self._make_light(lay, *TRAFFIC_LIGHTS[0])
        self.btn_min = self._make_light(lay, *TRAFFIC_LIGHTS[1])
        self.btn_max = self._make_light(lay, *TRAFFIC_LIGHTS[2])

        self.btn_close.clicked.connect(window.close)
        self.btn_min.clicked.connect(window.showMinimized)
        self.btn_max.clicked.connect(self._toggle_max)

        lay.addSpacing(10)
        self.lbl_title = QLabel("", self)
        self.lbl_title.setObjectName("sub")
        self.lbl_title.setStyleSheet("font-size: 12px; font-weight: 600;")
        self.lbl_title.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.lbl_title, 1)
        # 右侧补足三点宽度，让标题视觉居中
        lay.addSpacing(56)

    def _make_light(self, lay: QHBoxLayout, name: str, color: str,
                    hover: str, tip: str) -> QToolButton:
        """画一盏 12px 的圆点按钮（关闭/最小化/最大化）。"""
        btn = QToolButton(self)
        btn.setObjectName(name)
        btn.setFixedSize(12, 12)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setToolTip(tip)
        btn.setStyleSheet(
            f"QToolButton {{ border: none; border-radius: 6px; background: {color}; }}"
            f"QToolButton:hover {{ background: {hover}; }}"
        )
        lay.addWidget(btn)
        return btn

    def set_title(self, text: str) -> None:
        self.lbl_title.setText(text)

    def _toggle_max(self) -> None:
        if self._win.isMaximized():
            self._win.showNormal()
        else:
            self._win.showMaximized()

    # ---------- 拖动 ----------
    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._drag_offset = (
                event.globalPosition().toPoint() - self._win.frameGeometry().topLeft()
            )
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self._drag_offset is not None and event.buttons() & Qt.LeftButton:
            if self._win.isMaximized():
                # 从最大化状态拖下来先还原，再按相对位置继续跟手
                self._win.showNormal()
                self._drag_offset = QPoint(self.width() // 2, 18)
            self._win.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()

    def mouseReleaseEvent(self, event) -> None:
        self._drag_offset = None
        event.accept()

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._toggle_max()
            event.accept()
