"""主题系统：配色令牌 + 三套风格（透明水晶 / 跟随系统 / 深色）。

设计约定
--------
1. 所有颜色、圆角、字号都从 ``Theme`` 令牌出，QSS 里不再出现裸色值；
2. ``build_qss(theme)`` 是唯一的样式产出口，任何页面只管用 objectName；
3. ``resolve_theme(key)`` 负责把 ``system`` 解析成实际的浅色/深色。

QSS 里大量 ``{}``，用 ``string.Template`` 填值而不是 f-string，
免得结构括号和占位符互相干扰。
"""

from __future__ import annotations

from dataclasses import dataclass
from string import Template

FONT_FAMILY = (
    "Microsoft YaHei UI, Microsoft YaHei, Segoe UI Variable Text, "
    "PingFang SC, sans-serif"
)
MONO_FAMILY = "Cascadia Mono, Consolas, monospace"


@dataclass(frozen=True)
class Theme:
    key: str
    label: str
    hint: str
    dark: bool
    glass: bool          # 是否窗口级毛玻璃（无边框 + 系统亚克力）

    win_bg: str          # 窗口底色；glass 主题为 transparent，露出系统毛玻璃
    sidebar_bg: str
    surface: str         # 卡片
    surface_soft: str    # 输入框 / 次级面
    surface_alt: str     # 表头 / 进度条槽
    border: str
    border_soft: str
    text: str
    text_sub: str
    text_mute: str
    accent: str
    accent_hover: str
    accent_soft: str
    danger: str
    danger_soft: str
    success: str
    warn: str
    scroll: str = "#C9CFD8"

    radius: int = 9
    radius_lg: int = 16


# ---------- 1) 透明水晶：半透明卡片浮在系统亚克力之上 ----------
CRYSTAL = Theme(
    key="crystal",
    label="透明水晶",
    hint="无边框 + Windows 11 亚克力毛玻璃，卡片半透明",
    dark=False,
    glass=True,
    win_bg="transparent",
    sidebar_bg="rgba(255, 255, 255, 0.34)",
    surface="rgba(255, 255, 255, 0.58)",
    surface_soft="rgba(255, 255, 255, 0.46)",
    surface_alt="rgba(255, 255, 255, 0.30)",
    border="rgba(255, 255, 255, 0.78)",
    border_soft="rgba(0, 0, 0, 0.07)",
    text="#1B1D21",
    text_sub="#484D55",
    text_mute="#7B828B",
    accent="#0A84FF",
    accent_hover="#2E93FF",
    accent_soft="rgba(10, 132, 255, 0.15)",
    danger="#E5484D",
    danger_soft="rgba(229, 72, 77, 0.12)",
    success="#30A46C",
    warn="#F5A524",
    scroll="rgba(58, 70, 88, 0.32)",
)

# ---------- 2a) 跟随系统（浅色）----------
LIGHT = Theme(
    key="light",
    label="跟随系统",
    hint="浅色时使用这套；深色时自动切到深色配色",
    dark=False,
    glass=False,
    win_bg="#F5F6F8",
    sidebar_bg="#FBFBFD",
    surface="#FFFFFF",
    surface_soft="#FFFFFF",
    surface_alt="#F2F3F5",
    border="#E4E7EC",
    border_soft="#EEF0F3",
    text="#1F2329",
    text_sub="#5B626B",
    text_mute="#8F959E",
    accent="#2E6BE6",
    accent_hover="#4079EC",
    accent_soft="#EAF1FE",
    danger="#D83931",
    danger_soft="#FDECEC",
    success="#2BA471",
    warn="#D87A16",
)

# ---------- 2b) 深色 ----------
DARK = Theme(
    key="dark",
    label="黑色",
    hint="纯深色配色，夜里看不刺眼",
    dark=True,
    glass=False,
    win_bg="#14161A",
    sidebar_bg="#191C21",
    surface="#1F2329",
    surface_soft="#252A32",
    surface_alt="#2A3038",
    border="#2E343D",
    border_soft="#242A31",
    text="#E7EAEE",
    text_sub="#A4ABB5",
    text_mute="#6F7781",
    accent="#5B8CFF",
    accent_hover="#7AA2FF",
    accent_soft="rgba(91, 140, 255, 0.18)",
    danger="#F05B5B",
    danger_soft="rgba(240, 91, 91, 0.14)",
    success="#4CC38A",
    warn="#E8A33D",
    scroll="#3C434D",
)

THEMES: dict[str, Theme] = {t.key: t for t in (CRYSTAL, LIGHT, DARK)}

# 设置里可选的三项（system 是虚拟项，解析后落到 light / dark）
THEME_CHOICES: list[tuple[str, str, str]] = [
    ("crystal", CRYSTAL.label, "Win11 亚克力毛玻璃"),
    ("system", LIGHT.label, "跟随系统深浅色"),
    ("dark", DARK.label, "固定深色配色"),
]


def resolve_theme(key: str | None) -> Theme:
    """把配置里的主题名解析成具体主题；``system`` 跟随系统深浅色。"""
    key = (key or "").strip().lower()
    if key == "system":
        return DARK if system_is_dark() else LIGHT
    return THEMES.get(key, LIGHT)


def system_is_dark() -> bool:
    """读系统深浅色。拿不到就当作浅色。"""
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QGuiApplication

        hints = QGuiApplication.styleHints()
        return hints.colorScheme() == Qt.ColorScheme.Dark
    except Exception:
        return False


_QSS = Template(
    """
* {
    font-family: $font_family;
    outline: none;
}

QWidget {
    color: $text;
    font-size: 13px;
}

/* ---------- 窗口 / 页面底 ---------- */
QMainWindow, QDialog {
    background: $win_bg;
}
QWidget#pageRoot, QWidget#central {
    background: transparent;
}

/* ---------- 左侧导航 ---------- */
QWidget#sidebar {
    background: $sidebar_bg;
    border-right: 1px solid $border_soft;
}
QLabel#brand {
    font-size: 15px;
    font-weight: 700;
    letter-spacing: 0.3px;
    padding: 2px 8px 12px 8px;
    color: $text;
}
QListWidget#nav {
    border: none;
    background: transparent;
}
/* 选中态、图标与文字缩进都由 NavDelegate 自绘，这里清掉默认外观 */
QListWidget#nav {
    outline: none;
}
QListWidget#nav::item {
    border: none;
    border-radius: $radius;
    padding: 0;
    margin: 0;
}
QListWidget#nav::item:hover,
QListWidget#nav::item:selected {
    background: transparent;
}

/* ---------- 卡片：苹果风分组容器 ---------- */
QFrame#card {
    background: $surface;
    border: 1px solid $border;
    border-radius: $radius_lg;
}
QFrame#cardFlat {
    background: $surface_soft;
    border: 1px solid $border_soft;
    border-radius: $radius;
}
QFrame#row {
    border: none;
    border-bottom: 1px solid $border_soft;
    background: transparent;
}
QFrame#hairline {
    background: $border_soft;
    border: none;
}

/* ---------- 设置行 ---------- */
QLabel#rowTitle {
    font-size: 13px;
}
QLabel#rowHint {
    font-size: 11px;
    color: $text_mute;
}

/* ---------- 按钮 ---------- */
QPushButton {
    background: $surface_soft;
    border: 1px solid $border;
    border-radius: $radius;
    padding: 7px 15px;
    color: $text;
}
QPushButton:hover {
    border-color: $accent;
    background: $accent_soft;
}
QPushButton:pressed {
    background: $surface_alt;
    /* 轻微下压 1px，配合按压回弹动画做出「按进去」的手感 */
    padding-top: 8px;
    padding-bottom: 6px;
}
QPushButton:disabled {
    color: $text_mute;
    border-color: $border_soft;
    background: $surface_alt;
}

QPushButton#primary {
    background: $accent;
    border: 1px solid $accent;
    color: #FFFFFF;
    font-weight: 600;
}
QPushButton#primary:hover {
    background: $accent_hover;
    border-color: $accent_hover;
}
QPushButton#primary:disabled {
    background: $surface_alt;
    border-color: $border_soft;
    color: $text_mute;
}

QPushButton#danger {
    color: $danger;
    border-color: $border;
}
QPushButton#danger:hover {
    background: $danger_soft;
    border-color: $danger;
}

QPushButton#link {
    border: none;
    background: transparent;
    color: $accent;
    padding: 2px 6px;
}
QPushButton#link:hover {
    background: $accent_soft;
}

/* ---------- 输入 ---------- */
QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background: $surface_soft;
    border: 1px solid $border;
    border-radius: $radius;
    padding: 7px 10px;
    selection-background-color: $accent;
    selection-color: #FFFFFF;
}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus,
QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border-color: $accent;
}
QLineEdit:disabled, QTextEdit:disabled, QComboBox:disabled {
    color: $text_mute;
}
QComboBox::drop-down { border: none; width: 22px; }
QComboBox QAbstractItemView {
    background: $surface;
    border: 1px solid $border;
    border-radius: $radius;
    selection-background-color: $accent_soft;
    selection-color: $text;
    padding: 4px;
}

/* ---------- 列表 / 表格 ---------- */
QListWidget, QTableWidget, QTreeWidget {
    background: $surface;
    border: 1px solid $border;
    border-radius: $radius;
}
QListWidget::item { padding: 8px 10px; }
QListWidget::item:selected { background: $accent_soft; color: $text; }
QListWidget::item:hover { background: $surface_alt; }

QTableWidget {
    gridline-color: $border_soft;
    border-radius: $radius;
}
QTableWidget::item { padding: 6px 8px; }
QTableWidget::item:selected { background: $accent_soft; color: $text; }
QHeaderView::section {
    background: $surface_alt;
    border: none;
    border-bottom: 1px solid $border;
    padding: 8px 10px;
    font-weight: 600;
    color: $text_sub;
}
QTableCornerButton::section { background: $surface_alt; border: none; }

/* ---------- 分组 / 滚动区 ---------- */
QGroupBox {
    border: 1px solid $border;
    border-radius: $radius_lg;
    margin-top: 16px;
    padding: 14px 14px 12px 14px;
    background: $surface;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 0 6px;
    color: $text_sub;
    font-weight: 600;
}
QScrollArea { background: transparent; border: none; }
QScrollArea > QWidget > QWidget { background: transparent; }

/* ---------- 进度 ---------- */
QProgressBar {
    border: 1px solid $border_soft;
    border-radius: 7px;
    background: $surface_alt;
    height: 16px;
    text-align: center;
    color: $text_sub;
    font-size: 11px;
}
QProgressBar::chunk {
    background: $accent;
    border-radius: 6px;
}

/* ---------- 标签页 ---------- */
QTabWidget::pane { border: none; background: transparent; }
QTabBar::tab {
    padding: 8px 18px;
    margin-right: 4px;
    border-radius: $radius;
    color: $text_sub;
}
QTabBar::tab:selected { background: $surface; color: $text; font-weight: 600; }
QTabBar::tab:hover { color: $text; }

/* ---------- 滚动条 ---------- */
QScrollBar:vertical {
    background: transparent;
    width: 10px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: $scroll;
    border-radius: 5px;
    min-height: 32px;
}
QScrollBar::handle:vertical:hover { background: $text_mute; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 0; }
QScrollBar::handle:horizontal {
    background: $scroll;
    border-radius: 5px;
    min-width: 32px;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

/* ---------- 状态栏 ---------- */
QStatusBar {
    background: transparent;
    color: $text_sub;
    border-top: 1px solid $border_soft;
    min-height: 20px;
    padding: 4px 14px;
}
QStatusBar::item { border: none; }
QStatusBar QLabel { padding: 0 6px; }

/* ---------- 小工具按钮（帮助徽标等）---------- */
QToolButton {
    background: $surface_soft;
    border: 1px solid $border;
    border-radius: 10px;
    color: $text_sub;
    padding: 0;
}
QToolButton:hover { border-color: $accent; color: $accent; }
QToolButton#helpBadge {
    font-size: 11px;
    font-weight: 700;
    border-radius: 9px;
}

/* ---------- 帮助气泡 ---------- */
QLabel#helpPopup {
    background: $surface;
    color: $text;
    border: 1px solid $border;
    border-radius: 10px;
    padding: 10px 12px;
}

/* ---------- 文本角色 ---------- */
QLabel#sidebarFooter {
    font-size: 11px;
    color: $text_sub;
    padding: 0 6px;
}
QLabel#badge {
    background: $accent_soft;
    color: $accent;
    border: none;
    border-radius: 9px;
    padding: 1px 9px;
    font-size: 11px;
    font-weight: 700;
}

/* ---------- 文本角色 ---------- */
QLabel#muted { color: $text_mute; }
QLabel#sub { color: $text_sub; }
QLabel#ok { color: $success; }
QLabel#warn { color: $warn; }
QLabel#err { color: $danger; }
QLabel#title {
    font-size: 20px;
    font-weight: 700;
    padding-bottom: 2px;
}
QLabel#sectionTitle {
    font-size: 12px;
    font-weight: 700;
    color: $text_sub;
    letter-spacing: 0.6px;
}
QTextEdit#output {
    background: $surface;
    border: 1px solid $border;
    border-radius: $radius_lg;
    padding: 14px;
    font-size: 14px;
    line-height: 1.7;
}

/* ---------- 自定义标题栏（仅毛玻璃主题）---------- */
QWidget#titleBar { background: transparent; }
QToolButton#winBtn {
    border: none;
    border-radius: 6px;
    background: transparent;
    color: $text_sub;
    font-size: 13px;
}
QToolButton#winBtn:hover { background: $surface_alt; color: $text; }
QToolButton#winClose {
    border: none;
    border-radius: 6px;
    background: transparent;
    color: $text_sub;
    font-size: 13px;
}
QToolButton#winClose:hover { background: $danger; color: #FFFFFF; }

/* ---------- 工具提示 ---------- */
QToolTip {
    background: $surface;
    color: $text;
    border: 1px solid $border;
    border-radius: 8px;
    padding: 6px 8px;
}
"""
)


def build_qss(theme: Theme) -> str:
    """按主题令牌生成全局样式表。"""
    qss = _QSS.substitute(
        font_family=FONT_FAMILY,
        mono_family=MONO_FAMILY,
        win_bg=theme.win_bg,
        sidebar_bg=theme.sidebar_bg,
        surface=theme.surface,
        surface_soft=theme.surface_soft,
        surface_alt=theme.surface_alt,
        border=theme.border,
        border_soft=theme.border_soft,
        text=theme.text,
        text_sub=theme.text_sub,
        text_mute=theme.text_mute,
        accent=theme.accent,
        accent_hover=theme.accent_hover,
        accent_soft=theme.accent_soft,
        danger=theme.danger,
        danger_soft=theme.danger_soft,
        success=theme.success,
        warn=theme.warn,
        scroll=theme.scroll,
        radius=f"{theme.radius}px",
        radius_lg=f"{theme.radius_lg}px",
    )
    if theme.glass:
        # 毛玻璃主题下窗口本身是半透明的，状态栏直接裸在壁纸上会看不清，
        # 给它垫一层薄底，顺便形成苹果式的底部工具条。
        qss += """
QStatusBar {
    background: rgba(255, 255, 255, 0.26);
    color: #2C3138;
}
"""
    return qss


# 向后兼容：老代码（gui.py / 测试）直接 import QSS
QSS = build_qss(LIGHT)
CARD = "card"
