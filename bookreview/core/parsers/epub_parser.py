"""EPUB 解析：按 spine 阅读顺序提取正文文档。"""

from __future__ import annotations

import re
from pathlib import Path

import ebooklib
from bs4 import BeautifulSoup
from ebooklib import epub

from .base import BaseParser
from ..models import Book

# 明显不是正文的文档。
# 判定按「文件名主干的分词」精确比对：用子串匹配会把 discover.xhtml（含 cover）、
# canvas.xhtml（含 nav）误判成封面/目录页，静默丢掉真章节。
SKIP_STEMS = frozenset({
    "nav", "toc", "ncx", "cover", "titlepage", "title-page", "title_page",
    "copyright", "colophon", "frontmatter", "front-matter", "front_matter",
})
_DOC_SUFFIXES = (".xhtml", ".html", ".htm", ".xml")
_WORD_RE = re.compile(r"[a-z]+")


def _is_boilerplate(file_name: str | None) -> bool:
    """封面 / 目录 / 版权页判定。"""
    name = (file_name or "").lower().replace("\\", "/")
    stem = name.rsplit("/", 1)[-1]
    for suffix in _DOC_SUFFIXES:
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
            break
    if stem in SKIP_STEMS:
        return True
    return any(word in SKIP_STEMS for word in _WORD_RE.findall(stem))


def _reading_order(book) -> list:
    """按 spine（阅读顺序）返回正文文档。

    manifest 顺序只是「文件在包里的排列」，不等于翻页顺序；按 manifest 抽取
    会让章节错乱。spine 缺失或结构异常时退回 manifest，保证不丢正文。
    """
    ordered: list = []
    seen: set = set()
    try:
        for entry in book.spine or []:
            # read_epub 给出的是 (idref, linear)，手写时也可能只给 idref
            idref = entry[0] if isinstance(entry, (tuple, list)) else entry
            item = book.get_item_with_id(str(idref))
            if item is None or item.get_type() != ebooklib.ITEM_DOCUMENT:
                continue
            if item.id in seen:
                continue
            ordered.append(item)
            seen.add(item.id)
    except Exception:
        # spine 结构不合预期：整体退回 manifest 顺序
        ordered, seen = [], set()

    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        if item.id not in seen:
            ordered.append(item)
            seen.add(item.id)
    return ordered


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
        for item in _reading_order(book):
            if _is_boilerplate(item.file_name):
                continue
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
