"""书评库：已生成的书评列表、预览、编辑与导出。"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QFileDialog, QFrame, QHBoxLayout, QLabel, QMessageBox,
    QPushButton, QSplitter, QTableWidget, QTableWidgetItem, QTextEdit,
    QVBoxLayout, QWidget,
)
from ...core.pipeline import Pipeline

LENGTH_LABEL = {"short": "短评", "standard": "标准", "deep": "深度长评"}
FOCUS_LABEL = {
    "general": "综合", "plot": "情节", "character": "人物",
    "prose": "文笔", "theme": "主题",
}


class LibraryPage(QWidget):
    def __init__(self, pipeline: Pipeline, parent=None):
        super().__init__(parent)
        self.pipe = pipeline
        self._rows: list[dict] = []
        self._edited = False
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(12)

        head = QHBoxLayout()
        t = QLabel("书评库")
        t.setObjectName("title")
        head.addWidget(t)
        head.addStretch(1)
        btn_reload = QPushButton("刷新")
        btn_reload.clicked.connect(self.reload)
        self.btn_save = QPushButton("保存修改")
        self.btn_save.setObjectName("primary")
        self.btn_save.setEnabled(False)
        self.btn_save.clicked.connect(self._save)
        btn_del = QPushButton("删除")
        btn_del.setObjectName("danger")
        btn_del.clicked.connect(self._delete)
        head.addWidget(btn_reload)
        head.addWidget(self.btn_save)
        head.addWidget(btn_del)
        root.addLayout(head)

        card = QFrame()
        card.setObjectName("card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(10, 10, 10, 10)

        split = QSplitter(Qt.Horizontal)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["书名", "风格", "规格", "字数", "时间"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 220)
        self.table.setColumnWidth(1, 120)
        self.table.setColumnWidth(2, 110)
        self.table.setColumnWidth(3, 70)
        self.table.itemSelectionChanged.connect(self._on_select)
        split.addWidget(self.table)

        right = QWidget()
        rlay = QVBoxLayout(right)
        rlay.setContentsMargins(8, 0, 0, 0)
        rlay.setSpacing(8)
        self.lbl_meta = QLabel("")
        self.lbl_meta.setObjectName("sub")
        self.lbl_meta.setWordWrap(True)
        rlay.addWidget(self.lbl_meta)

        self.txt = QTextEdit()
        self.txt.setPlaceholderText("从左侧选择一篇书评")
        self.txt.textChanged.connect(self._on_edit)
        rlay.addWidget(self.txt, 1)

        erow = QHBoxLayout()
        btn_exp = QPushButton("导出…")
        btn_exp.clicked.connect(self._export)
        btn_copy = QPushButton("复制")
        btn_copy.clicked.connect(self._copy)
        erow.addStretch(1)
        erow.addWidget(btn_copy)
        erow.addWidget(btn_exp)
        rlay.addLayout(erow)
        split.addWidget(right)
        split.setStretchFactor(0, 2)
        split.setStretchFactor(1, 3)

        lay.addWidget(split)
        root.addWidget(card, 1)

        self.reload()

    # ---------- 数据 ----------
    def set_pipeline(self, pipeline: Pipeline) -> None:
        self.pipe = pipeline
        self.reload()

    def reload(self) -> None:
        rows = [dict(r) for r in self.pipe.db.list_reviews()]
        rows.sort(key=lambda r: r.get("created_at") or 0, reverse=True)
        self._rows = rows
        self.table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            ts = r.get("created_at") or 0
            when = datetime.fromtimestamp(ts).strftime("%m-%d %H:%M") if ts else ""
            prof = ""
            pid = r.get("profile_id")
            if pid:
                p = self.pipe.get_profile(pid)
                prof = (p or {}).get("name", f"#{pid}") if isinstance(p, dict) else f"#{pid}"
            spec = f"{LENGTH_LABEL.get(r.get('length_key'), r.get('length_key'))}"
            foc = FOCUS_LABEL.get(r.get("focus_key"), "")
            if foc and foc != "综合":
                spec += f"·{foc}"
            content = r.get("content") or ""
            for c, v in enumerate([r.get("book_title") or "（无标题）", prof,
                                   spec, f"{len(content)}", when]):
                item = QTableWidgetItem(str(v))
                item.setData(Qt.UserRole, r.get("id"))
                self.table.setItem(i, c, item)
        if rows and self.table.currentRow() < 0:
            self.table.selectRow(0)

    def _current(self) -> dict | None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self._rows):
            return None
        return self._rows[row]

    def _on_select(self) -> None:
        self._edited = False
        self.btn_save.setEnabled(False)
        r = self._current()
        if not r:
            return
        self.txt.blockSignals(True)
        self.txt.setPlainText(r.get("content") or "")
        self.txt.blockSignals(False)
        prof = ""
        pid = r.get("profile_id")
        if pid:
            p = self.pipe.get_profile(pid)
            prof = (p or {}).get("name", "") if isinstance(p, dict) else ""
        self.lbl_meta.setText(
            f"《{r.get('book_title')}》　风格：{prof or '未使用'}　"
            f"规格：{LENGTH_LABEL.get(r.get('length_key'), '')}　"
            f"字数：{len(r.get('content') or '')}"
        )

    def _on_edit(self) -> None:
        self._edited = True
        self.btn_save.setEnabled(True)

    # ---------- 操作 ----------
    def _save(self) -> None:
        r = self._current()
        if not r:
            return
        conn = self.pipe.db.conn
        conn.execute(
            "UPDATE reviews SET content=? WHERE id=?",
            (self.txt.toPlainText(), r["id"]),
        )
        conn.commit()
        r["content"] = self.txt.toPlainText()
        self._edited = False
        self.btn_save.setEnabled(False)
        QMessageBox.information(self, "已保存", "修改已写回书评库")

    def _delete(self) -> None:
        r = self._current()
        if not r:
            return
        if QMessageBox.question(
            self, "确认删除", f"删除《{r.get('book_title')}》的这篇书评？此操作不可撤销。"
        ) != QMessageBox.Yes:
            return
        self.pipe.db.conn.execute("DELETE FROM reviews WHERE id=?", (r["id"],))
        self.pipe.db.conn.commit()
        self.reload()

    def _copy(self) -> None:
        from PySide6.QtWidgets import QApplication
        text = self.txt.toPlainText()
        if text:
            QApplication.clipboard().setText(text)

    def _export(self) -> None:
        r = self._current()
        if not r:
            return
        name = (r.get("book_title") or "书评").replace("/", "_")
        path, _ = QFileDialog.getSaveFileName(
            self, "导出书评", f"{name}.md", "Markdown (*.md);;文本 (*.txt)"
        )
        if not path:
            return
        Path(path).write_text(self.txt.toPlainText(), encoding="utf-8")
        QMessageBox.information(self, "已导出", path)
