"""生成页：选书 → 构建理解卡 → 选风格/长度/侧重 → 生成书评。"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel, QMessageBox,
    QProgressBar, QPushButton, QTextEdit, QVBoxLayout, QWidget,
)

from ...core.models import Book, BookDigest
from ...core.pipeline import Pipeline
from ...core.prompts import FOCUS_PRESETS, LENGTH_PRESETS
from ..workers import DigestWorker, GenerateWorker, ParseWorker
from ..parameter_help import ParameterHelp

FILE_FILTER = (
    "电子书 (*.epub *.mobi *.azw3 *.docx *.txt *.md);;"
    "EPUB (*.epub);;Kindle (*.mobi *.azw3);;Word (*.docx);;全部文件 (*.*)"
)


class GeneratePage(QWidget):
    def __init__(self, pipeline: Pipeline, parent=None):
        super().__init__(parent)
        self.pipe = pipeline
        self.book: Book | None = None
        self.digest: BookDigest | None = None
        self._parse_w: ParseWorker | None = None
        self._digest_w: DigestWorker | None = None
        self._gen_w: GenerateWorker | None = None
        self.help = ParameterHelp(self)
        self._build_ui()
        self._refresh_profiles()

    # ---------- 界面 ----------
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(12)

        title = QLabel("生成书评")
        title.setObjectName("title")
        root.addWidget(title)

        # --- 选书 ---
        card = QFrame()
        card.setObjectName("card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(8)

        row = QHBoxLayout()
        self.btn_pick = QPushButton("选择电子书…")
        self.btn_pick.setObjectName("primary")
        self.btn_pick.clicked.connect(self._pick_file)
        self.lbl_file = QLabel("尚未选择文件（支持 epub / mobi / azw3 / docx）")
        self.lbl_file.setObjectName("sub")
        row.addWidget(self.btn_pick)
        row.addWidget(self.lbl_file, 1)
        lay.addLayout(row)

        self.lbl_book = QLabel("")
        self.lbl_book.setObjectName("muted")
        self.lbl_book.setWordWrap(True)
        lay.addWidget(self.lbl_book)
        root.addWidget(card)

        # --- 理解卡 ---
        dcard = QFrame()
        dcard.setObjectName("card")
        dlay = QVBoxLayout(dcard)
        dlay.setContentsMargins(14, 12, 14, 12)
        dlay.setSpacing(8)

        drow = QHBoxLayout()
        self.btn_digest = QPushButton("构建理解卡")
        self.btn_digest.clicked.connect(self._build_digest)
        self.btn_digest.setEnabled(False)
        self.chk_force = QPushButton("重建")
        self.chk_force.setObjectName("link")
        self.chk_force.setToolTip("忽略缓存重新构建（会再次消耗 token）")
        self.chk_force.clicked.connect(lambda: self._build_digest(force=True))
        self.chk_force.setEnabled(False)
        self.lbl_digest_state = QLabel("")
        self.lbl_digest_state.setObjectName("muted")
        drow.addWidget(self.btn_digest)
        drow.addWidget(self.chk_force)
        drow.addWidget(self.lbl_digest_state, 1)
        dlay.addLayout(drow)

        self.bar = QProgressBar()
        self.bar.setVisible(False)
        self.bar.setFormat("%p%  %v/%m")
        dlay.addWidget(self.bar)

        self.txt_digest = QTextEdit()
        self.txt_digest.setReadOnly(True)
        self.txt_digest.setPlaceholderText(
            "理解卡是全书压缩后的产物（约 3000 字）。\n"
            "同一本书只会构建一次，之后直接命中缓存，不重复消耗 token。"
        )
        self.txt_digest.setMinimumHeight(90)
        self.txt_digest.setMaximumHeight(150)
        dlay.addWidget(self.txt_digest)
        root.addWidget(dcard)

        # --- 选项 ---
        ocard = QFrame()
        ocard.setObjectName("card")
        olay = QVBoxLayout(ocard)
        olay.setContentsMargins(14, 12, 14, 12)
        olay.setSpacing(10)

        o_row = QHBoxLayout()
        o_row.addWidget(self.help.label("风格画像", "选择从你的书评样本中学习得到的写作风格卡。它会控制自称、语气、句式、结构和剧透习惯；不选择则使用默认书评风格。"))
        self.cmb_profile = QComboBox()
        self.cmb_profile.setMinimumWidth(220)
        o_row.addWidget(self.cmb_profile, 1)

        o_row.addSpacing(12)
        o_row.addWidget(self.help.label("长度", "短评：约 200-300 字，只讲核心判断。\n标准：约 800-1200 字，包含完整论证。\n深度长评：约 2000-3000 字，展开人物、结构和主题。"))
        self.cmb_length = QComboBox()
        for k, v in LENGTH_PRESETS.items():
            self.cmb_length.addItem(v["label"], k)
        self.cmb_length.setCurrentIndex(1)
        o_row.addWidget(self.cmb_length)

        o_row.addSpacing(12)
        o_row.addWidget(self.help.label("侧重", "综合：平衡情节、人物、文笔和主题。\n情节：重点分析结构、悬念和节奏。\n人物：重点分析动机和人物弧光。\n文笔：重点分析语言、意象和对话。\n主题：重点分析核心命题与现实呼应。"))
        self.cmb_focus = QComboBox()
        for k, v in FOCUS_PRESETS.items():
            self.cmb_focus.addItem(v.split("，")[0], k)
        o_row.addWidget(self.cmb_focus, 1)
        olay.addLayout(o_row)
        root.addWidget(ocard)

        # --- 生成 ---
        grow = QHBoxLayout()
        self.btn_gen = QPushButton("生成书评")
        self.btn_gen.setObjectName("primary")
        self.btn_gen.setEnabled(False)
        self.btn_gen.clicked.connect(self._generate)
        self.btn_stop = QPushButton("停止")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self._stop_generate)
        self.lbl_gen_state = QLabel("")
        self.lbl_gen_state.setObjectName("muted")
        grow.addWidget(self.btn_gen)
        grow.addWidget(self.btn_stop)
        grow.addWidget(self.lbl_gen_state, 1)
        root.addLayout(grow)

        self.txt_out = QTextEdit()
        self.txt_out.setPlaceholderText("生成的书评会出现在这里，边生成边显示。")
        root.addWidget(self.txt_out, 1)

        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setMaximumHeight(110)
        self.txt_log.setPlaceholderText("运行日志会显示在这里…")
        root.addWidget(self.txt_log)

        erow = QHBoxLayout()
        self.lbl_count = QLabel("")
        self.lbl_count.setObjectName("muted")
        btn_copy = QPushButton("复制")
        btn_copy.clicked.connect(self._copy)
        btn_save = QPushButton("导出…")
        btn_save.clicked.connect(self._export)
        erow.addWidget(self.lbl_count, 1)
        erow.addWidget(btn_copy)
        erow.addWidget(btn_save)
        root.addLayout(erow)

    # ---------- 数据 ----------
    def _refresh_profiles(self) -> None:
        selected = self.cmb_profile.currentData()
        self.cmb_profile.clear()
        self.cmb_profile.addItem("（不使用风格卡）", None)
        for row in self.pipe.list_profiles():
            d = dict(row)
            self.cmb_profile.addItem(f"{d['name']}  #{d['id']}", d["id"])
        if selected is not None:
            index = self.cmb_profile.findData(selected)
            if index >= 0:
                self.cmb_profile.setCurrentIndex(index)

    def reload_profiles(self) -> None:
        self._refresh_profiles()

    def set_pipeline(self, pipeline: Pipeline) -> None:
        """设置页改动配置后替换 pipeline。"""
        self.pipe = pipeline
        self._refresh_profiles()

    # ---------- 选书 ----------
    def _pick_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "选择电子书", "", FILE_FILTER)
        if not path:
            return
        self._load(path)

    def _load(self, path: str) -> None:
        self.lbl_file.setText(Path(path).name)
        self.lbl_book.setText("正在解析…")
        self.btn_digest.setEnabled(False)
        self.chk_force.setEnabled(False)
        self.btn_gen.setEnabled(False)
        self.digest = None
        self.txt_digest.clear()
        self._parse_w = ParseWorker(self.pipe, path)
        self._parse_w.done.connect(self._on_parsed)
        self._parse_w.failed.connect(self._on_error)
        self._parse_w.start()

    def _on_parsed(self, book: Book) -> None:
        self.book = book
        self.lbl_book.setText(book.summary_line())
        self.btn_digest.setEnabled(True)
        self.chk_force.setEnabled(True)
        cached = self.pipe.get_cached_digest(book)
        if cached and not cached.is_empty():
            self.digest = cached
            self.txt_digest.setPlainText(cached.to_prompt_block())
            self.lbl_digest_state.setText("已命中缓存，可直接生成（不重复消耗 token）")
            self.lbl_digest_state.setObjectName("ok")
            self.btn_gen.setEnabled(True)
        else:
            self.lbl_digest_state.setText("需要先构建理解卡")
            self.lbl_digest_state.setObjectName("muted")
        self.lbl_digest_state.setStyleSheet("")

    # ---------- 理解卡 ----------
    def _build_digest(self, force: bool = False) -> None:
        if not self.book:
            return
        self.bar.setVisible(True)
        self.bar.setValue(0)
        self.btn_digest.setEnabled(False)
        self.chk_force.setEnabled(False)
        self.btn_gen.setEnabled(False)
        self.lbl_digest_state.setText("正在构建理解卡，长篇需要几分钟…")
        self._digest_w = DigestWorker(self.pipe, self.book, force=force)
        self._digest_w.progress.connect(self._on_digest_progress)
        self._digest_w.done.connect(self._on_digest_done)
        self._digest_w.failed.connect(self._on_error)
        self._digest_w.start()

    def _on_digest_progress(self, done: int, total: int, msg: str) -> None:
        self.bar.setMaximum(max(1, total))
        self.bar.setValue(done)
        self.lbl_digest_state.setText(msg or f"正在处理 {done}/{total}")

    def _on_digest_done(self, digest: BookDigest, built: bool) -> None:
        self.bar.setVisible(False)
        self.digest = digest
        self.txt_digest.setPlainText(digest.to_prompt_block())
        self.btn_digest.setEnabled(True)
        self.chk_force.setEnabled(True)
        self.btn_gen.setEnabled(True)
        self.lbl_digest_state.setText("理解卡已就绪" if built else "已命中缓存")
        self.lbl_digest_state.setObjectName("ok")
        self.lbl_digest_state.setStyleSheet("")
        if self.parent() and hasattr(self.parent(), "status"):
            self.parent().status("理解卡构建完成" if built else "命中理解卡缓存")

    # ---------- 生成 ----------
    def _generate(self) -> None:
        if not self.book or not self.digest:
            return
        self.txt_out.clear()
        self.btn_gen.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.lbl_gen_state.setText("生成中…")
        self._gen_w = GenerateWorker(
            self.pipe, self.book, self.digest,
            self.cmb_profile.currentData(),
            self.cmb_length.currentData() or "standard",
            self.cmb_focus.currentData() or "general",
            "",
        )
        self._gen_w.chunk.connect(self._on_chunk)
        self._gen_w.log.connect(self._append_log)
        self._gen_w.done.connect(self._on_gen_done)
        self._gen_w.failed.connect(self._on_error)
        self._gen_w.start()

    def _stop_generate(self) -> None:
        if self._gen_w:
            self._gen_w.request_stop()
        self.btn_stop.setEnabled(False)

    def _on_chunk(self, delta: str) -> None:
        cursor = self.txt_out.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(delta)
        self.txt_out.setTextCursor(cursor)
        self.txt_out.verticalScrollBar().setValue(
            self.txt_out.verticalScrollBar().maximum()
        )
        self.lbl_count.setText(f"{len(self.txt_out.toPlainText())} 字")

    def _append_log(self, message: str) -> None:
        self.txt_log.append(message)
        self.txt_log.verticalScrollBar().setValue(self.txt_log.verticalScrollBar().maximum())

    def _on_gen_done(self, content: str) -> None:
        self.btn_gen.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.lbl_gen_state.setText("")
        self.lbl_count.setText(f"{len(self.txt_out.toPlainText())} 字")
        if not content:
            self._on_error("模型没有返回内容（可能是输出被截断或余额不足）")

    # ---------- 导出 ----------
    def _copy(self) -> None:
        text = self.txt_out.toPlainText()
        if not text:
            return
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(text)

    def _export(self) -> None:
        text = self.txt_out.toPlainText()
        if not text:
            QMessageBox.information(self, "提示", "还没有生成内容")
            return
        name = self.book.title if self.book else "书评"
        name = "".join("_" if c in '<>:/\\|?*\"' else c for c in name).strip(" .") or "书评"
        path, _ = QFileDialog.getSaveFileName(
            self, "导出书评", f"{name}.md", "Markdown (*.md);;文本 (*.txt)"
        )
        if not path:
            return
        Path(path).write_text(text, encoding="utf-8")
        QMessageBox.information(self, "已导出", path)

    # ---------- 错误 ----------
    def _on_error(self, msg: str) -> None:
        self.bar.setVisible(False)
        self.btn_digest.setEnabled(bool(self.book))
        self.chk_force.setEnabled(bool(self.book))
        self.btn_gen.setEnabled(bool(self.digest))
        self.btn_stop.setEnabled(False)
        self.lbl_gen_state.setText("")
        self.lbl_digest_state.setText(msg[:120])
        self.lbl_digest_state.setObjectName("err")
        self.lbl_digest_state.setStyleSheet("")
        self.lbl_digest_state.setToolTip(msg)
        QMessageBox.warning(self, "出错了", msg)

    def dragEnterEvent(self, e):  # noqa: N802
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):  # noqa: N802
        urls = e.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if path:
                self._load(path)
