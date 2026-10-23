"""数据模型：解析产物、理解卡、风格画像、书评。"""

from __future__ import annotations

import hashlib
import re
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


# ---------------- 风格画像的类型归一 ----------------
#
# 画像卡是一份「可编辑 JSON」：可能由模型生成、由用户点面板改、也可能被手写编辑。
# 字段类型经常被写成另一种形态：
#   "signature_phrases": "说实话、没想到"      ← 本该是 list[str]
#   "structure": ["开篇", "论证"]              ← 正常
#   "spoiler_policy_by_genre": {...}           ← 本该是 list[dict]
#   "tone": "真诚犀利"                          ← 本该是 dict
# 渲染层若不归一，轻则把字符串逐字符拼成「说、实、话」，重则 AttributeError 直接崩。
# 所有渲染函数都在入口调用它，保证「错乱的画像不会把生成流程带崩」。

_PROFILE_LIST_FIELDS = {
    "review_priorities": 8,
    "structure": 12,
    "signature_phrases": 16,
    "habits": 12,
    "forbidden": 10,
    "spoiler_blur_notes": 10,
}
_PROFILE_DICT_FIELDS = ("persona", "tone", "sentence", "vocabulary", "_stats")
_PROFILE_TEXT_FIELDS = ("genre_focus", "spoiler_policy", "opening_pattern", "ending_pattern")

# 手写时常见的多项分隔符（→ 也常被用来串行文结构）
_ITEM_SPLIT_RE = re.compile(r"[、,，;；/|]|→|->")


def _as_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (list, tuple)):
        return "／".join(t for t in (_as_text(v) for v in value) if t)
    return str(value).strip()


def _as_items(value: object, limit: int) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        parts = _ITEM_SPLIT_RE.split(value)
    elif isinstance(value, (list, tuple, set)):
        parts = [_as_text(v) for v in value]
    else:
        parts = [_as_text(value)]
    return [p for p in (s.strip() for s in parts) if p][:limit]


def normalize_style_profile(profile: object) -> dict:
    """把风格画像归一到渲染层期望的类型；非法输入返回空 dict。

    保留所有未知字段（不改语义），只修正已知字段的容器类型。
    """
    if not isinstance(profile, dict):
        return {}
    p: dict = dict(profile)

    for key, limit in _PROFILE_LIST_FIELDS.items():
        p[key] = _as_items(p.get(key), limit)

    for key in _PROFILE_DICT_FIELDS:
        raw = p.get(key)
        p[key] = dict(raw) if isinstance(raw, dict) else {}

    for key in _PROFILE_TEXT_FIELDS:
        if key in p:
            p[key] = _as_text(p[key])

    persona = p["persona"]
    for key in ("self_name", "identity", "address_reader"):
        if key in persona:
            persona[key] = _as_text(persona[key])

    vocab = p["vocabulary"]
    vocab["preferred_words"] = _as_items(vocab.get("preferred_words"), 12)
    vocab["avoided"] = _as_items(vocab.get("avoided"), 8)

    # 必须是 [{"keywords": [...], "policy": "blur"}, ...]
    rules = p.get("spoiler_policy_by_genre")
    if isinstance(rules, dict):
        rules = [rules]
    elif not isinstance(rules, (list, tuple)):
        rules = []
    clean_rules: list[dict] = []
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        keywords = _as_items(rule.get("keywords"), 20)
        policy = _as_text(rule.get("policy")).lower()
        if keywords and policy:
            clean_rules.append({"keywords": keywords, "policy": policy})
    p["spoiler_policy_by_genre"] = clean_rules
    return p
