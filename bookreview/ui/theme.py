"""浅色主题：配色常量与全局样式表。

只做一套浅色配色，和 IDE 主题保持一致。所有页面共用这里的 QSS，
改配色只需要动这个文件。
"""

from __future__ import annotations

# ---------- 配色 ----------
BG = "#F7F8FA"          # 窗口底色
SURFACE = "#FFFFFF"     # 卡片/面板
BORDER = "#E3E6EB"      # 分隔线
TEXT = "#1F2329"        # 主文本
TEXT_SUB = "#646A73"    # 次要文本
TEXT_MUTE = "#8F959E"   # 占位/禁用
ACCENT = "#2E6BE6"      # 主色（按钮、选中）
ACCENT_HOVER = "#4079EC"
ACCENT_SOFT = "#EAF1FE"  # 选中底色
DANGER = "#D83931"
SUCCESS = "#2BA471"
WARN = "#D87A16"

# ---------- 尺寸 ----------
RADIUS = 8
FONT_FAMILY = "Microsoft YaHei UI, Microsoft YaHei, PingFang SC, sans-serif"

QSS = f"""
QWidget {{
    font-family: {FONT_FAMILY};
    font-size: 13px;
    color: {TEXT};
}}

QMainWindow, QDialog {{
    background: {BG};
}}

/* ---------- 卡片 ---------- */
QFrame#card {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: {RADIUS}px;
}}

/* ---------- 按钮 ---------- */
QPushButton {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 6px 14px;
    color: {TEXT};
}}
QPushButton:hover {{ background: {ACCENT_SOFT}; border-color: {ACCENT}; }}
QPushButton:disabled {{ color: {TEXT_MUTE}; background: #F2F3F5; border-color: {BORDER}; }}

QPushButton#primary {{
    background: {ACCENT}; border: 1px solid {ACCENT}; color: #FFFFFF; font-weight: 600;
}}
QPushButton#primary:hover {{ background: {ACCENT_HOVER}; border-color: {ACCENT_HOVER}; }}
QPushButton#primary:disabled {{ background: #A9C4F5; border-color: #A9C4F5; color: #FFFFFF; }}

QPushButton#danger {{ color: {DANGER}; }}
QPushButton#danger:hover {{ background: #FDECEC; border-color: {DANGER}; }}

QPushButton#link {{
    border: none; background: transparent; color: {ACCENT}; padding: 2px 4px;
}}
QPushButton#link:hover {{ background: {ACCENT_SOFT}; }}

/* ---------- 输入 ---------- */
QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 6px 8px;
    selection-background-color: {ACCENT_SOFT};
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus {{
    border-color: {ACCENT};
}}
QComboBox::drop-down {{ border: none; width: 20px; }}
QComboBox QAbstractItemView {{
    border: 1px solid {BORDER}; background: {SURFACE}; selection-background-color: {ACCENT_SOFT};
}}

/* ---------- 列表 / 表格 ---------- */
QListWidget, QTableWidget, QTreeWidget {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: {RADIUS}px;
    outline: none;
}}
QListWidget::item {{ padding: 8px 10px; border-bottom: 1px solid {BORDER}; }}
QListWidget::item:selected {{ background: {ACCENT_SOFT}; color: {TEXT}; }}
QListWidget::item:hover {{ background: #F2F5FB; }}

QTableWidget {{
    gridline-color: {BORDER};
}}
QHeaderView::section {{
    background: #FAFBFC; border: none; border-bottom: 1px solid {BORDER};
    padding: 8px 10px; font-weight: 600; color: {TEXT_SUB};
}}

/* ---------- 分组 ---------- */
QGroupBox {{
    border: 1px solid {BORDER};
    border-radius: {RADIUS}px;
    margin-top: 14px;
    padding: 12px 12px 10px 12px;
    background: {SURFACE};
}}
QGroupBox::title {{
    subcontrol-origin: margin; subcontrol-position: top left;
    left: 12px; padding: 0 6px; color: {TEXT_SUB}; font-weight: 600;
}}

/* ---------- 进度 ---------- */
QProgressBar {{
    border: 1px solid {BORDER}; border-radius: 6px; background: #F2F3F5;
    height: 18px; text-align: center; color: {TEXT_SUB};
}}
QProgressBar::chunk {{ background: {ACCENT}; border-radius: 5px; }}

/* ---------- 标签页 / 导航 ---------- */
QTabWidget::pane {{ border: none; background: {BG}; }}
QTabBar::tab {{
    padding: 8px 18px; margin-right: 4px; border-radius: 6px; color: {TEXT_SUB};
}}
QTabBar::tab:selected {{ background: {SURFACE}; color: {TEXT}; font-weight: 600; }}
QTabBar::tab:hover {{ color: {TEXT}; }}

/* ---------- 滚动条 ---------- */
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 0; }}
QScrollBar::handle:vertical {{ background: #D4D8DE; border-radius: 5px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: #BFC5CD; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; }}
QScrollBar::handle:horizontal {{ background: #D4D8DE; border-radius: 5px; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

/* ---------- 状态标签 ---------- */
QLabel#muted {{ color: {TEXT_MUTE}; }}
QLabel#sub {{ color: {TEXT_SUB}; }}
QLabel#ok {{ color: {SUCCESS}; }}
QLabel#warn {{ color: {WARN}; }}
QLabel#err {{ color: {DANGER}; }}
QLabel#title {{ font-size: 16px; font-weight: 600; }}
"""

CARD = "card"
