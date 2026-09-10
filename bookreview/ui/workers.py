"""后台工作线程：解析、构建理解卡、流式生成、学习风格。

所有耗时操作都放这里，主线程只负责更新界面，避免界面卡死。
"""

from __future__ import annotations

from typing import Iterator

from PySide6.QtCore import QThread, Signal

from ..core.models import Book, BookDigest


class ParseWorker(QThread):
    """解析电子书。mobi/azw3 走 Calibre 时可能较慢，所以也放后台。"""

    done = Signal(object)          # Book
    failed = Signal(str)

    def __init__(self, pipeline, path: str, parent=None):
        super().__init__(parent)
        self.pipeline = pipeline
        self.path = path

    def run(self) -> None:
        try:
            book = self.pipeline.parse(self.path)
            self.done.emit(book)
        except Exception as e:
            self.failed.emit(f"{type(e).__name__}: {e}")


class DigestWorker(QThread):
    """构建全书理解卡。长篇要跑几十次模型调用，必须后台 + 进度回报。"""

    progress = Signal(int, int, str)   # 已完成 / 总数 / 说明
    done = Signal(object, bool)        # BookDigest / 是否新建
    failed = Signal(str)

    def __init__(self, pipeline, book: Book, force: bool = False, parent=None):
        super().__init__(parent)
        self.pipeline = pipeline
        self.book = book
        self.force = force

    def run(self) -> None:
        try:
            digest, built = self.pipeline.get_or_build_digest(
                self.book, force=self.force,
                progress=lambda d, t, m: self.progress.emit(d, t, m),
            )
            self.done.emit(digest, built)
        except Exception as e:
            self.failed.emit(f"{type(e).__name__}: {e}")


class GenerateWorker(QThread):
    """流式生成书评，边生成边把文字推给界面。"""

    chunk = Signal(str)
    done = Signal(str)             # 全文
    failed = Signal(str)
    log = Signal(str)

    def __init__(self, pipeline, book: Book, digest: BookDigest,
                 profile_id: int | None, length_key: str, focus_key: str,
                 author_name: str = "", parent=None):
        super().__init__(parent)
        self.pipeline = pipeline
        self.book = book
        self.digest = digest
        self.profile_id = profile_id
        self.length_key = length_key
        self.focus_key = focus_key
        self.author_name = author_name
        self._stop = False

    def request_stop(self) -> None:
        self._stop = True

    def run(self) -> None:
        parts: list[str] = []
        self.log.emit("开始生成书评，正在连接模型…")
        try:
            stream: Iterator[str] = self.pipeline.stream_review(
                self.book, self.digest, self.profile_id,
                self.length_key, self.focus_key, self.author_name,
            )
            for delta in stream:
                if self._stop:
                    break
                parts.append(delta)
                self.chunk.emit(delta)
                self.log.emit(f"已接收模型输出 {sum(map(len, parts))} 字")
        except Exception as e:
            self.failed.emit(f"{type(e).__name__}: {e}")
            return

        content = "".join(parts).strip()
        self.log.emit(f"书评生成完成，共 {len(content)} 字")
        if content:
            try:
                self.pipeline.db.save_review(
                    self.book.file_hash, self.book.title, self.profile_id,
                    self.length_key, self.focus_key, content,
                )
            except Exception:
                pass  # 入库失败不影响用户看到内容
        self.done.emit(content)


class StyleLearnWorker(QThread):
    """从书评样本学习风格。"""

    done = Signal(int, object)     # profile_id / profile
    failed = Signal(str)

    def __init__(self, pipeline, paths: list[str], name: str, hint: str = "",
                 parent=None):
        super().__init__(parent)
        self.pipeline = pipeline
        self.paths = paths
        self.name = name
        self.hint = hint

    def run(self) -> None:
        try:
            pid, profile = self.pipeline.learn_style(
                self.paths, name=self.name, hint=self.hint
            )
            self.done.emit(pid, profile)
        except Exception as e:
            self.failed.emit(f"{type(e).__name__}: {e}")


class PingWorker(QThread):
    """测试模型连通性。"""

    done = Signal(bool, str)

    def __init__(self, pipeline, parent=None):
        super().__init__(parent)
        self.pipeline = pipeline

    def run(self) -> None:
        try:
            ok, msg = self.pipeline.llm.ping()
            self.done.emit(ok, msg)
        except Exception as e:
            self.done.emit(False, f"{type(e).__name__}: {e}")
