"""解析器接口与通用工具。"""

from __future__ import annotations

import abc
from pathlib import Path

from ..models import Book, Chapter
from .cleaner import clean_text, split_by_headings

SUPPORTED_EXTS = {".docx", ".epub", ".mobi", ".azw3", ".azw", ".doc"}


class ParseError(RuntimeError):
    pass


class BaseParser(abc.ABC):
    formats: tuple[str, ...] = ()

    @abc.abstractmethod
    def parse(self, path: Path) -> Book:
        ...

    # ---------- 通用工具 ----------
    def build_book(self, path: Path, title: str, author: str, fmt: str,
                   raw_blocks: list[tuple[str, str]], language: str = "") -> Book:
        """raw_blocks: [(章节标题, 正文), ...]，统一清洗并组装成 Book。"""
        # 解析器没给出章节结构时（如 KF7 老 MOBI 解包成单个 HTML），
        # 用正则识别"第X章"等标题做二次切分
        if len(raw_blocks) <= 1 and raw_blocks:
            only = raw_blocks[0][1]
            if len(only) > 500:
                raw_blocks = split_by_headings(only)

        chapters: list[Chapter] = []
        idx = 0
        for heading, body in raw_blocks:
            text = clean_text(body)
            if len(text) < 30:  # 丢弃目录页、版权页等极短块
                continue
            if heading and len(text) < 80:
                # 标题 + 极短正文，多半是目录行，跳过
                continue
            idx += 1
            chapters.append(Chapter(index=idx, title=heading, text=text))
        if not chapters:
            raise ParseError(f"未能从文件中提取到有效正文: {path}")
        book = Book(
            title=title or path.stem,
            author=author,
            fmt=fmt,
            source_path=str(path),
            chapters=chapters,
            language=language,
        )
        book.compute_hash()
        return book

    def fallback_split(self, text: str) -> list[tuple[str, str]]:
        return split_by_headings(text)
