"""苹果式设置控件：分组卡片 + 一行一项 + 发丝分割线。

控件对齐方式可配：
    align="left"（默认）标签列固定宽度，控件紧跟在标签后面 —— 紧凑，接近原 QFormLayout；
    align="right"       控件贴右边缘 —— macOS 系统设置那种，宽控件时空隙会比较大。

用法：
    card = SettingCard("外观")
    card.add_row(SettingRow("主题", self.cmb_theme, hint="跟随系统深浅色"))
    layout.addWidget(card)
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget,
)

LABEL_WIDTH = 132   # 左侧标签列宽度，保证所有行的控件左边缘对齐


class SettingRow(QWidget):
    """一行设置：左侧标题(+说明)，右侧控件。除最后一行外底部带发丝线。"""

    def __init__(self, title: str, control: QWidget, *, hint: str = "",
                 help_text: str = "", help_provider=None, last: bool = False,
                 align: str = "left", label_width: int = LABEL_WIDTH,
                 dense: bool = False, parent: QWidget | None = None):
        super().__init__(parent)
        self._title = title

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        pad_y = 8 if dense else 11
        content = QHBoxLayout()
        content.setContentsMargins(16, pad_y, 16, pad_y)
        content.setSpacing(14)

        left = QVBoxLayout()
        left.setContentsMargins(0, 0, 0, 0)
        left.setSpacing(2)

        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(6)
        self.lbl_title = QLabel(title)
        self.lbl_title.setObjectName("rowTitle")
        title_row.addWidget(self.lbl_title)

        if help_text and help_provider is not None:
            title_row.addWidget(help_provider.label("", help_text))
        title_row.addStretch(1)
        left.addLayout(title_row)

        self.lbl_hint = QLabel(hint)
        self.lbl_hint.setObjectName("rowHint")
        self.lbl_hint.setWordWrap(True)
        self.lbl_hint.setVisible(bool(hint))
        left.addWidget(self.lbl_hint)

        left_host = QWidget()
        left_host.setLayout(left)
        left_host.setFixedWidth(label_width)

        control.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.control = control

        if align == "right":
            # 标签列占满剩余空间，控件才能贴到右边缘
            content.addWidget(left_host, 1, Qt.AlignVCenter | Qt.AlignLeft)
            content.addWidget(control, 0, Qt.AlignRight | Qt.AlignVCenter)
        else:
            content.addWidget(left_host, 0, Qt.AlignVCenter | Qt.AlignLeft)
            content.addWidget(control, 0, Qt.AlignLeft | Qt.AlignVCenter)
            content.addStretch(1)
        outer.addLayout(content)

        if not last:
            outer.addWidget(_hairline())

    def set_hint(self, text: str) -> None:
        self.lbl_hint.setText(text)
        self.lbl_hint.setVisible(bool(text))


class SettingCard(QFrame):
    """一组设置行，圆角卡片，行间由 SettingRow 自己画发丝线。"""

    def __init__(self, title: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("card")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        if title:
            header = QLabel(title)
            header.setObjectName("sectionTitle")
            header_wrap = QHBoxLayout()
            header_wrap.setContentsMargins(16, 12, 16, 6)
            header_wrap.addWidget(header)
            header_wrap.addStretch(1)
            outer.addLayout(header_wrap)

        self._rows = QVBoxLayout()
        self._rows.setContentsMargins(0, 0, 0, 0)
        self._rows.setSpacing(0)
        outer.addLayout(self._rows)

    def add_row(self, row: SettingRow) -> SettingRow:
        self._rows.addWidget(row)
        return row

    def add_widget(self, widget: QWidget) -> QWidget:
        self._rows.addWidget(widget)
        return widget


def _hairline() -> QFrame:
    line = QFrame()
    line.setObjectName("hairline")
    line.setFixedHeight(1)
    return line
