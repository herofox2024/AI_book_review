"""文本清洗：页码、页眉页脚、多余空白、全角标点规范化。"""

from __future__ import annotations

import re
from collections import Counter

# 纯页码行：单独成行的数字 / 第 N 页 / - 12 -
RE_PAGE_NUM = re.compile(r"^\s*(?:[-—–·\.]*\s*)?(?:第?\s*\d+\s*[页頁]?\s*)\s*(?:[-—–·\.]*\s*)?$")
RE_DASH_PAGE = re.compile(r"^\s*[-—–]{1,3}\s*\d+\s*[-—–]{1,3}\s*$")
RE_BLANKS = re.compile(r"[ \t\u3000]+")
RE_MULTI_NL = re.compile(r"\n{3,}")
RE_CHAPTER = re.compile(
    r"^\s*(?:第\s*[0-9一二三四五六七八九十百千零〇两]+\s*[章节回卷部篇節]|(?:序|序章|楔子|引子|前言|后记|後記|尾声|尾聲|附录|附錄|番外))"
)

# 中文书名号内的标题行，如：第一章  薄冰之沼
RE_CN_CHAPTER_TITLE = re.compile(r"^\s*第[0-9一二三四五六七八九十百千零〇两]+[章节回卷部篇節]")


def is_noise_line(line: str) -> bool:
    s = line.strip()
    if not s:
        return True
    if RE_PAGE_NUM.match(s) and len(s) <= 12:
        return True
    if RE_DASH_PAGE.match(s):
        return True
    # 纯符号行
    if re.fullmatch(r"[-—–=*·\.~_ ]{1,20}", s):
        return True
    return False


def normalize(text: str) -> str:
    """基础规范化：换行、空格、引号。"""
    t = text.replace("\r\n", "\n").replace("\r", "\n")
    t = t.replace("\u00a0", " ")
    t = RE_BLANKS.sub(" ", t)
    lines = [ln.strip() for ln in t.split("\n")]
    t = "\n".join(lines)
    t = RE_MULTI_NL.sub("\n\n", t)
    return t.strip()


def detect_repeated_lines(lines: list[str], min_repeat: int = 5) -> set[str]:
    """识别页眉页脚：在正文中高频重复出现的短行。"""
    counter = Counter(ln.strip() for ln in lines if 0 < len(ln.strip()) <= 40)
    return {ln for ln, c in counter.items() if c >= min_repeat}


def clean_text(text: str, drop_repeated: bool = True) -> str:
    """清洗一段正文。"""
    t = normalize(text)
    lines = t.split("\n")
    if drop_repeated and len(lines) > 60:
        noise = detect_repeated_lines(lines)
        lines = [ln for ln in lines if ln.strip() not in noise]
    lines = [ln for ln in lines if not is_noise_line(ln)]
    return "\n".join(lines).strip()


def guess_title(line: str) -> str | None:
    """判断某行是否是章节标题。"""
    s = line.strip()
    if not s or len(s) > 60:
        return None
    if RE_CN_CHAPTER_TITLE.match(s) or RE_CHAPTER.match(s):
        return s
    return None


def split_by_headings(text: str, max_chars: int = 20000) -> list[tuple[str, str]]:
    """按章节标题切分；没有标题或某段过长时按字数兜底。

    返回 [(title, body), ...]
    """
    lines = text.split("\n")
    blocks: list[tuple[str, str]] = []
    cur_title = ""
    cur_buf: list[str] = []

    def flush() -> None:
        if cur_buf:
            blocks.append((cur_title, "\n".join(cur_buf).strip()))
            cur_buf.clear()

    for ln in lines:
        t = guess_title(ln)
        if t:
            flush()
            cur_title = t
        else:
            cur_buf.append(ln)
    flush()

    # 标题识别失败 → 整篇作为一块
    if len(blocks) <= 1:
        blocks = [("", text)]

    # 过长的块再按段落均分
    result: list[tuple[str, str]] = []
    for title, body in blocks:
        if len(body) <= max_chars:
            result.append((title, body))
            continue
        paras = [p for p in body.split("\n") if p.strip()]
        buf, size = [], 0
        part = 1
        for p in paras:
            buf.append(p)
            size += len(p)
            if size >= max_chars:
                suffix = f"（续{part}）" if part > 1 else "（上）"
                result.append((f"{title}{suffix}".strip(), "\n".join(buf)))
                buf, size = [], 0
                part += 1
        if buf:
            suffix = f"（续{part}）" if part > 1 else ""
            result.append((f"{title}{suffix}".strip(), "\n".join(buf)))
    return result
