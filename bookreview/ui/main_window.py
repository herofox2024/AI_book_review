"""主窗口：左侧导航 + 右侧页面。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QListWidget, QMainWindow, QStackedWidget, QVBoxLayout,
    QWidget,
)

from ..core.pipeline import Pipeline
from .pages import GeneratePage, LibraryPage, SettingsPage, StylePage
from .theme import QSS

NAV_ITEMS = [
    ("生成书评", "generate"),
    ("书评库", "library"),
    ("风格画像", "style"),
    ("设置", "settings"),
]


class MainWindow(QMainWindow):
    def __init__(self, pipeline: Pipeline | None = None):
        super().__init__()
        self.pipe = pipeline or Pipeline()
        self.setWindowTitle("个人风格书评生成器")
        self.resize(1100, 720)
        self.setStyleSheet(QSS)
        self._build_ui()

    def _build_ui(self) -> None:
        central = QWidget()
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # --- 左侧导航 ---
        nav = QWidget()
        nav.setFixedWidth(150)
        nav.setStyleSheet("background: #FFFFFF; border-right: 1px solid #E3E6EB;")
        nlay = QVBoxLayout(nav)
        nlay.setContentsMargins(10, 16, 10, 16)
        nlay.setSpacing(6)

        logo = QLabel("书评生成器")
        logo.setStyleSheet("font-size: 15px; font-weight: 700; padding: 0 6px 10px 6px;")
        nlay.addWidget(logo)

        self.nav_list = QListWidget()
        self.nav_list.setStyleSheet(
            "QListWidget { border: none; background: transparent; }"
            "QListWidget::item { border: none; border-radius: 6px; padding: 9px 10px; }"
        )
        for text, _ in NAV_ITEMS:
            self.nav_list.addItem(text)
        self.nav_list.currentRowChanged.connect(self._switch)
        nlay.addWidget(self.nav_list, 1)

        self.lbl_loaded = QLabel("")
        self.lbl_loaded.setObjectName("muted")
        self.lbl_loaded.setWordWrap(True)
        self.lbl_loaded.setStyleSheet("font-size: 11px; padding: 0 6px;")
        nlay.addWidget(self.lbl_loaded)

        root.addWidget(nav)

        # --- 右侧页面 ---
        self.stack = QStackedWidget()
        self.page_gen = GeneratePage(self.pipe, self)
        self.page_lib = LibraryPage(self.pipe, self)
        self.page_style = StylePage(self.pipe, self)
        self.page_style.profiles_changed.connect(self.page_gen.reload_profiles)
        self.page_set = SettingsPage(self.pipe, on_saved=self._on_settings_saved, parent=self)
        for p in (self.page_gen, self.page_lib, self.page_style, self.page_set):
            self.stack.addWidget(p)
        root.addWidget(self.stack, 1)

        self.setCentralWidget(central)

        self.statusBar().setStyleSheet("background: #FFFFFF; color: #646A73;")
        self._refresh_status()
        self.nav_list.setCurrentRow(0)

    # ---------- 交互 ----------
    def _switch(self, row: int) -> None:
        if 0 <= row < self.stack.count():
            self.stack.setCurrentIndex(row)
            if NAV_ITEMS[row][1] == "generate":
                self.page_gen.reload_profiles()
            elif NAV_ITEMS[row][1] == "library":
                self.page_lib.reload()
            elif NAV_ITEMS[row][1] == "style":
                self.page_style.reload()

    def _on_settings_saved(self, new_pipe: Pipeline) -> None:
        """设置保存后把所有页面切到新的 pipeline。"""
        self.pipe = new_pipe
        for p in (self.page_gen, self.page_lib, self.page_style):
            p.set_pipeline(new_pipe)
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
