"""EPUB 解析：按 spine 阅读顺序提取正文文档。"""

from __future__ import annotations

from pathlib import Path

import ebooklib
from bs4 import BeautifulSoup
from ebooklib import epub

from .base import BaseParser
from ..models import Book

# 明显不是正文的文档名
SKIP_NAME_HINTS = ("nav", "toc", "cover", "titlepage", "copyright", "frontmatter")


def _html_to_blocks(html: bytes, chapter_hint: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav"]):
        tag.decompose()

    # 章节标题：优先 h1/h2/h3，其次 title
    heading = chapter_hint
    for tag_name in ("h1", "h2", "h3"):
        h = soup.find(tag_name)
        if h and h.get_text(strip=True):
            candidate = h.get_text(strip=True)
            if len(candidate) <= 60:
                heading = candidate
                break

    body = soup.get_text("\n")
    return heading, body


class EpubParser(BaseParser):
    formats = (".epub",)

    def parse(self, path: Path) -> Book:
        try:
            book = epub.read_epub(str(path))
        except Exception as e:
            raise RuntimeError(f"无法读取 epub: {e}") from e

        def first_meta(ns: str, tag: str) -> str:
            try:
                items = book.get_metadata(ns, tag)
                if items:
                    return str(items[0][0]).strip()
            except Exception:
                pass
            return ""

        title = first_meta("DC", "title")
        author = first_meta("DC", "creator")
        language = first_meta("DC", "language")

        blocks: list[tuple[str, str]] = []
        for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
            name = (item.file_name or "").lower()
            if any(h in name for h in SKIP_NAME_HINTS):
                continue
                # 封面/目录页通常无正文，但仍尝试提取，短块会被 build_book 丢弃
                pass
            try:
                content = item.get_content()
            except Exception:
                continue
            heading, body = _html_to_blocks(content, item.file_name or "")
            if len(body.strip()) >= 80:
                blocks.append((heading, body))

        if not blocks:
            raise RuntimeError("epub 中未找到正文文档")

        return self.build_book(path, title, author, "epub", blocks, language=language)
