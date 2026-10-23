"""书评库：已生成的书评列表、预览、编辑与导出。

版式与设置页保持一致：标题行 + 分组卡片；左侧列表、右侧编辑器都在卡片里。
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QFileDialog, QFrame, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QMessageBox, QPushButton, QSplitter, QTableWidget,
    QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget,
)
from ...core.pipeline import Pipeline

LENGTH_LABEL = {"short": "短评", "standard": "标准", "deep": "深度长评"}
FOCUS_LABEL = {
    "general": "综合", "plot": "情节", "character": "人物",
    "prose": "文笔", "theme": "主题",
}
COLUMNS = ["书名", "风格", "规格", "字数", "时间"]


class LibraryPage(QWidget):
    def __init__(self, pipeline: Pipeline, parent=None):
        super().__init__(parent)
        self.pipe = pipeline
        self._rows: list[dict] = []
        self._edited = False
        self._query = ""
        self._build_ui()

    # ---------- 界面 ----------
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(12)

        # --- 标题行 ---
        head = QHBoxLayout()
        head.setSpacing(8)
        t = QLabel("书评库")
        t.setObjectName("title")
        head.addWidget(t)
        self.lbl_badge = QLabel("0")
        self.lbl_badge.setObjectName("badge")
        head.addWidget(self.lbl_badge)
        head.addStretch(1)

        self.ed_search = QLineEdit()
        self.ed_search.setPlaceholderText("搜索书名或风格…")
        self.ed_search.setClearButtonEnabled(True)
        self.ed_search.setFixedWidth(220)
        self.ed_search.textChanged.connect(self._on_search)
        head.addWidget(self.ed_search)

        btn_reload = QPushButton("刷新")
        btn_reload.clicked.connect(self.reload)
        head.addWidget(btn_reload)
        root.addLayout(head)

        # --- 主体：左列表 / 右编辑器 ---
        split = QSplitter(Qt.Horizontal)
        split.setHandleWidth(12)
        split.setChildrenCollapsible(False)

        left = QFrame()
        left.setObjectName("card")
        llay = QVBoxLayout(left)
        llay.setContentsMargins(6, 6, 6, 6)

        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(False)
        self.table.verticalHeader().setDefaultSectionSize(34)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        for col, width in ((1, 120), (2, 96), (3, 64), (4, 96)):
            header.setSectionResizeMode(col, QHeaderView.Fixed)
            self.table.setColumnWidth(col, width)
        header.setHighlightSections(False)
        self.table.itemSelectionChanged.connect(self._on_select)
        llay.addWidget(self.table)
        split.addWidget(left)

        right = QFrame()
        right.setObjectName("card")
        rlay = QVBoxLayout(right)
        rlay.setContentsMargins(16, 12, 16, 12)
        rlay.setSpacing(10)

        meta_row = QHBoxLayout()
        self.lbl_meta = QLabel("从左侧选择一篇书评")
        self.lbl_meta.setObjectName("sub")
        self.lbl_meta.setWordWrap(True)
        meta_row.addWidget(self.lbl_meta, 1)
        self.lbl_dirty = QLabel("")
        self.lbl_dirty.setObjectName("warn")
        meta_row.addWidget(self.lbl_dirty)
        rlay.addLayout(meta_row)

        self.txt = QTextEdit()
        self.txt.setObjectName("output")
        self.txt.setPlaceholderText("从左侧选择一篇书评，即可在这里预览和编辑。")
        self.txt.textChanged.connect(self._on_edit)
        rlay.addWidget(self.txt, 1)

        erow = QHBoxLayout()
        erow.setSpacing(8)
        self.btn_save = QPushButton("保存修改")
        self.btn_save.setObjectName("primary")
        self.btn_save.setEnabled(False)
        self.btn_save.clicked.connect(self._save)
        btn_del = QPushButton("删除")
        btn_del.setObjectName("danger")
        btn_del.clicked.connect(self._delete)
        btn_copy = QPushButton("复制")
        btn_copy.clicked.connect(self._copy)
        btn_exp = QPushButton("导出…")
        btn_exp.clicked.connect(self._export)
        erow.addWidget(btn_del)
        erow.addStretch(1)
        erow.addWidget(btn_copy)
        erow.addWidget(btn_exp)
        erow.addWidget(self.btn_save)
        rlay.addLayout(erow)
        split.addWidget(right)

        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 4)
        root.addWidget(split, 1)

        self.reload()

    # ---------- 数据 ----------
    def set_pipeline(self, pipeline: Pipeline) -> None:
        self.pipe = pipeline
        self.reload()

    def reload(self) -> None:
        rows = [dict(r) for r in self.pipe.db.list_reviews()]
        rows.sort(key=lambda r: r.get("created_at") or 0, reverse=True)
        self._rows = rows
        self.lbl_badge.setText(str(len(rows)))
        self._fill_table()

    def _fill_table(self) -> None:
        """按当前搜索词填充表格。"""
        query = self._query.strip().lower()
        visible: list[dict] = []
        for r in self._rows:
            prof = self._profile_name(r.get("profile_id"))
            if query and query not in (r.get("book_title") or "").lower() \
                    and query not in prof.lower():
                continue
            visible.append({**r, "_profile_name": prof})

        self.table.blockSignals(True)
        self.table.setRowCount(len(visible))
        for i, r in enumerate(visible):
            ts = r.get("created_at") or 0
            when = datetime.fromtimestamp(ts).strftime("%m-%d %H:%M") if ts else ""
            spec = f"{LENGTH_LABEL.get(r.get('length_key'), r.get('length_key'))}"
            foc = FOCUS_LABEL.get(r.get("focus_key"), "")
            if foc and foc != "综合":
                spec += f"·{foc}"
            values = [
                r.get("book_title") or "（无标题）",
                r["_profile_name"] or "未使用",
                spec,
                f"{len(r.get('content') or '')}",
                when,
            ]
            for c, v in enumerate(values):
                item = QTableWidgetItem(str(v))
                item.setData(Qt.UserRole, r.get("id"))
                if c == 3:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(i, c, item)
        self.table.blockSignals(False)

        self._visible = visible
        if visible:
            self.table.selectRow(0)
        else:
            self._on_select()

    def _profile_name(self, pid) -> str:
        if not pid:
            return ""
        p = self.pipe.get_profile(pid)
        if isinstance(p, dict):
            return p.get("name", "") or f"#{pid}"
        return f"#{pid}"

    def _current(self) -> dict | None:
        row = self.table.currentRow()
        if row < 0 or row >= len(getattr(self, "_visible", [])):
            return None
        return self._visible[row]

    def _on_search(self, text: str) -> None:
        self._query = text
        self._fill_table()

    def _on_select(self) -> None:
        self._edited = False
        self.btn_save.setEnabled(False)
        self.lbl_dirty.setText("")
        r = self._current()
        if not r:
            self.lbl_meta.setText(
                "还没有书评" if not self._rows else "没有匹配的书评"
            )
            self.txt.blockSignals(True)
            self.txt.clear()
            self.txt.blockSignals(False)
            return
        self.txt.blockSignals(True)
        self.txt.setPlainText(r.get("content") or "")
        self.txt.blockSignals(False)
        prof = r.get("_profile_name") or ""
        self.lbl_meta.setText(
            f"《{r.get('book_title')}》　风格：{prof or '未使用'}　"
            f"规格：{LENGTH_LABEL.get(r.get('length_key'), '')}　"
            f"字数：{len(r.get('content') or '')}"
        )

    def _on_edit(self) -> None:
        if self._current() is None:
            return
        self._edited = True
        self.btn_save.setEnabled(True)
        self.lbl_dirty.setText("未保存")

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
        self.lbl_dirty.setText("")
        # 字数列需要跟着更新，但不能把用户从当前行挤走
        row = self.table.currentRow()
        if row >= 0 and self.table.item(row, 3) is not None:
            self.table.item(row, 3).setText(f"{len(r['content'])}")
        self.lbl_meta.setText(
            f"《{r.get('book_title')}》　风格：{r.get('_profile_name') or '未使用'}　"
            f"规格：{LENGTH_LABEL.get(r.get('length_key'), '')}　"
            f"字数：{len(r['content'])}"
        )
        self._status("修改已保存")

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
            self._status("已复制到剪贴板")

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

    def _status(self, msg: str) -> None:
        win = self.window()
        if hasattr(win, "status"):
            win.status(msg)
