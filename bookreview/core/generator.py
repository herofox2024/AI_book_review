"""书评生成：理解卡 + 风格卡 + 长度/侧重 → 书评正文。"""

from __future__ import annotations

from typing import Iterator

from .config import Settings
from .llm import LLMClient
from .models import Book, BookDigest
from .prompts import (
    LENGTH_PRESETS,
    REVIEW_SYSTEM,
    REVIEW_USER,
    render_focus_desc,
    render_length_desc,
    render_persona_line,
    render_spoiler_rule,
    render_structure_desc,
    render_style_block,
)


class ReviewGenerator:
    def __init__(self, llm: LLMClient, settings: Settings):
        self.llm = llm
        self.settings = settings

    def build_messages(self, book: Book, digest: BookDigest, profile: dict | None,
                       length_key: str, focus_key: str, author_name: str = "",
                       structure_custom: str | None = None) -> tuple[str, str]:
        length_key = length_key if length_key in LENGTH_PRESETS else "standard"
        system = REVIEW_SYSTEM.format(
            persona_line=render_persona_line(profile, author_name),
            title=book.title,
            style_block=render_style_block(profile),
            spoiler_rule=render_spoiler_rule(profile, digest.genre),
        )
        meta = f"《{book.title}》"
        if book.author:
            meta += f"，{book.author}"
        if digest.genre:
            meta += f"，{digest.genre}"
        user = REVIEW_USER.format(
            digest_block=f"{meta}\n{digest.to_prompt_block()}",
            length_desc=render_length_desc(length_key),
            focus_desc=render_focus_desc(focus_key),
            structure_desc=render_structure_desc(length_key, structure_custom),
        )
        return system, user

    def _review_model(self) -> str | None:
        """生成书评使用的模型：优先 llm.review_model，留空则复用默认模型。"""
        return self.settings.llm.review_model or None

    def generate(self, book: Book, digest: BookDigest, profile: dict | None = None,
                 length_key: str = "standard", focus_key: str = "general",
                 author_name: str = "", structure_custom: str | None = None,
                 temperature: float | None = None) -> str:
        system, user = self.build_messages(
            book, digest, profile, length_key, focus_key, author_name, structure_custom
        )
        max_tokens = LENGTH_PRESETS.get(length_key, LENGTH_PRESETS["standard"])["max_tokens"]
        return self.llm.chat(
            system, user,
            temperature=temperature if temperature is not None else 0.85,
            max_tokens=max_tokens,
            model=self._review_model(),
        )

    def stream(self, book: Book, digest: BookDigest, profile: dict | None = None,
               length_key: str = "standard", focus_key: str = "general",
               author_name: str = "", structure_custom: str | None = None,
               temperature: float | None = None) -> Iterator[str]:
        system, user = self.build_messages(
            book, digest, profile, length_key, focus_key, author_name, structure_custom
        )
        max_tokens = LENGTH_PRESETS.get(length_key, LENGTH_PRESETS["standard"])["max_tokens"]
        yield from self.llm.stream(
            system, user,
            temperature=temperature if temperature is not None else 0.85,
            max_tokens=max_tokens,
            model=self._review_model(),
        )
