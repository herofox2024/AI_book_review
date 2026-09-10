"""样本净化：剔除混杂在书评文件里的 AI 生成内容与对话痕迹。

真实场景里，用户的"书评"文件常常是这样的：
    <给 AI 的指令>
    <自己的真实书评>
    ---
    这是我润色后的版本...      <- AI 产出的开始
    #User: 改写成小红书格式
    #DeepSeek: 💥绝了！！...   <- 另一个 AI 的产出

如果不做净化，风格学习会学到 AI 的腔调，完全背离目标。
本模块负责切掉 AI 部分，只留下人写的原文。
"""

from __future__ import annotations

import re

# === A 类：AI 的回复，从这里开始截断 ===
AI_START_MARKERS = [
    # #User: / #Human: 后面跟的往往是作者自己的原文，不能一律截断，
    # 单独放下面的 INSTRUCTION_LINE_MARKERS 里处理。
    r"^\s*#{1,3}\s*(DeepSeek|ChatGPT|Claude|Assistant|GPT|AI|Qwen|GLM|智谱|豆包|通义|Kimi|文心|Copilot|Gemini)\s*[:：]",
    r"^\s*主要(修改|改动|调整)\s*[:：]",
    r"^\s*(根据|基于)(这篇|这篇文章|文章|以上内容)?(内容)?(，|,)?\s*我?(为您|给你|帮你)?(提供|给出|整理|总结)",
    r"^\s*(已|已经)?(根据|按照)你(的)?要求",
    r"^\s*以下是.{0,10}(标题|书名|建议)",
    r"^\s*###?\s*\*\*推荐标题",
    # 「这是我润色后的版本……」——后面不接冒号，单独一条
    r"^\s*(这是我|以下是|下面是|上面是)\s*(润色|改写|修改|优化|调整|重写|洗稿)后?的?\s*(版本|内容|文章|文本|稿子)?",
    # 「修改版：」「润色版：」「改写版：」——AI 产出的成稿
    r"^\s*\**\s*(修改|润色|改写|优化|重写|洗稿|调整|精修)[后的]*\s*(版本|版|稿|文本|内容|文章)?\s*\**\s*[:：，,]",
    # 「公众号：」「小红书格式：」——投放渠道版本，基本都是 AI 改写
    r"^\s*\**\s*(公众号|小红书|知乎|豆瓣|微博|简书|今日头条|视频号)\s*(格式|版|文案|版本|风格)?\s*\**\s*[:：]",
    r"^\s*\**\s*改写为?\s*(小红书|公众号|知乎|豆瓣)?\s*格式?\s*\**\s*[:：]",
    r"^\s*\**\s*(改写|润色|修改)\s*说明\s*\**\s*[:：]",
]

# === B 类：作者写给 AI 的指令行 —— 只删这一行，正文要保留 ===
# 典型：「#User : 把这篇文章润色下」后面跟的其实是作者自己的原文。
INSTRUCTION_LINE_MARKERS = [
    r"^\s*#{1,3}\s*(User|Human|用户|我)\s*[:：]",
]

# 指令型首行（用户写给 AI 的 prompt），长度短且含改写类动词
INSTRUCTION_PATTERN = re.compile(
    r"^\s*(把下面|把这篇|请(把|帮|将)|帮我|帮我把|将下面|给这篇|把以上)"
)

# 小红书 / 社媒标签行：#推理小说 #本格推理 ...
TAG_LINE = re.compile(r"^\s*(#[^\s#]{1,20}\s*){2,}\s*$")

# emoji 及变体选择符
EMOJI = re.compile(
    "["
    "\U0001F000-\U0001FAFF"
    "\U00002600-\U000027BF"
    "\U0001F1E6-\U0001F1FF"
    "\U00002190-\U000021FF"
    "\U00002B00-\U00002BFF"
    "\U0000FE0F"
    "\U0000200D"
    "\U00002B50"
    "]+"
)

# 明显的社媒装饰行
SOCIAL_LINE = re.compile(r"^\s*(姐妹们|宝子们|家人们|求求|跪了|封神|绝绝子).{0,20}[！!]{1,}")

# 公众号/小红书的互动召唤句（CTA）——作者本人写的书评极少出现
RE_CTA = re.compile(
    r"欢迎(在)?(评论区|下方|留言)|评论区(聊聊|分享|留言|告诉我)|一起聊聊"
    r"|你们(是否也曾|觉得|认为).{0,12}[？?]|欢迎分享你的|你的看法"
)
# 排版痕迹：多级小标题、大段加粗
RE_HEADING = re.compile(r"^\s*#{3,4}\s+\S", re.MULTILINE)
RE_BOLD = re.compile(r"\*\*[^*\n]{2,40}\*\*")

_COMPILED_MARKERS = [re.compile(p) for p in AI_START_MARKERS]
_COMPILED_INSTR = [re.compile(p) for p in INSTRUCTION_LINE_MARKERS]


def sanitize(text: str, verbose: bool = False) -> tuple[str, list[str]]:
    """净化单篇样本，返回 (净化后文本, 剔除原因列表)。"""
    notes: list[str] = []
    lines = text.split("\n")

    # 1) 找到 AI 内容的起点并截断；指令行单独处理
    #
    # 关键在于「#User:」这类指令行后面跟的是什么：
    #   - 文件开头就有 #User:（前面没有正文）→ 后面是作者贴进去的原文，删行继续
    #   - 已经写了几百字才出现 #User:        → 后面是 AI 的产出，直接截断
    cut = len(lines)
    drop: set[int] = set()
    for i, line in enumerate(lines):
        if i >= cut:
            break
        if len(line) < 120 and any(p.match(line) for p in _COMPILED_INSTR):
            prior = len("".join(lines[:i]).strip())
            if prior >= INSTRUCTION_TRUNCATE_THRESHOLD:
                cut = i
                notes.append(f"第{i+1}行是指令行且前面已有 {prior} 字原文，"
                             f"判定后续为 AI 产出并截断：{line.strip()[:24]}")
                break
            drop.add(i)
            notes.append(f"剔除指令行（后接原文）：{line.strip()[:30]}")
            continue
        for pat in _COMPILED_MARKERS:
            if pat.match(line):
                cut = i
                notes.append(f"第{i+1}行起判定为 AI 内容并截断：{line.strip()[:30]}")
                break
    lines = lines[:cut]

    # 2) 剔除指令型首行
    if lines and INSTRUCTION_PATTERN.match(lines[0]) and len(lines[0]) < 60:
        notes.append(f"剔除指令首行：{lines[0].strip()[:30]}")
        lines = lines[1:]

    # 3) 逐行清理
    kept: list[str] = []
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if idx in drop:
            continue
        if not stripped:
            kept.append("")
            continue
        if TAG_LINE.match(stripped):
            notes.append(f"剔除标签行：{stripped[:30]}")
            continue
        if SOCIAL_LINE.match(stripped):
            notes.append(f"剔除社媒腔行：{stripped[:30]}")
            continue
        cleaned = EMOJI.sub("", line).strip()
        if not cleaned:
            notes.append(f"剔除纯 emoji 行：{stripped[:20]}")
            continue
        kept.append(cleaned)

    result = "\n".join(kept).strip()
    # 4) 收尾：去掉多余空行
    result = re.sub(r"\n{3,}", "\n\n", result)
    if _looks_ai_article(result):
        notes.append(
            "整篇判定为 AI 生成的公众号/社媒稿（含互动召唤句且通篇分节加粗），"
            "未找到作者本人写的原文，已丢弃"
        )
        return "", notes
    if verbose:
        return result, notes
    return result, notes


def _looks_ai_article(text: str) -> bool:
    """判断截断后剩下的部分是否仍是 AI 洗稿。

    单看"有加粗"或"有 CTA"都不足以定罪——只有两者同时具备时才判定，
    避免误杀作者本人写的正常书评。
    """
    if len(text) < 150:
        return False
    has_cta = bool(RE_CTA.search(text))
    if not has_cta:
        return False
    markup = len(RE_HEADING.findall(text)) >= 2 or len(RE_BOLD.findall(text)) >= 4
    return markup


# 多行模式下使用的版本
TAG_LINE_ML = re.compile(TAG_LINE.pattern, re.MULTILINE)
SOCIAL_LINE_ML = re.compile(SOCIAL_LINE.pattern, re.MULTILINE)

MIN_SAMPLE_CHARS = 100   # 净化后低于此长度视为残片
FALLBACK_CHARS = 50      # 全部被丢弃时的兜底长度

# 指令行之前已积累的原文超过这个字数，就认为指令之后是 AI 产出
INSTRUCTION_TRUNCATE_THRESHOLD = 300


def sanitize_many(texts: list[str]) -> tuple[list[str], list[str]]:
    """批量净化，丢弃净化后过短的残片。

    若全部样本都被判为过短，保留最长的一片——宁可留下稍短的原文，
    也不能把用户辛苦整理的样本全部误杀。
    """
    out: list[str] = []
    notes: list[str] = []
    longest = ""
    for i, t in enumerate(texts, 1):
        cleaned, n = sanitize(t)
        for item in n:
            notes.append(f"[样本{i}] {item}")
        if len(cleaned) >= MIN_SAMPLE_CHARS:
            out.append(cleaned)
        else:
            notes.append(f"[样本{i}] 净化后仅 {len(cleaned)} 字，低于 {MIN_SAMPLE_CHARS} 字")
            if len(cleaned) > len(longest):
                longest = cleaned

    if not out and len(longest) >= FALLBACK_CHARS:
        out.append(longest)
        notes.append(f"全部样本净化后过短，保留最长的一篇（{len(longest)} 字）")
    return out, notes


def looks_ai_generated(text: str) -> bool:
    """粗判：整篇是否像 AI 写的（AI 标记 / emoji 密度 / 标签行 / 社媒腔）。"""
    for line in text.split("\n"):
        for pat in _COMPILED_MARKERS:
            if pat.match(line):
                return True
    if TAG_LINE_ML.search(text):
        return True
    if len(EMOJI.findall(text)) >= 3:
        return True
    if len(SOCIAL_LINE_ML.findall(text)) >= 2:
        return True
    return False
