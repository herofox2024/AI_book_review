"""智能分块：按章节累积，接近阈值时在段落边界切分，保留重叠避免切断情节。"""

from __future__ import annotations

from dataclasses import dataclass

from .models import Book


@dataclass
class Chunk:
    index: int
    chapter: str          # 所属章节标题
    position: str         # 给模型看的位置描述，如"第 12-15 章"
    text: str
    part: int = 1
    part_total: int = 1

    @property
    def char_count(self) -> int:
        return len(self.text)


def chunk_book(book: Book, chunk_size: int = 6000, chunk_overlap: int = 300) -> list[Chunk]:
    """把 Book 切成若干块。

    规则：
    1. 短章节连续累积，直到接近 chunk_size 才切；
    2. 单章过长时在段落边界二次切分；
    3. 相邻块之间保留 overlap 字符的重叠，避免情节被切断；
    4. 每块带章节范围描述，供摘要时定位。
    """
    chunks: list[Chunk] = []
    buf: list[str] = []
    buf_chapters: list[str] = []
    buf_size = 0
    buf_has_new = False   # 缓冲区里除上一块的重叠尾巴外，是否还有新内容
    idx = 0

    def flush() -> None:
        nonlocal buf, buf_chapters, buf_size, buf_has_new, idx
        if not buf:
            return
        if not buf_has_new:
            # 只剩上一块的重叠尾巴：不产出新块，等真正的新内容进来一并送出。
            # 否则会产出一块 chapter/position 为空、内容纯重复的"空壳块"。
            return
        text = "\n\n".join(buf)
        idx += 1
        chunks.append(
            Chunk(
                index=idx,
                chapter=buf_chapters[0] if buf_chapters else "",
                position=_fmt_position(buf_chapters),
                text=text,
            )
        )
        tail = text[-chunk_overlap:] if chunk_overlap > 0 and len(text) > chunk_overlap else ""
        buf, buf_chapters, buf_size = ([tail] if tail else []), [], len(tail)
        buf_has_new = False

    for ch in book.chapters:
        if len(ch.text) <= chunk_size:
            if buf_size + len(ch.text) > chunk_size and buf:
                flush()
            buf.append(ch.text)
            buf_chapters.append(ch.title or f"第{ch.index}节")
            buf_size += len(ch.text)
            buf_has_new = True
        else:
            # 超长章节：先送走已积累的块，把它留下的重叠尾巴接到本章第一段之前
            flush()
            carried = "\n\n".join(buf)
            buf, buf_chapters, buf_size, buf_has_new = [], [], 0, False

            paras = [p for p in ch.text.split("\n") if p.strip()]
            parts: list[str] = []
            sub: list[str] = [carried] if carried else []
            sub_size = len(carried)
            pending_new = False          # 当前 sub 里是否有尚未产出过的新段落
            for p in paras:
                sub.append(p)
                sub_size += len(p)
                pending_new = True
                if sub_size >= chunk_size:
                    parts.append("\n".join(sub))
                    tail_p = "\n".join(sub)[-chunk_overlap:] if chunk_overlap > 0 else ""
                    sub = [tail_p] if tail_p else []
                    sub_size = len(tail_p)
                    pending_new = False
            # 收尾：残留内容里确有新段落才补最后一块，避免追加一块纯重叠内容
            if pending_new and sub and "".join(sub).strip():
                parts.append("\n".join(sub))

            total_parts = len(parts)
            for k, text in enumerate(parts, 1):
                idx += 1
                if total_parts > 1:
                    position = (f"{ch.title}（第{k}/{total_parts}部分）" if ch.title
                                else f"第{k}/{total_parts}部分")
                else:
                    position = ch.title or ""
                chunks.append(
                    Chunk(
                        index=idx,
                        chapter=ch.title,
                        position=position,
                        text=text,
                        part=k,
                        part_total=max(1, total_parts),
                    )
                )
    flush()

    # 标注总块数
    for c in chunks:
        if c.part_total == 1:
            c.part_total = len(chunks)
    return chunks


def _fmt_position(chapters: list[str]) -> str:
    if not chapters:
        return ""
    if len(chapters) == 1:
        return chapters[0]
    return f"{chapters[0]} 至 {chapters[-1]}"
