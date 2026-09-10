"""全流程编排：解析 → 理解卡 → 风格卡 → 书评。GUI 与 CLI 共用。"""

from __future__ import annotations

import json
import hashlib
from pathlib import Path
from typing import Callable

from .config import Settings, load_settings
from .db import DB
from .digest import DigestBuilder
from .generator import ReviewGenerator
from .llm import LLMClient
from .logging_utils import configure_logging
from .models import Book, BookDigest
from .parsers.factory import parse_book
from .style import StyleAnalyzer, load_samples_from_paths

ProgressCB = Callable[[int, int, str], None]
DIGEST_CACHE_VERSION = 2


class Pipeline:
    def __init__(self, settings: Settings | None = None, db: DB | None = None):
        self.settings = settings or load_settings()
        self.db = db or DB(self.settings.resolve_data_dir())
        self.logger = configure_logging(self.settings.resolve_data_dir() / "logs")
        self._llm: LLMClient | None = None
        self._digest_builder: DigestBuilder | None = None
        self._generator: ReviewGenerator | None = None
        self._style_analyzer: StyleAnalyzer | None = None

    # ---------- 惰性组件 ----------
    @property
    def llm(self) -> LLMClient:
        if self._llm is None:
            self._llm = LLMClient(self.settings)
        return self._llm

    @property
    def digests(self) -> DigestBuilder:
        if self._digest_builder is None:
            self._digest_builder = DigestBuilder(self.llm, self.settings)
        return self._digest_builder

    @property
    def generator(self) -> ReviewGenerator:
        if self._generator is None:
            self._generator = ReviewGenerator(self.llm, self.settings)
        return self._generator

    @property
    def styles(self) -> StyleAnalyzer:
        if self._style_analyzer is None:
            self._style_analyzer = StyleAnalyzer(self.llm)
        return self._style_analyzer

    # ---------- 步骤 ----------
    def parse(self, path: str | Path) -> Book:
        self.logger.info("开始解析电子书: %s", path)
        book = parse_book(path)
        self.db.upsert_book(book)
        self.logger.info("解析完成: %s, %d章, %d字", book.title, book.chapter_count, book.total_chars)
        return book

    def get_cached_digest(self, book: Book) -> BookDigest | None:
        data = self.db.get_digest(book.file_hash)
        if not data:
            return None
        if data.get("cache_version") != DIGEST_CACHE_VERSION:
            return None
        if data.get("cache_fingerprint") != self._digest_fingerprint():
            return None
        data.setdefault("book_hash", book.file_hash)
        fields = set(BookDigest.__dataclass_fields__)
        try:
            return BookDigest(**{k: v for k, v in data.items() if k in fields})
        except TypeError:
            return None

    def build_digest(self, book: Book, progress: ProgressCB | None = None) -> BookDigest:
        self.logger.info("开始构建理解卡: %s", book.title)
        digest = self.digests.build(book, progress)
        self.db.save_digest(book.file_hash, {
            "book_hash": digest.book_hash,
            "one_line": digest.one_line,
            "genre": digest.genre,
            "plot_arc": digest.plot_arc,
            "characters": digest.characters,
            "themes": digest.themes,
            "style_notes": digest.style_notes,
            "highlights": digest.highlights,
            "weaknesses": digest.weaknesses,
            "raw": digest.raw,
            "cache_version": DIGEST_CACHE_VERSION,
            "cache_fingerprint": self._digest_fingerprint(),
        })
        self.logger.info("理解卡构建完成: %s", book.title)
        return digest

    def _digest_fingerprint(self) -> str:
        payload = {"version": DIGEST_CACHE_VERSION, "model": self.settings.llm.model,
                   "chunk_size": self.settings.pipeline.chunk_size,
                   "chunk_overlap": self.settings.pipeline.chunk_overlap,
                   "merge_size": self.settings.pipeline.chapter_merge_size}
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]

    def get_or_build_digest(self, book: Book, force: bool = False,
                            progress: ProgressCB | None = None) -> tuple[BookDigest, bool]:
        """返回 (理解卡, 是否新建)。命中缓存时 from_cache=False。"""
        if not force:
            cached = self.get_cached_digest(book)
            if cached and not cached.is_empty():
                return cached, False
        self.db.clear_digest(book.file_hash)
        return self.build_digest(book, progress), True

    # ---------- 风格 ----------
    def learn_style(self, sample_paths: list[str | Path], name: str = "我的风格",
                    hint: str = "", profile_id: int | None = None) -> tuple[int, dict]:
        samples = load_samples_from_paths(sample_paths)
        if not samples:
            raise ValueError("没有读到任何有效书评样本（每篇至少 50 字）")
        profile = self.styles.analyze(samples, hint)
        if profile_id is None:
            existing = self.db.find_profile_by_name(name.strip())
            if existing:
                profile_id = int(existing["id"])
        pid = self.db.save_profile(name, profile, len(samples), profile_id)
        return pid, profile

    def list_profiles(self):
        return self.db.list_profiles()

    def get_profile(self, profile_id: int) -> dict | None:
        return self.db.get_profile(profile_id)

    # ---------- 生成 ----------
    def generate_review(self, book: Book, digest: BookDigest, profile_id: int | None = None,
                        length_key: str = "standard", focus_key: str = "general",
                        author_name: str = "你") -> str:
        profile = self.get_profile(profile_id) if profile_id else None
        content = self.generator.generate(
            book, digest, profile, length_key, focus_key, author_name
        )
        self.db.save_review(book.file_hash, book.title, profile_id, length_key,
                            focus_key, content)
        return content

    def stream_review(self, book: Book, digest: BookDigest, profile_id: int | None = None,
                      length_key: str = "standard", focus_key: str = "general",
                      author_name: str = "你"):
        profile = self.get_profile(profile_id) if profile_id else None
        return self.generator.stream(
            book, digest, profile, length_key, focus_key, author_name
        )

    def close(self) -> None:
        self.db.close()
