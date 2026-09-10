"""数据模型：解析产物、理解卡、风格画像、书评。"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field


@dataclass
class Chapter:
    index: int
    title: str
    text: str

    @property
    def char_count(self) -> int:
        return len(self.text)


@dataclass
class Book:
    """解析器的统一输出。"""

    title: str
    author: str
    fmt: str                       # docx / epub / mobi / azw3
    source_path: str
    chapters: list[Chapter] = field(default_factory=list)
    language: str = ""
    file_hash: str = ""

    @property
    def full_text(self) -> str:
        return "\n\n".join(c.text for c in self.chapters)

    @property
    def total_chars(self) -> int:
        return sum(c.char_count for c in self.chapters)

    @property
    def chapter_count(self) -> int:
        return len(self.chapters)

    def compute_hash(self) -> str:
        h = hashlib.sha256()
        h.update(self.full_text.encode("utf-8", errors="ignore"))
        self.file_hash = h.hexdigest()[:32]
        return self.file_hash

    def summary_line(self) -> str:
        return (
            f"《{self.title}》 {self.author or '佚名'} | {self.fmt.upper()} | "
            f"{self.chapter_count} 章 | {self.total_chars:,} 字"
        )


@dataclass
class BookDigest:
    """全书理解卡：分级压缩后的产物，供书评生成消费。"""

    book_hash: str
    one_line: str = ""             # 一句话定位
    genre: str = ""                # 类型
    plot_arc: str = ""             # 情节主线
    characters: str = ""           # 主要人物与弧光
    themes: str = ""               # 主题与母题
    style_notes: str = ""          # 文笔与叙事手法
    highlights: str = ""           # 高光段落/场景
    weaknesses: str = ""           # 明显短板
    raw: str = ""                  # 完整 JSON 原文

    def __post_init__(self) -> None:
        # 模型有时把本该是字符串的字段返回成数组，统一收敛成文本
        for f in ("one_line", "genre", "plot_arc", "characters",
                  "themes", "style_notes", "highlights", "weaknesses"):
            v = getattr(self, f)
            if isinstance(v, (list, tuple)):
                setattr(self, f, "\n".join(f"・{x}" for x in v if str(x).strip()))
            elif v is None:
                setattr(self, f, "")

    def to_prompt_block(self) -> str:
        """转成给模型看的紧凑文本块。"""
        parts = [
            f"【一句话定位】{self.one_line}",
            f"【类型】{self.genre}",
            f"【情节主线】{self.plot_arc}",
            f"【主要人物】\n{self.characters}" if "\n" in self.characters else f"【主要人物】{self.characters}",
            f"【主题与母题】{self.themes}",
            f"【文笔与叙事】{self.style_notes}",
            f"【高光之处】{self.highlights}",
            f"【明显短板】{self.weaknesses}",
        ]
        return "\n".join(p for p in parts if not p.endswith("】"))

    def is_empty(self) -> bool:
        return not (self.plot_arc or self.one_line)
