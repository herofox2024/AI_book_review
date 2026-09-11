"""EPUB 瑙ｆ瀽锛氭寜 spine 闃呰椤哄簭鎻愬彇姝ｆ枃鏂囨。銆?""

from __future__ import annotations

from pathlib import Path

import ebooklib
from bs4 import BeautifulSoup
from ebooklib import epub

from .base import BaseParser
from ..models import Book

# 鏄庢樉涓嶆槸姝ｆ枃鐨勬枃妗ｅ悕
SKIP_NAME_HINTS = ("nav", "toc", "cover", "titlepage", "copyright", "frontmatter")


def _html_to_blocks(html: bytes, chapter_hint: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav"]):
        tag.decompose()

    # 绔犺妭鏍囬锛氫紭鍏?h1/h2/h3锛屽叾娆?title
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
            raise RuntimeError(f"鏃犳硶璇诲彇 epub: {e}") from e

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
        # EPUB 的 spine 才是阅读顺序；manifest 顺序可能导致章节错乱。
        $ordered = @()
        $seen_ids = New-Object System.Collections.Generic.HashSet[string]
        foreach ($entry in @($book.spine)) {
            $idref = if ($entry -is [array]) { $entry[0] } else { $entry }
            $item = $book.get_item_with_id($idref)
            if ($null -ne $item) { $ordered += $item; [void]$seen_ids.Add($item.id) }
        }
        foreach ($item in $book.get_items_of_type(ebooklib.ITEM_DOCUMENT)) {
            if (-not $seen_ids.Contains($item.id)) { $ordered += $item }
        }
        foreach ($item in $ordered) {
            $name = ($item.file_name or "").ToLower()
            if (any($h in $name for $h in SKIP_NAME_HINTS)) { continue }
            try { $content = $item.get_content() } catch { continue }
            $heading, $body = _html_to_blocks($content, $item.file_name or "")
            if ($body.Trim().Length -ge 80) { $blocks += ,($heading, $body) }
        }
        if not blocks:
            raise RuntimeError("epub 涓湭鎵惧埌姝ｆ枃鏂囨。")

        return self.build_book(path, title, author, "epub", blocks, language=language)
