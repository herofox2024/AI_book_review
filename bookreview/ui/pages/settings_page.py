"""设置页：模型服务商、API Key、双模型分流、推理预算与并发、外观主题。

版式走 macOS 系统设置那一路：分组卡片 → 一行一项 → 行间发丝线 → 右侧控件右对齐。
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QDoubleSpinBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPushButton, QScrollArea, QSizePolicy, QSpinBox, QVBoxLayout, QWidget,
)

from ...core.config import PRESETS, Settings
from ...core.pipeline import Pipeline
from ..parameter_help import ParameterHelp
from ..theme import THEME_CHOICES
from ..widgets import SettingCard, SettingRow
from ..workers import PingWorker

INPUT_WIDTH = 340


def _wide(widget: QWidget, width: int = INPUT_WIDTH) -> QWidget:
    widget.setMinimumWidth(width)
    return widget


class SettingsPage(QWidget):
    def __init__(self, pipeline: Pipeline, on_saved=None, on_theme=None, parent=None):
        super().__init__(parent)
        self.pipe = pipeline
        self.on_saved = on_saved
        self.on_theme = on_theme
        self._ping: PingWorker | None = None
        self.help = ParameterHelp(self)
        self._build_ui()
        self._load()

    # ---------- 界面 ----------
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(12)

        title = QLabel("设置")
        title.setObjectName("title")
        root.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        body = QWidget()
        lay = QVBoxLayout(body)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)

        # --- 外观 ---
        self.cmb_theme = QComboBox()
        _wide(self.cmb_theme, 220)
        for key, label, hint in THEME_CHOICES:
            self.cmb_theme.addItem(label, key)
            self.cmb_theme.setItemData(
                self.cmb_theme.count() - 1, f"{label} —— {hint}", Qt.ToolTipRole
            )
        self.cmb_theme.currentIndexChanged.connect(self._preview_theme)

        appearance = SettingCard("外观")
        self.row_theme = appearance.add_row(
            SettingRow(
                "主题",
                self.cmb_theme,
                hint=THEME_CHOICES[0][2],
                help_text=(
                    "透明水晶：无边框 + Windows 11 亚克力毛玻璃。\n"
                    "跟随系统：系统深色就用深色配色，反之用浅色。\n"
                    "黑色：固定深色，夜里更省眼。\n"
                    "切换即时预览，点保存才会记住。"
                ),
                help_provider=self.help,
                last=True,
            )
        )
        lay.addWidget(appearance)

        # --- 模型服务 ---
        self.cmb_provider = QComboBox()
        for key in PRESETS:
            self.cmb_provider.addItem(key if key != "custom" else "custom（自定义）", key)
        self.cmb_provider.currentIndexChanged.connect(self._on_provider)

        self.ed_base = _wide(QLineEdit())
        self.ed_key = _wide(QLineEdit())
        self.ed_key.setEchoMode(QLineEdit.Password)
        self.ed_key.setPlaceholderText("sk-…")
        self.ed_model = _wide(QLineEdit())
        self.ed_model.setPlaceholderText("分块摘要用的模型，建议便宜的")
        self.ed_review = _wide(QLineEdit())
        self.ed_review.setPlaceholderText("生成书评用的模型，留空则复用上面的")

        service = SettingCard("模型服务")
        service.add_row(SettingRow(
            "服务商", self.cmb_provider,
            help_text="选择提供大模型 API 的平台。选择预设服务商会自动填写接口地址和推荐摘要模型。",
            help_provider=self.help,
        ))
        service.add_row(SettingRow(
            "Base URL", self.ed_base,
            help_text="OpenAI 兼容接口的基础地址。使用预设服务商时通常不需要手动修改。",
            help_provider=self.help,
        ))
        service.add_row(SettingRow(
            "API Key", self.ed_key,
            help_text="服务商分配的访问密钥。也可用 BOOKREVIEW_API_KEY 环境变量，避免写进配置文件。",
            help_provider=self.help,
        ))
        service.add_row(SettingRow(
            "摘要模型", self.ed_model,
            help_text="用于分块阅读和全书理解，调用次数多，建议选便宜、长文本稳定的模型。",
            help_provider=self.help,
        ))
        service.add_row(SettingRow(
            "生成模型", self.ed_review,
            hint="留空则复用摘要模型",
            help_text="用于最终书评写作，只调用少量次数，可以选质量更高的模型。",
            help_provider=self.help,
            last=True,
        ))
        lay.addWidget(service)

        # --- 高级参数 ---
        self.sp_reserve = QDoubleSpinBox()
        _wide(self.sp_reserve, 150)
        self.sp_reserve.setRange(1.0, 10.0)
        self.sp_reserve.setSingleStep(0.5)
        self.sp_cap = QSpinBox()
        _wide(self.sp_cap, 150)
        self.sp_cap.setRange(1024, 65536)
        self.sp_cap.setSingleStep(1024)
        self.sp_conc = QSpinBox()
        _wide(self.sp_conc, 150)
        self.sp_conc.setRange(1, 16)

        advanced = SettingCard("高级参数")
        advanced.add_row(SettingRow(
            "推理预算系数", self.sp_reserve,
            help_text=(
                "推理模型（deepseek-v4-*）的思维链会占用输出预算。\n"
                "实际请求上限 = max_tokens × 此系数；非推理模型设为 1.0。"
            ),
            help_provider=self.help,
        ))
        advanced.add_row(SettingRow(
            "输出上限", self.sp_cap,
            help_text="单次请求允许的最大输出 token，含推理过程和正文。太小会导致输出被截断。",
            help_provider=self.help,
        ))
        advanced.add_row(SettingRow(
            "摘要并发", self.sp_conc,
            help_text="同时处理的摘要请求数。越大越快，也越容易触发限流；建议 2-4。",
            help_provider=self.help,
            last=True,
        ))
        lay.addWidget(advanced)

        lay.addStretch(1)
        scroll.setWidget(body)
        root.addWidget(scroll, 1)

        # --- 操作条：固定在页面底部，不随卡片一起滚走 ---
        actions = QHBoxLayout()
        actions.setContentsMargins(2, 0, 2, 0)
        btn_save = QPushButton("保存")
        btn_save.setObjectName("primary")
        btn_save.clicked.connect(self._save)
        self.btn_ping = QPushButton("测试连接")
        self.btn_ping.clicked.connect(self._ping_test)
        self.lbl_state = QLabel("")
        self.lbl_state.setObjectName("sub")
        self.lbl_state.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        actions.addWidget(btn_save)
        actions.addWidget(self.btn_ping)
        actions.addWidget(self.lbl_state, 1)
        root.addLayout(actions)

    # ---------- 载入 / 保存 ----------
    def _load(self) -> None:
        s: Settings = self.pipe.settings

        idx = self.cmb_provider.findData(s.llm.provider)
        self.cmb_provider.blockSignals(True)
        self.cmb_provider.setCurrentIndex(idx if idx >= 0 else 0)
        self.cmb_provider.blockSignals(False)

        self.ed_base.setText(s.llm.base_url)
        self.ed_key.setText(s.llm.api_key)
        self.ed_model.setText(s.llm.model)
        self.ed_review.setText(s.llm.review_model)
        self.sp_reserve.setValue(float(s.llm.reasoning_reserve))
        self.sp_cap.setValue(int(s.llm.max_output_cap))
        self.sp_conc.setValue(int(s.pipeline.concurrency))

        theme_key = getattr(s.ui, "theme", "crystal")
        theme_idx = self.cmb_theme.findData(theme_key)
        self.cmb_theme.blockSignals(True)
        self.cmb_theme.setCurrentIndex(theme_idx if theme_idx >= 0 else 0)
        self.cmb_theme.blockSignals(False)
        self._update_theme_hint()

    def _update_theme_hint(self) -> None:
        key = self.cmb_theme.currentData()
        hint = next((h for k, _, h in THEME_CHOICES if k == key), "")
        self.row_theme.set_hint(hint)

    def _preview_theme(self) -> None:
        """切换即预览（不落盘，保存后才记住）。"""
        self._update_theme_hint()
        if self.on_theme:
            self.on_theme(self.cmb_theme.currentData())

    def _on_provider(self) -> None:
        key = self.cmb_provider.currentData()
        preset = PRESETS.get(key)
        if preset and preset.get("base_url"):
            self.ed_base.setText(preset["base_url"])
            if not self.ed_model.text().strip() or preset.get("model"):
                self.ed_model.setText(preset["model"])

    def _save(self) -> None:
        s: Settings = self.pipe.settings
        s.llm.provider = self.cmb_provider.currentData()
        s.llm.base_url = self.ed_base.text().strip()
        s.llm.api_key = self.ed_key.text().strip()
        s.llm.model = self.ed_model.text().strip()
        s.llm.review_model = self.ed_review.text().strip()
        s.llm.reasoning_reserve = self.sp_reserve.value()
        s.llm.max_output_cap = self.sp_cap.value()
        s.pipeline.concurrency = self.sp_conc.value()
        s.ui.theme = self.cmb_theme.currentData() or "crystal"
        s.save()

        # 重建 pipeline，让新配置立即生效
        new_pipe = Pipeline()
        self.pipe = new_pipe
        if self.on_saved:
            self.on_saved(new_pipe)
        self.lbl_state.setText("已保存")
        self.lbl_state.setObjectName("ok")
        self.lbl_state.setStyleSheet("")

    def _ping_test(self) -> None:
        self.btn_ping.setEnabled(False)
        self.lbl_state.setText("测试中…")
        self.lbl_state.setObjectName("sub")
        self.lbl_state.setStyleSheet("")
        self._ping = PingWorker(self.pipe)
        self._ping.done.connect(self._on_ping)
        self._ping.start()

    def _on_ping(self, ok: bool, msg: str) -> None:
        self.btn_ping.setEnabled(True)
        self.lbl_state.setText(("连接正常：" if ok else "连接失败：") + msg[:60])
        self.lbl_state.setObjectName("ok" if ok else "err")
        self.lbl_state.setStyleSheet("")
        self.lbl_state.setToolTip(msg)
        if not ok:
            QMessageBox.warning(self, "连接失败", msg)
