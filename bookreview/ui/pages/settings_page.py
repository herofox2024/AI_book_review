"""设置页：模型服务商、API Key、双模型分流、推理预算与并发。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QDoubleSpinBox, QFormLayout, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPushButton, QSpinBox, QVBoxLayout, QWidget,
)

from ...core.config import PRESETS, Settings
from ...core.pipeline import Pipeline
from ..workers import PingWorker
from ..parameter_help import ParameterHelp


class SettingsPage(QWidget):
    def __init__(self, pipeline: Pipeline, on_saved=None, parent=None):
        super().__init__(parent)
        self.pipe = pipeline
        self.on_saved = on_saved
        self._ping: PingWorker | None = None
        self.help = ParameterHelp(self)
        self._build_ui()
        self._load()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(12)

        t = QLabel("设置")
        t.setObjectName("title")
        root.addWidget(t)

        card = QFrame()
        card.setObjectName("card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 14, 16, 14)
        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignRight)

        self.cmb_provider = QComboBox()
        for k, v in PRESETS.items():
            label = k if k != "custom" else "custom（自定义）"
            self.cmb_provider.addItem(label, k)
        self.ed_base = QLineEdit()
        self.ed_key = QLineEdit()
        self.ed_key.setEchoMode(QLineEdit.Password)
        self.ed_key.setPlaceholderText("sk-…")
        self.ed_model = QLineEdit()
        self.ed_model.setPlaceholderText("分块摘要用的模型，建议便宜的")
        self.ed_review = QLineEdit()
        self.ed_review.setPlaceholderText("生成书评用的模型，留空则复用上面的")

        self.sp_reserve = QDoubleSpinBox()
        self.sp_reserve.setRange(1.0, 10.0)
        self.sp_reserve.setSingleStep(0.5)
        self.sp_reserve.setToolTip(
            "推理模型（deepseek-v4-*）的思维链会占用输出预算。\n"
            "请求预算 = max_tokens × 这个系数。非推理模型设为 1.0。"
        )
        self.sp_cap = QSpinBox()
        self.sp_cap.setRange(1024, 65536)
        self.sp_cap.setSingleStep(1024)
        self.sp_conc = QSpinBox()
        self.sp_conc.setRange(1, 16)

        form.addRow(self.help.label("服务商", "选择提供大模型 API 的平台。选择预设服务商会自动填写接口地址和推荐摘要模型。"), self.cmb_provider)
        form.addRow(self.help.label("Base URL", "OpenAI 兼容接口的基础地址。使用预设服务商时通常不需要手动修改。"), self.ed_base)
        form.addRow(self.help.label("API Key", "服务商分配的访问密钥。也可使用 BOOKREVIEW_API_KEY 环境变量，避免把密钥写入配置文件。"), self.ed_key)
        form.addRow(self.help.label("摘要模型", "用于分块阅读和全书理解，调用次数较多，建议选择速度快、成本较低且长文本能力稳定的模型。"), self.ed_model)
        form.addRow(self.help.label("生成模型", "用于最终书评写作，只调用少量次数。可选择质量更高的模型；留空则使用摘要模型。"), self.ed_review)
        form.addRow(self.help.label("推理预算系数", "推理模型会消耗一部分预算进行思考。实际请求上限 = max_tokens × 此系数；普通模型建议设为 1.0。"), self.sp_reserve)
        form.addRow(self.help.label("输出上限", "单次模型请求允许使用的最大输出 token 数，包含推理过程和最终正文。过小可能导致输出被截断。"), self.sp_cap)
        form.addRow(self.help.label("摘要并发", "同时处理的摘要请求数量。数值越大速度越快，但更容易触发服务商限流；建议从 2-4 开始。"), self.sp_conc)
        lay.addLayout(form)

        row = QHBoxLayout()
        btn_save = QPushButton("保存")
        btn_save.setObjectName("primary")
        btn_save.clicked.connect(self._save)
        self.btn_ping = QPushButton("测试连接")
        self.btn_ping.clicked.connect(self._ping_test)
        self.lbl_state = QLabel("")
        self.lbl_state.setObjectName("sub")
        row.addWidget(btn_save)
        row.addWidget(self.btn_ping)
        row.addWidget(self.lbl_state, 1)
        lay.addLayout(row)

        root.addWidget(card)
        root.addStretch(1)

        self.cmb_provider.currentIndexChanged.connect(self._on_provider)

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
        self.sp_conc.setValue(int(self.pipe.settings.pipeline.concurrency))

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
