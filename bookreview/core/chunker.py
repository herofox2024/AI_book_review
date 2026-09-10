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
    idx = 0

    def flush() -> None:
        nonlocal buf, buf_chapters, buf_size, idx
        if not buf:
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

    for ch in book.chapters:
        if len(ch.text) <= chunk_size:
            if buf_size + len(ch.text) > chunk_size and buf:
                flush()
            buf.append(ch.text)
            buf_chapters.append(ch.title or f"第{ch.index}节")
            buf_size += len(ch.text)
        else:
            # 超长章节：按段落切
            flush()
            paras = [p for p in ch.text.split("\n") if p.strip()]
            sub: list[str] = []
            sub_size = 0
            part = 1
            total = max(1, (len(ch.text) + chunk_size - 1) // chunk_size)
            for p in paras:
                sub.append(p)
                sub_size += len(p)
                if sub_size >= chunk_size:
                    idx += 1
                    chunks.append(
                        Chunk(
                            index=idx,
                            chapter=ch.title,
                            position=f"{ch.title}（第{part}/{total}部分）" if ch.title
                            else f"第{part}/{total}部分",
                            text="\n".join(sub),
                            part=part,
                            part_total=total,
                        )
                    )
                    tail_p = "\n".join(sub)[-chunk_overlap:] if chunk_overlap > 0 else ""
                    sub = [tail_p] if tail_p else []
                    sub_size = len(tail_p)
                    part += 1
            if sub and "".join(sub).strip():
                idx += 1
                chunks.append(
                    Chunk(
                        index=idx,
                        chapter=ch.title,
                        position=f"{ch.title}（第{part}/{total}部分）" if ch.title
                        else f"第{part}/{total}部分",
                        text="\n".join(sub),
                        part=part,
                        part_total=total,
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
