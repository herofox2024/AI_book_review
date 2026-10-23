"""主窗口：左侧导航 + 右侧页面，支持三套主题（水晶 / 跟随系统 / 深色）。"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QListWidget, QMainWindow, QSizeGrip,
    QStackedWidget, QVBoxLayout, QWidget,
)

from ..core.pipeline import Pipeline
from . import glass, motion
from .chrome import TitleBar
from .nav import NavDelegate
from .pages import GeneratePage, LibraryPage, SettingsPage, StylePage
from .theme import Theme, LIGHT, build_qss, resolve_theme

# (标签, 页面 key, 图标名)
NAV_ITEMS = [
    ("生成书评", "generate", "compose"),
    ("书评库", "library", "library"),
    ("风格画像", "style", "style"),
    ("设置", "settings", "settings"),
]

CORNER = 16          # 毛玻璃窗口圆角
SIDEBAR_WIDTH = 176


class MainWindow(QMainWindow):
    def __init__(self, pipeline: Pipeline | None = None):
        super().__init__()
        self.pipe = pipeline or Pipeline()
        self.setWindowTitle("个人风格书评生成器")
        self.resize(1120, 740)
        self.setMinimumSize(920, 600)

        self.theme: Theme = LIGHT
        self._glass_ok = False

        self._build_ui()
        self.apply_theme(getattr(self.pipe.settings.ui, "theme", "crystal"))

        # 「跟随系统」时，系统深浅色一变就跟着换
        try:
            QGuiApplication.styleHints().colorSchemeChanged.connect(self._on_scheme_changed)
        except Exception:
            pass

    # ---------- 搭界面 ----------
    def _build_ui(self) -> None:
        central = QWidget()
        central.setObjectName("central")
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # 无边框主题下的自定义标题栏（有边框主题时隐藏）
        self.title_bar = TitleBar(self)
        self.title_bar.set_title(self.windowTitle())
        self.title_bar.setVisible(False)
        outer.addWidget(self.title_bar)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        # --- 左侧导航 ---
        nav = QWidget()
        nav.setObjectName("sidebar")
        nav.setFixedWidth(SIDEBAR_WIDTH)
        nlay = QVBoxLayout(nav)
        nlay.setContentsMargins(10, 14, 10, 14)
        nlay.setSpacing(8)

        logo = QLabel("书评生成器")
        logo.setObjectName("brand")
        nlay.addWidget(logo)

        self.nav_list = QListWidget()
        self.nav_list.setObjectName("nav")
        self.nav_list.setFrameShape(QListWidget.NoFrame)
        self.nav_list.setMouseTracking(True)
        for text, _, _ in NAV_ITEMS:
            self.nav_list.addItem(text)
        self.nav_delegate = NavDelegate(
            lambda: self.theme, [item[2] for item in NAV_ITEMS], self.nav_list
        )
        self.nav_list.setItemDelegate(self.nav_delegate)
        self.nav_list.currentRowChanged.connect(self._switch)
        nlay.addWidget(self.nav_list, 1)

        self.lbl_loaded = QLabel("")
        self.lbl_loaded.setObjectName("sidebarFooter")
        self.lbl_loaded.setWordWrap(True)
        nlay.addWidget(self.lbl_loaded)
        body.addWidget(nav)

        # --- 右侧页面 ---
        self.stack = QStackedWidget()
        self.page_gen = GeneratePage(self.pipe, self)
        self.page_lib = LibraryPage(self.pipe, self)
        self.page_style = StylePage(self.pipe, self)
        self.page_style.profiles_changed.connect(self.page_gen.reload_profiles)
        self.page_set = SettingsPage(
            self.pipe, on_saved=self._on_settings_saved,
            on_theme=self.apply_theme, parent=self,
        )
        for p in (self.page_gen, self.page_lib, self.page_style, self.page_set):
            self.stack.addWidget(p)
        body.addWidget(self.stack, 1)

        outer.addLayout(body, 1)
        self.setCentralWidget(central)

        self.size_grip = QSizeGrip(self.statusBar())
        self.size_grip.setVisible(False)
        # 系统自带的抓手和圆角窗口边角打架，关掉，改用上面的 size_grip
        self.statusBar().setSizeGripEnabled(False)
        self.statusBar().addPermanentWidget(self.size_grip)

        self._refresh_status()
        self.nav_list.setCurrentRow(0)
        self._attach_motion()

    # ---------- 微交互 ----------
    def _attach_motion(self) -> None:
        """给所有卡片挂悬停浮起、给所有按钮挂按压回弹。"""
        from PySide6.QtWidgets import QFrame, QPushButton

        shadow = QColor(0, 0, 0, 60 if self.theme.dark else 34)
        for frame in self.findChildren(QFrame):
            if frame.objectName() in ("card", "cardFlat"):
                motion.attach_hover_lift(frame, color=shadow)
        for button in self.findChildren(QPushButton):
            motion.attach_press_bounce(button)

    # ---------- 主题 ----------
    def apply_theme(self, key: str) -> None:
        """切换主题：换 QSS、切窗口边框模式、套系统材质。"""
        theme = resolve_theme(key)
        self.theme = theme
        qss = build_qss(theme)

        # 全局也设一份，保证 QMessageBox / QToolTip 这类独立顶层窗口同步
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(qss)
        self.setStyleSheet(qss)

        want_glass = theme.glass and glass.is_supported()
        self._set_frameless(want_glass)
        self.title_bar.setVisible(want_glass)
        self.size_grip.setVisible(want_glass)

        if want_glass:
            # 等窗口真正显示后再套材质，否则拿到的 hwnd 可能还没建好
            QTimer.singleShot(0, self._apply_glass)
        else:
            self._glass_ok = False
            if glass.is_supported():
                glass.apply_titlebar_only(self, dark=theme.dark)

        self._restyle_motion()
        self.nav_list.viewport().update()
        self.update()

    def _restyle_motion(self) -> None:
        """深浅色切换后，卡片阴影和导航选中态要跟着重绘。"""
        from PySide6.QtWidgets import QFrame

        shadow = QColor(0, 0, 0, 70 if self.theme.dark else 34)
        for frame in self.findChildren(QFrame):
            lift = getattr(frame, "_hover_lift", None)
            if lift is not None:
                lift.effect.setColor(shadow)

    def _set_frameless(self, on: bool) -> None:
        was_visible = self.isVisible()
        if was_visible:
            # WA_TranslucentBackground 只对「尚未显示」的窗口生效，
            # 运行中切换必须先把窗口藏起来重建表面，否则会留下一层透明洞。
            self.hide()
        if on:
            self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
            self.setAttribute(Qt.WA_TranslucentBackground, True)
        else:
            self.setWindowFlags(Qt.Window)
            self.setAttribute(Qt.WA_TranslucentBackground, False)
        if was_visible:
            self.show()

    def _apply_glass(self) -> None:
        result = glass.apply(self, dark=self.theme.dark, backdrop="acrylic")
        self._glass_ok = bool(result.get("backdrop"))
        self.update()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self.theme.glass and glass.is_supported():
            QTimer.singleShot(0, self._apply_glass)

    def paintEvent(self, event) -> None:
        """自己画窗口底：玻璃主题画圆角水膜，其余主题画不透明底。

        非玻璃主题不能只靠 QSS 的 ``QMainWindow`` 背景 —— 从玻璃主题切回来时
        窗口表面可能仍是透明的，那些没被卡片覆盖的区域就会露出桌面（看起来一片黑）。
        这里显式填充，保证任何切换路径下底色都实心。
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        if not (self.theme.glass and glass.is_supported()):
            painter.fillRect(self.rect(), QColor(self.theme.win_bg))
            painter.end()
            super().paintEvent(event)
            return

        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(rect, CORNER, CORNER)

        if self._glass_ok:
            # 亚克力已经提供了背景模糊，这里只加一层很薄的水膜
            tint = QColor(255, 255, 255, 42) if not self.theme.dark else QColor(16, 18, 22, 92)
            edge = QColor(255, 255, 255, 130) if not self.theme.dark else QColor(255, 255, 255, 28)
        else:
            # 系统材质拿不到：退成接近不透明的底，避免露出未模糊的桌面
            tint = QColor(246, 247, 250, 250) if not self.theme.dark else QColor(20, 22, 26, 252)
            edge = QColor(0, 0, 0, 18) if not self.theme.dark else QColor(255, 255, 255, 20)

        painter.fillPath(path, tint)
        painter.setPen(QPen(edge, 1))
        painter.drawPath(path)
        painter.end()

    # ---------- 交互 ----------
    def _switch(self, row: int) -> None:
        if 0 <= row < self.stack.count():
            self.stack.setCurrentIndex(row)
            motion.fade_in(self.stack.currentWidget())
            key = NAV_ITEMS[row][1]
            if key == "generate":
                self.page_gen.reload_profiles()
            elif key == "library":
                self.page_lib.reload()
            elif key == "style":
                self.page_style.reload()
            self.nav_list.viewport().update()

    def _on_settings_saved(self, new_pipe: Pipeline) -> None:
        """设置保存后把所有页面切到新的 pipeline，并应用新主题。"""
        self.pipe = new_pipe
        for p in (self.page_gen, self.page_lib, self.page_style):
            p.set_pipeline(new_pipe)
        self.apply_theme(getattr(new_pipe.settings.ui, "theme", "crystal"))
        self._refresh_status()
        self.status("配置已保存并生效")

    def _refresh_status(self) -> None:
        s = self.pipe.settings
        key_state = "已设置" if s.llm.api_key else "未设置"
        self.lbl_loaded.setText(f"{s.llm.provider}\nKey {key_state}")
        self.statusBar().showMessage(
            f"服务商 {s.llm.provider} | 摘要 {s.llm.model} | "
            f"生成 {s.llm.review_model or s.llm.model} | API Key {key_state}"
        )

    def status(self, msg: str, timeout: int = 5000) -> None:
        self.statusBar().showMessage(msg, timeout)

    def _on_scheme_changed(self, *_args) -> None:
        if getattr(self.pipe.settings.ui, "theme", "") == "system":
            self.apply_theme("system")
