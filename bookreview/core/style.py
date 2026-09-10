"""风格画像：统计特征 + LLM 提炼 → 可编辑的 JSON 画像卡。"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from .llm import LLMClient
from .prompts import (
    STYLE_ANALYSIS_SYSTEM,
    STYLE_ANALYSIS_USER,
    render_stats_block,
)
from .sanitizer import sanitize, sanitize_many

# 样本总字数上限，超出部分截断（避免烧 token）
MAX_SAMPLE_CHARS = 15000

RE_SENT_SPLIT = re.compile(r"[。！？!?；;…]+")
RE_FIRST_PERSON = re.compile(r"我|我们|笔者")
RE_STOPWORD = re.compile(r"[的了是在和与及就不都很也有还要会能将于对为被把从第到]")

# 风格标记词白名单：这些是"怎么写"的信号，不是"写了什么"
STYLE_MARKERS = [
    "说实话", "老实说", "其实", "不过", "当然", "所以", "而且", "但是", "然而",
    "没想到", "没曾想", "不曾想", "本以为", "本来", "结果", "反正", "毕竟",
    "话说", "另外", "首先", "其次", "接着", "紧接着", "然后", "最后",
    "总的来说", "总而言之", "整体来看", "有一说一",
    "有点", "相当", "特别", "非常", "真的", "简直", "完全", "绝对", "莫名",
    "倒是", "倒是说", "只能说", "可以说", "怎么说", "不得不说",
    "在我看来", "个人觉得", "我感觉", "我觉得", "我以为", "我原以为", "我猜",
    "估计", "大概", "似乎", "仿佛", "显然", "毫无疑问",
    "上头", "牛逼", "无语", "给力", "看头", "惊艳", "拉胯", "翻车", "封神",
]

# 常见主语，检测自称时要排除
COMMON_SUBJECTS = {
    "我", "我们", "你", "你们", "他", "她", "它", "他们", "她们", "大家",
    "这", "那", "这个", "那个", "作者", "书中", "故事", "小说", "读者",
    "本书", "作品", "内容", "情节", "人物", "主角", "侦探", "凶手",
}

RE_SELF_CANDIDATE = re.compile(
    r"([\u4e00-\u9fff]{2,4})(?:看|觉得|认为|要讲|要说|想|猜|以为|发现|觉得|感觉)"
)


def compute_stats(samples: list[str]) -> dict:
    """客观统计特征，作为 LLM 分析的依据。"""
    if not samples:
        return {}
    all_text = "\n".join(samples)
    total_chars = len(all_text)

    sentences = [s.strip() for s in RE_SENT_SPLIT.split(all_text) if len(s.strip()) > 1]
    sent_lens = [len(s) for s in sentences]
    avg_sent = round(sum(sent_lens) / len(sent_lens), 1) if sent_lens else 0
    short_ratio = round(sum(1 for l in sent_lens if l <= 15) / max(1, len(sent_lens)), 2)

    question_ratio = round(all_text.count("？") + all_text.count("?"), 3)
    excl_ratio = round(all_text.count("！") + all_text.count("!"), 3)

    # 高频双字词（粗分词）
    bigrams: Counter = Counter()
    for s in sentences:
        clean = re.sub(r"[^\u4e00-\u9fff]", "", s)
        for i in range(len(clean) - 1):
            w = clean[i:i + 2]
            if not RE_STOPWORD.search(w):
                bigrams[w] += 1
    top_words = [w for w, c in bigrams.most_common(40) if c >= 3][:15]

    paras = [p for p in all_text.split("\n") if p.strip()]
    avg_para = round(sum(len(p) for p in paras) / max(1, len(paras)), 1)

    # 风格标记词：只统计白名单里的，避免把"这本书讲了什么"误当成"怎么写"
    markers: dict[str, int] = {}
    for w in STYLE_MARKERS:
        c = all_text.count(w)
        if c >= 2:
            markers[w] = c
    markers = dict(sorted(markers.items(), key=lambda x: -x[1])[:12])

    # 内容词（高频双字）：仅供参考，明确标记，禁止作为风格特征使用
    top_content = [w for w, c in bigrams.most_common(40) if c >= 3][:15]

    # 自称检测：如"非帅"，作者用它代替"我"
    self_name = detect_self_name(all_text)

    # 置信度：样本越少，风格词越不可信
    confidence = "高" if len(samples) >= 5 else ("中" if len(samples) >= 3 else "低")

    return {
        "sample_count": len(samples),
        "confidence": confidence,
        "total_chars": total_chars,
        "avg_review_chars": round(total_chars / len(samples)),
        "avg_sentence_len": avg_sent,
        "short_sentence_ratio": short_ratio,
        "avg_paragraph_len": avg_para,
        "question_marks": question_ratio,
        "exclamation_marks": excl_ratio,
        "first_person_density": round(
            len(RE_FIRST_PERSON.findall(all_text)) / max(1, total_chars / 1000), 2
        ),
        "self_name": self_name,
        "style_markers": markers,
        # 内容词，禁止入风格特征
        "content_words": top_content,
    }


STOP_CHARS = "的了是在和与及不都很也有就还要会能将于对为被把从第到这那他把她它们"


def detect_self_name(text: str) -> str:
    """检测作者的自称（如"非帅"）。

    难点：正则贪婪匹配会把"最近非帅看"整段吃进去，得到"最近非帅"。
    解法：对每个匹配，同时取尾部 2/3/4 字作为候选（主语总是紧邻动词），
    再按出现频次投票——带脏前缀的候选频次必然低，会被自然淘汰。
    """
    counter: Counter = Counter()
    for m in RE_SELF_CANDIDATE.finditer(text):
        full = m.group(1)
        seen = set()
        for n in (2, 3, 4):
            if len(full) < n:
                continue
            cand = full[-n:]
            if cand in seen:
                continue
            seen.add(cand)
            if cand in COMMON_SUBJECTS:
                continue
            if any(ch in STOP_CHARS for ch in cand):
                continue
            counter[cand] += 1

    # 频次优先，同频次取更长的（3 字自称比 2 字更可信）
    ranked = sorted(counter.items(), key=lambda x: (x[1], len(x[0])), reverse=True)
    for name, c in ranked:
        if c >= 2:
            return name
    return ""


class StyleAnalyzer:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    def analyze(self, samples: list[str], hint: str = "",
                sanitize: bool = True) -> dict:
        """输入若干篇书评文本，输出风格画像 dict。

        sanitize=True 时会先剔除样本里混杂的 AI 生成内容，
        否则学到的会是 AI 的腔调而不是本人的。
        """
        samples = [s.strip() for s in samples if s and s.strip()]
        if not samples:
            raise ValueError("没有可用的书评样本")

        self.clean_notes: list[str] = []
        if sanitize:
            samples, self.clean_notes = sanitize_many(samples)
            if not samples:
                raise ValueError(
                    "样本净化后为空——这些文件里可能全是 AI 生成内容，"
                    "没有找到你本人写的文字。请换用你自己写的原始书评。"
                )

        stats = compute_stats(samples)
        packed = self._pack_samples(samples)
        user = STYLE_ANALYSIS_USER.format(
            count=len(samples),
            samples=packed,
            stats_block=render_stats_block(stats),
        )
        if hint:
            user += f"\n\n【作者对自身风格的补充描述】\n{hint}"

        profile = self.llm.chat_json(
            STYLE_ANALYSIS_SYSTEM, user, temperature=0.3, max_tokens=2500
        )

        # 用统计结果校正/补全 LLM 可能给错的数值字段
        persona = profile.setdefault("persona", {})
        if stats.get("self_name") and not persona.get("self_name"):
            persona["self_name"] = stats["self_name"]
        sent = profile.setdefault("sentence", {})
        sent.setdefault("avg_len", stats.get("avg_sentence_len", 0))
        sent.setdefault("short_ratio", stats.get("short_sentence_ratio", 0))
        if stats.get("question_marks", 0) > 0:
            sent["uses_rhetorical_question"] = True
        profile["_stats"] = stats
        profile["_sample_chars"] = stats.get("total_chars", 0)
        return profile

    def _pack_samples(self, samples: list[str]) -> str:
        """打包样本，超出上限时优先保留较新的完整篇目。"""
        parts: list[str] = []
        size = 0
        for i, s in enumerate(reversed(samples), 1):
            block = f"--- 样本 {i} ---\n{s}\n"
            if size + len(block) > MAX_SAMPLE_CHARS and parts:
                break
            parts.append(block)
            size += len(block)
        return "\n".join(reversed(parts))


def load_samples_from_paths(paths: list[str | Path]) -> list[str]:
    """从 txt / md / docx 文件读取书评样本。多篇可用分隔线分割。"""
    from .parsers.factory import parse_book  # 避免循环导入

    out: list[str] = []
    for p in paths:
        path = Path(p)
        if not path.exists():
            continue
        suffix = path.suffix.lower()
        if suffix in (".txt", ".md", ".markdown"):
            text = path.read_text(encoding="utf-8", errors="ignore")
            # 必须先整体净化再切分：AI 内容的起始标记（#DeepSeek: 等）
            # 若先被分隔线切成碎片，标记就会失效，导致 AI 文本混入样本。
            text, _ = sanitize(text)
            pieces = split_samples(text)
            out.extend(pieces if len(pieces) > 1 else [text])
        elif suffix == ".docx":
            book = parse_book(path)
            out.append(sanitize(book.full_text)[0])
        else:
            try:
                book = parse_book(path)
                out.append(sanitize(book.full_text)[0])
            except Exception:
                continue
    return [s for s in out if len(s.strip()) >= 50]


def split_samples(text: str) -> list[str]:
    """txt 中多篇书评按分隔线切分。"""
    seps = [
        r"\n\s*={3,}\s*\n",
        r"\n\s*-{3,}\s*\n",
        r"\n\s*#{1,3}\s+",
    ]
    import re as _re
    parts = [text]
    for sep in seps:
        new_parts: list[str] = []
        for p in parts:
            new_parts.extend(_re.split(sep, p))
        parts = new_parts
    return [p.strip() for p in parts if len(p.strip()) >= 50]
