"""风格卡页：列表、从样本学习、可视化编辑关键字段、导入导出 JSON。"""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout, QFrame, QHBoxLayout,
    QInputDialog, QLabel, QLineEdit, QMessageBox, QPlainTextEdit, QPushButton,
    QSplitter, QTextEdit, QVBoxLayout, QWidget,
)

from ...core.pipeline import Pipeline
from ..workers import StyleLearnWorker
from ..parameter_help import ParameterHelp

SPOILER_LABEL = {
    "blur": "blur — 推理/悬疑防泄底（模糊化诡计与真相）",
    "partial": "partial — 不点破真凶与核心反转",
    "none": "none — 严格不剧透",
    "full": "full — 充分展开剧情",
}


class StylePage(QWidget):
    profiles_changed = Signal()

    def __init__(self, pipeline: Pipeline, parent=None):
        super().__init__(parent)
        self.pipe = pipeline
        self._profiles: list[dict] = []
        self._worker: StyleLearnWorker | None = None
        self.help = ParameterHelp(self)
        self._build_ui()
        self.reload()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(12)

        head = QHBoxLayout()
        t = QLabel("风格画像")
        t.setObjectName("title")
        head.addWidget(t)
        head.addStretch(1)
        btn_learn = QPushButton("从样本学习…")
        btn_learn.clicked.connect(self._learn)
        btn_import = QPushButton("导入 JSON")
        btn_import.clicked.connect(self._import)
        btn_del = QPushButton("删除")
        btn_del.setObjectName("danger")
        btn_del.clicked.connect(self._delete)
        btn_cleanup = QPushButton("清理重复")
        btn_cleanup.setToolTip("同名或带版本后缀的风格卡只保留最新一张")
        btn_cleanup.clicked.connect(self._cleanup_duplicates)
        head.addWidget(btn_learn)
        head.addWidget(btn_import)
        head.addWidget(btn_cleanup)
        head.addWidget(btn_del)
        root.addLayout(head)

        split = QSplitter(Qt.Horizontal)

        # 左：列表
        left = QFrame()
        left.setObjectName("card")
        llay = QVBoxLayout(left)
        llay.setContentsMargins(10, 10, 10, 10)
        self.cmb = QComboBox()
        self.cmb.currentIndexChanged.connect(self._on_pick)
        llay.addWidget(QLabel("已保存的风格卡"))
        llay.addWidget(self.cmb)
        self.lbl_info = QLabel("")
        self.lbl_info.setObjectName("sub")
        self.lbl_info.setWordWrap(True)
        llay.addWidget(self.lbl_info)
        llay.addStretch(1)
        split.addWidget(left)

        # 右：编辑
        right = QFrame()
        right.setObjectName("card")
        rlay = QVBoxLayout(right)
        rlay.setContentsMargins(14, 12, 14, 12)
        rlay.setSpacing(10)

        form = QFormLayout()
        form.setSpacing(8)
        self.ed_name = QLineEdit()
        self.ed_self = QLineEdit()
        self.ed_self.setPlaceholderText("如：非帅（留空则不用自称）")
        self.ed_identity = QLineEdit()
        self.ed_identity.setPlaceholderText("如：本格推理爱好者，追系列作品")
        self.cmb_spoiler = QComboBox()
        for k, v in SPOILER_LABEL.items():
            self.cmb_spoiler.addItem(v, k)
        form.addRow(self.help.label("名称", "风格卡在生成页中的显示名称。同名重新学习时会更新已有风格卡，不会创建重复卡。"), self.ed_name)
        form.addRow(self.help.label("自称", "书评正文中对自己的固定称呼，例如“非帅”。留空时模型使用普通第一人称。"), self.ed_self)
        form.addRow(self.help.label("人设", "写作者的身份和阅读立场，例如“本格推理爱好者”。它会影响评价角度和专业表达。"), self.ed_identity)
        form.addRow(self.help.label("剧透策略", "blur：模糊关键诡计与真相；partial：可谈部分剧情但不点破核心反转；none：严格不剧透；full：允许充分展开剧情。"), self.cmb_spoiler)
        rlay.addLayout(form)

        # 语气滑块
        tone_row = QHBoxLayout()
        self.sp_form = self._slider("正式度", "0 更口语随意，1 更正式书面。数值只表示倾向，不是文章质量评分。")
        self.sp_emo = self._slider("情感浓度", "0 更克制冷静，1 情绪表达更强烈，会增加感叹、个人感受和态度表达。")
        self.sp_sharp = self._slider("批判锋利度", "0 更温和委婉，1 更直接尖锐。较高数值会更明确地指出作品短板。")
        for w in (self.sp_form, self.sp_emo, self.sp_sharp):
            tone_row.addWidget(w)
        rlay.addLayout(tone_row)

        rlay.addWidget(QLabel("完整 JSON（可手动微调）"))
        self.ed_json = QPlainTextEdit()
        self.ed_json.setPlaceholderText("选中左侧风格卡后显示完整配置")
        rlay.addWidget(self.ed_json, 1)

        btn_row = QHBoxLayout()
        self.btn_apply = QPushButton("用面板覆盖 JSON")
        self.btn_apply.clicked.connect(self._apply_panel)
        btn_save = QPushButton("保存")
        btn_save.setObjectName("primary")
        btn_save.clicked.connect(self._save)
        btn_export = QPushButton("导出 JSON")
        btn_export.clicked.connect(self._export)
        btn_row.addWidget(self.btn_apply)
        btn_row.addStretch(1)
        btn_row.addWidget(btn_export)
        btn_row.addWidget(btn_save)
        rlay.addLayout(btn_row)

        split.addWidget(right)
        split.setStretchFactor(0, 2)
        split.setStretchFactor(1, 5)
        root.addWidget(split, 1)

    def _slider(self, label: str, help_text: str) -> QWidget:
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        lay.addWidget(self.help.label(label, help_text))
        sp = QDoubleSpinBox()
        sp.setRange(0.0, 1.0)
        sp.setSingleStep(0.05)
        sp.setDecimals(2)
        lay.addWidget(sp)
        box.sp = sp  # type: ignore[attr-defined]
        return box

    # ---------- 数据 ----------
    def set_pipeline(self, pipeline: Pipeline) -> None:
        self.pipe = pipeline
        self.reload()

    def reload(self) -> None:
        self._profiles = [dict(r) for r in self.pipe.list_profiles()]
        self.cmb.blockSignals(True)
        self.cmb.clear()
        for p in self._profiles:
            self.cmb.addItem(f"{p['name']}  #{p['id']}", p["id"])
        self.cmb.blockSignals(False)
        if self._profiles:
            self.cmb.setCurrentIndex(0)
        self._on_pick()

    def _current_id(self) -> int | None:
        return self.cmb.currentData()

    def _on_pick(self) -> None:
        pid = self._current_id()
        if not pid:
            self.lbl_info.setText("还没有风格卡")
            self.ed_json.clear()
            return
        prof = self.pipe.get_profile(pid) or {}
        persona = prof.get("persona") or {}
        tone = prof.get("tone") or {}
        self.ed_name.setText(prof.get("name", ""))
        self.ed_self.setText(persona.get("self_name", ""))
        self.ed_identity.setText(persona.get("identity", ""))
        sp = prof.get("spoiler_policy") or "none"
        idx = self.cmb_spoiler.findData(sp)
        self.cmb_spoiler.setCurrentIndex(idx if idx >= 0 else 0)
        self.sp_form.sp.setValue(float(tone.get("formality", 0.5) or 0))  # type: ignore[attr-defined]
        self.sp_emo.sp.setValue(float(tone.get("emotion", 0.5) or 0))  # type: ignore[attr-defined]
        self.sp_sharp.sp.setValue(float(tone.get("critique_sharpness", 0.5) or 0))  # type: ignore[attr-defined]
        self.ed_json.setPlainText(json.dumps(prof, ensure_ascii=False, indent=2))
        st = prof.get("_stats") or {}
        bits = [f"样本 {prof.get('sample_count', st.get('sample_count', 0))} 篇"]
        if st.get("total_chars"):
            bits.append(f"{st['total_chars']} 字")
        if st.get("confidence"):
            bits.append(f"置信度 {st['confidence']}")
        if st.get("self_name"):
            bits.append(f"自称「{st['self_name']}」")
        self.lbl_info.setText("　".join(bits))

    # ---------- 操作 ----------
    def _apply_panel(self) -> None:
        """把面板上的字段写回 JSON 文本框（不落库）。"""
        try:
            data = json.loads(self.ed_json.toPlainText() or "{}")
        except json.JSONDecodeError as e:
            QMessageBox.warning(self, "JSON 有误", f"先修正 JSON 再覆盖：{e}")
            return
        data["name"] = self.ed_name.text().strip() or data.get("name", "我的风格")
        data.setdefault("persona", {})
        data["persona"]["self_name"] = self.ed_self.text().strip()
        data["persona"]["identity"] = self.ed_identity.text().strip()
        data["spoiler_policy"] = self.cmb_spoiler.currentData()
        data.setdefault("tone", {})
        data["tone"]["formality"] = self.sp_form.sp.value()  # type: ignore[attr-defined]
        data["tone"]["emotion"] = self.sp_emo.sp.value()  # type: ignore[attr-defined]
        data["tone"]["critique_sharpness"] = self.sp_sharp.sp.value()  # type: ignore[attr-defined]
        self.ed_json.setPlainText(json.dumps(data, ensure_ascii=False, indent=2))

    def _save(self) -> None:
        pid = self._current_id()
        if not pid:
            return
        try:
            data = json.loads(self.ed_json.toPlainText())
        except json.JSONDecodeError as e:
            QMessageBox.warning(self, "JSON 有误", str(e))
            return
        self.pipe.db.save_profile(
            data.get("name") or "我的风格", data,
            data.get("_stats", {}).get("sample_count", 0), pid,
        )
        QMessageBox.information(self, "已保存", "风格卡已更新")
        self.reload()
        self.profiles_changed.emit()

    def _delete(self) -> None:
        pid = self._current_id()
        if not pid:
            return
        if QMessageBox.question(self, "确认删除", "删除这张风格卡？") != QMessageBox.Yes:
            return
        self.pipe.db.delete_profile(pid)
        self.reload()
        self.profiles_changed.emit()

    def _cleanup_duplicates(self) -> None:
        plan = self.pipe.db.plan_dedupe_profiles()
        if not plan:
            QMessageBox.information(self, "无需清理", "没有发现重复风格卡。")
            return
        duplicate_count = sum(len(item["remove"]) for item in plan)
        if QMessageBox.question(self, "确认清理", f"发现 {duplicate_count} 张重复卡，保留每组最新版本并删除旧卡？") != QMessageBox.Yes:
            return
        removed = self.pipe.db.apply_dedupe_profiles(plan)
        self.reload()
        self.profiles_changed.emit()
        QMessageBox.information(self, "清理完成", f"已清理 {removed} 张重复风格卡。")

    def _import(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "导入风格卡", "style_presets", "JSON (*.json)"
        )
        if not path:
            return
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except Exception as e:
            QMessageBox.warning(self, "导入失败", str(e))
            return
        name = data.get("name") or Path(path).stem
        pid = self.pipe.db.save_profile(name, data, data.get("_stats", {}).get("sample_count", 0))
        self.reload()
        idx = self.cmb.findData(pid)
        if idx >= 0:
            self.cmb.setCurrentIndex(idx)
        self.profiles_changed.emit()
        QMessageBox.information(self, "已导入", f"{name}  (#{pid})")

    def _export(self) -> None:
        pid = self._current_id()
        if not pid:
            return
        prof = self.pipe.get_profile(pid) or {}
        name = prof.get("name", "风格卡").replace("/", "_")
        path, _ = QFileDialog.getSaveFileName(
            self, "导出风格卡", f"{name}.json", "JSON (*.json)"
        )
        if not path:
            return
        Path(path).write_text(json.dumps(prof, ensure_ascii=False, indent=2), encoding="utf-8")
        QMessageBox.information(self, "已导出", path)

    def _learn(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "选择你的书评样本（可多选）", "",
            "文本 (*.md *.txt);;Word (*.docx);;全部文件 (*.*)",
        )
        if not paths:
            return
        name, ok = QInputDialog.getText(
            self, "风格卡名称", "给这张风格卡起个名字：", text="我的风格"
        )
        if not ok or not name.strip():
            return
        hint, ok2 = QInputDialog.getText(
            self, "补充说明（可选）",
            "想额外告诉模型什么？例如：我写推理书评不泄底。", text=""
        )
        self.btn_apply.setEnabled(False)
        self._worker = StyleLearnWorker(self.pipe, paths, name.strip(), hint if ok2 else "")
        self._worker.done.connect(self._on_learned)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_learned(self, pid: int, profile: dict) -> None:
        self.btn_apply.setEnabled(True)
        self.reload()
        idx = self.cmb.findData(pid)
        if idx >= 0:
            self.cmb.setCurrentIndex(idx)
        self.profiles_changed.emit()
        QMessageBox.information(self, "学习完成", f"已生成风格卡 #{pid}")

    def _on_failed(self, msg: str) -> None:
        self.btn_apply.setEnabled(True)
        QMessageBox.warning(self, "学习失败", msg)
