"""解析器工厂：按扩展名分发。"""

from __future__ import annotations

from pathlib import Path

from .base import SUPPORTED_EXTS, BaseParser, ParseError
from .docx_parser import DocxParser
from .epub_parser import EpubParser
from .mobi_parser import MobiParser

_REGISTRY: list[BaseParser] = [DocxParser(), EpubParser(), MobiParser()]


def get_parser(path: str | Path) -> BaseParser:
    p = Path(path)
    ext = p.suffix.lower()
    if ext not in SUPPORTED_EXTS:
        raise ParseError(
            f"不支持的格式: {ext or '(无扩展名)'}。"
            f"当前支持: {', '.join(sorted(SUPPORTED_EXTS))}"
        )
    if ext == ".doc":
        raise ParseError("旧版 .doc 无法直接解析，请用 Word 另存为 .docx，或用 Calibre 转换。")
    for parser in _REGISTRY:
        if ext in parser.formats:
            return parser
    raise ParseError(f"没有可用的解析器: {ext}")


def parse_book(path: str | Path):
    """解析电子书，返回 Book 对象。"""
    p = Path(path)
    if not p.exists():
        raise ParseError(f"文件不存在: {p}")
    return get_parser(p).parse(p)
