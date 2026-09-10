"""分层摘要：块摘要 → 阶段合并 → 全书理解卡。"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

from .chunker import chunk_book
from .config import Settings
from .llm import LLMClient
from .models import Book, BookDigest
from .prompts import (
    CHUNK_SUMMARY_SYSTEM,
    CHUNK_SUMMARY_USER,
    DIGEST_SYSTEM,
    DIGEST_USER,
    MERGE_SUMMARY_SYSTEM,
    MERGE_SUMMARY_USER,
)

ProgressCB = Callable[[int, int, str], None]


class DigestBuilder:
    def __init__(self, llm: LLMClient, settings: Settings):
        self.llm = llm
        self.settings = settings

    def build(self, book: Book, progress: ProgressCB | None = None) -> BookDigest:
        p = self.settings.pipeline
        chunks = chunk_book(book, p.chunk_size, p.chunk_overlap)

        def report(cur: int, total: int, msg: str) -> None:
            if progress:
                progress(cur, total, msg)

        report(0, len(chunks) + 2, f"开始处理，共 {len(chunks)} 块")

        # 短书：直接出理解卡，省 token
        if len(chunks) <= 2:
            material = book.full_text[: p.chunk_size * 2]
            return self._make_digest(book, material, "（全书原文）")

        # 1) 并发生成块摘要
        summaries: list[tuple[int, str]] = []
        total = len(chunks)
        done = 0
        with ThreadPoolExecutor(max_workers=max(1, p.concurrency)) as ex:
            futures = {
                ex.submit(self._summarize_chunk, book.title, c): c.index
                for c in chunks
            }
            for fut in as_completed(futures):
                idx = futures[fut]
                try:
                    summaries.append((idx, fut.result()))
                except Exception as e:
                    summaries.append((idx, f"[第{idx}块摘要失败: {e}]"))
                done += 1
                report(done, total + 2, f"已摘要 {done}/{total} 块")

        summaries.sort(key=lambda x: x[0])

        # 2) 阶段合并：把块摘要按固定字数打包后再压一层
        merged = self._merge_summaries(book.title, summaries)
        report(total + 1, total + 2, "阶段合并完成")

        # 3) 生成全书理解卡
        digest = self._make_digest(book, merged, "（全书分层理解材料）")
        report(total + 2, total + 2, "理解卡生成完成")
        return digest

    # ---------- 各阶段 ----------
    def _summarize_chunk(self, title: str, chunk) -> str:
        user = CHUNK_SUMMARY_USER.format(
            title=title,
            position=f"第 {chunk.index}/{chunk.part_total} 部分" if not chunk.position
            else f"（{chunk.position}）",
            chapter=chunk.position or "未分章",
            text=chunk.text,
        )
        return self.llm.chat(
            CHUNK_SUMMARY_SYSTEM, user,
            temperature=0.3,
            max_tokens=min(1200, max(400, len(chunk.text) // 4)),
        )

    def _merge_summaries(self, title: str, summaries: list[tuple[int, str]]) -> str:
        p = self.settings.pipeline
        groups: list[list[tuple[int, str]]] = []
        cur: list[tuple[int, str]] = []
        size = 0
        for item in summaries:
            cur.append(item)
            size += len(item[1])
            if size >= p.chapter_merge_size:
                groups.append(cur)
                cur, size = [], 0
        if cur:
            groups.append(cur)

        if len(groups) == 1:
            return "\n\n".join(f"[{i}] {s}" for i, s in summaries)

        merged_parts: list[str] = []
        with ThreadPoolExecutor(max_workers=max(1, p.concurrency)) as ex:
            futures = []
            for g in groups:
                body = "\n\n".join(f"[{i}] {s}" for i, s in g)
                futures.append(
                    ex.submit(self._merge_one, title, g[0][0], g[-1][0], body)
                )
            for fut in as_completed(futures):
                merged_parts.append(fut.result())
        return "\n\n".join(merged_parts)

    def _merge_one(self, title: str, start: int, end: int, body: str) -> str:
        user = MERGE_SUMMARY_USER.format(title=title, start=start, end=end, text=body)
        try:
            return self.llm.chat(MERGE_SUMMARY_SYSTEM, user, temperature=0.3, max_tokens=1600)
        except Exception as e:
            return body  # 合并失败就退回原始摘要，不丢信息

    def _make_digest(self, book: Book, material: str, note: str) -> BookDigest:
        author_line = f"（作者：{book.author}）" if book.author else ""
        user = DIGEST_USER.format(
            title=book.title, author_line=author_line, material=material[:60000]
        )
        data = self.llm.chat_json(DIGEST_SYSTEM, user, temperature=0.4, max_tokens=3000)
        digest = BookDigest(
            book_hash=book.file_hash,
            one_line=str(data.get("one_line", "")),
            genre=str(data.get("genre", "")),
            plot_arc=str(data.get("plot_arc", "")),
            characters=str(data.get("characters", "")),
            themes=str(data.get("themes", "")),
            style_notes=str(data.get("style_notes", "")),
            highlights=str(data.get("highlights", "")),
            weaknesses=str(data.get("weaknesses", "")),
            raw=json.dumps(data, ensure_ascii=False),
        )
        if digest.is_empty():
            raise RuntimeError("理解卡生成结果为空，请检查模型输出或重试")
        return digest
