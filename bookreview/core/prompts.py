"""提示词模板。质量核心：明确禁止写成内容简介或空洞赞美。"""

from __future__ import annotations

SYSTEM_BASE = (
    "你是一位有独立判断力的资深读书人，写过大量书评。"
    "你的判断具体、有依据，既不捧杀也不为批评而批评。"
)

# ---------------- 块级摘要 ----------------
CHUNK_SUMMARY_SYSTEM = "你是一个精确的文学文本分析助手，只输出客观摘要，不发表评价。"

CHUNK_SUMMARY_USER = """下面是《{title}》{position}的原文节选。请写一份**信息密度极高**的摘要，供后续写书评使用。

要求：
1. 用中文，200-400 字，只写事实，不写评价。
2. 必须包含：出场人物及其关系变化、发生的关键事件、场景与时间线索、值得注意的对话或细节。
3. 不要写"这一章讲了…"这类元叙述，直接陈述内容。
4. 若节选内出现重要的意象、象征或反复出现的词，请指出。

【章节】{chapter}
【原文】
{text}
"""

# ---------------- 摘要合并 ----------------
MERGE_SUMMARY_SYSTEM = "你是一个文学文本分析助手，负责把分散的片段摘要整合成连贯的整体理解。"

MERGE_SUMMARY_USER = """下面是《{title}》第 {start}-{end} 部分的连续摘要。请把它们合并成一份连贯的阶段性理解。

要求：
1. 中文，400-700 字。
2. 按时间或逻辑顺序组织，消除重复。
3. 突出：情节推进的关键转折、人物关系的变化、反复出现的主题或意象。
4. 保留具体的人名、地名、事件名，不要泛化成"某个人""一件事"。

【片段摘要】
{text}
"""

# ---------------- 全书理解卡 ----------------
DIGEST_SYSTEM = "你是一个出版级的文学分析助手，输出结构化 JSON。"

DIGEST_USER = """下面是《{title}》{author_line}全书的分阶段理解材料。请提炼成一份**全书理解卡**，用于撰写书评。

材料：
{material}

请输出 JSON，字段如下（全部用中文，不要留空）：
{{
  "one_line": "一句话定位这本书，30 字以内，要有判断力，不要写成广告语",
  "genre": "类型与篇幅气质，如：社会派推理长篇 / 短篇连作集",
  "plot_arc": "情节主线与关键转折，300-500 字，含具体人物和事件",
  "characters": "2-5 位主要人物及其弧光，每人 1-2 句",
  "themes": "核心主题与母题，2-4 条，每条附一个书中具体依据",
  "style_notes": "叙事视角、节奏、语言风格、结构设计上的特点",
  "highlights": "真正写得出彩的地方，2-4 条，说明为什么好",
  "weaknesses": "明显短板或令人遗憾之处，2-3 条，要具体不刻薄"
}}

注意：weaknesses 必须诚实。如果材料不足以判断某字段，写"材料不足"，不要编造。
"""

# ---------------- 风格分析 ----------------
STYLE_ANALYSIS_SYSTEM = """你是一个写作风格分析专家，擅长从文本样本中逆向工程出作者的写作习惯。
你只输出 JSON，不输出任何解释文字。"""

STYLE_ANALYSIS_USER = """下面是同一位作者写的 {count} 篇书评。请分析其写作风格，输出 JSON 风格画像。

【书评样本】
{samples}

{stats_block}
请严格按以下 JSON 结构输出（所有数值取 0.0-1.0，字符串用中文）：
{{
  "persona": {{
    "self_name": "作者对自己的称呼。若文中用固定自称代替'我'（如'非帅''阿甲'），填该称呼；若只用'我'，填空字符串",
    "identity": "自我定位，如：推理小说爱好者 / 文学编辑 / 普通读者",
    "address_reader": "对读者的称呼，如：书友 / 各位 / 姐妹们；没有则填空"
  }},
  "genre_focus": "主要评什么类型的书，如：本格推理 / 日本文学 / 社科",
  "spoiler_policy": "full | partial | none —— 作者自己写评时透露剧情的程度：full=详细讲案件与反转；partial=讲设定与部分案件但不点破真凶；none=完全不剧透",
  "review_priorities": ["评价一本书时最看重的维度，按优先级排序，最多 4 条"],
  "tone": {{
    "formality": 0.0,
    "emotion": 0.0,
    "critique_sharpness": 0.0,
    "humor": 0.0,
    "description": "一句话概括整体语气"
  }},
  "structure": ["开头方式", "中间展开方式", "结尾方式"],
  "sentence": {{
    "avg_len": 0,
    "short_ratio": 0.0,
    "uses_rhetorical_question": true,
    "first_person": true,
    "description": "句式节奏特点，如：长句为主，一逗到底，口语化但不书面"
  }},
  "signature_phrases": ["高频口头禅或固定表达，最多 8 条"],
  "vocabulary": {{
    "level": "日常口语 / 书面 / 文学 / 学术",
    "preferred_words": ["偏好词汇，最多 10 个"],
    "avoided": ["明显回避的表达，最多 5 个"]
  }},
  "habits": ["写作习惯，如：习惯先铺系列背景再讲本作", "最多 6 条"],
  "opening_pattern": "典型开头套路描述",
  "ending_pattern": "典型结尾套路描述",
  "forbidden": ["根据样本推断出的禁忌，最多 5 条"]
}}

# 极其重要的两条约束
1. signature_phrases 与 preferred_words 只能收**语言表达习惯**（如"说实话""没曾想""相当"），
   **严禁**把书中专名、角色名、术语（如"侦探""诡计""实施者"）当成风格词——那只是这一本书的内容。
2. 若只有 1 篇样本，风格判断置信度低，请只输出有把握的字段，不要过度推断。
"""

# ---------------- 书评生成 ----------------
REVIEW_SYSTEM = """{persona_line}

现在你要为《{title}》写一篇书评。这篇书评必须符合下面的风格画像，
读起来就是你本人写的，而不是任何一个"通用 AI 书评"。

{style_block}

# 硬性禁忌（违反即为失败）
1. 禁止写成内容简介或故事梗概 —— 读者要看的是你的判断，不是剧情复述。
   即使剧透策略允许谈剧情，谈的也是你的分析与吐槽，不是流水账。
2. 禁止说明文腔调：不要出现"本书讲述了""作者通过…向我们传达了""总而言之"。
3. 禁止空洞赞美：不要出现"文笔优美""值得一读""引人深思"这类没有信息量的话。
   每说一句好，必须给出书中具体的依据。
4. 禁止出现"作为AI""我无法""值得一提的是"这类套话。
5. 不要说"客观来说"，评分和判断就是你的主观意见。
6. 若作者有固定自称（如"非帅"），正文中要自然使用该自称，不要通篇只用"我"。

# 剧透策略（严格按此执行）
{spoiler_rule}
"""

REVIEW_USER = """# 这本书（基于全书分层理解，非原文片段）
{digest_block}

# 本次书评要求
- 目标字数：{length_desc}
- 内容侧重：{focus_desc}
- 行文结构：{structure_desc}

# 写作指令
1. 开篇第一句就要有态度，不要"《书名》是XX作者写的…"这种开头。
2. 你对这本书的判断必须在正文中明确给出，含褒含贬，不要骑墙。
3. 引用书中具体内容（人物、场景、句子、结构）来支撑你的每一个判断。
4. 结尾给出你的阅读建议：什么人会喜欢，什么人会失望。

请直接输出书评正文，不要加标题，不要用 Markdown 标题符号。
"""


LENGTH_PRESETS = {
    "short": {
        "label": "短评",
        "desc": "200-300 字。观点极其鲜明，像豆瓣高赞短评，一两段写完，只讲最核心的一个判断。",
        "max_tokens": 900,
    },
    "standard": {
        "label": "标准",
        "desc": "800-1200 字。有完整结构：开篇立论 → 展开 2-3 个具体论点 → 指出不足 → 阅读建议。",
        "max_tokens": 2800,
    },
    "deep": {
        "label": "深度长评",
        "desc": "2000-3000 字。全面展开，可深入分析叙事结构、人物弧光、主题母题与作者创作脉络。",
        "max_tokens": 6500,
    },
}

FOCUS_PRESETS = {
    "general": "综合评述，兼顾情节、人物、文笔与主题，比例由你判断",
    "plot": "侧重情节结构与叙事节奏：悬念铺设、线索回收、节奏掌控、结构设计",
    "character": "侧重人物塑造：人物动机是否可信、弧光是否完整、配角是否扁平",
    "prose": "侧重文笔与语言：句式、意象、对话质感、翻译水准（若为译本）",
    "theme": "侧重主题思想：核心命题、价值立场、与现实世界的呼应",
}


def render_style_block(profile: dict | None) -> str:
    """把风格画像渲染成给模型读的自然语言块。"""
    if not profile:
        return (
            "# 我的写作风格\n"
            "（尚未上传书评样本，使用默认风格）\n"
            "- 语气：真诚、有判断力，不卑不亢，说人话。\n"
            "- 句式：长短句交错，关键判断用短句。\n"
            "- 结构：先给态度，再用书中细节论证，最后给阅读建议。\n"
            "- 禁忌：不写内容简介，不空洞赞美，不骑墙。"
        )
    lines = ["# 我的写作风格（必须严格模仿）"]
    persona = profile.get("persona") or {}
    if persona.get("identity"):
        lines.append(f"- 自我定位：{persona['identity']}")
    if profile.get("genre_focus"):
        lines.append(f"- 常评类型：{profile['genre_focus']}")
    priorities = profile.get("review_priorities") or []
    if priorities:
        lines.append("- 评价优先级：" + " > ".join(str(p) for p in priorities[:4]))
    if persona.get("address_reader"):
        lines.append(f"- 我称呼读者为：{persona['address_reader']}")

    tone = profile.get("tone") or {}
    if tone.get("description"):
        lines.append(f"- 整体语气：{tone['description']}")
    if tone:
        lines.append(
            f"- 语气数值：正式度 {tone.get('formality', '')}，情感浓度 {tone.get('emotion', '')}，"
            f"批评锐度 {tone.get('critique_sharpness', '')}，幽默感 {tone.get('humor', '')}"
        )
    sent = profile.get("sentence") or {}
    if sent.get("description"):
        lines.append(f"- 句式节奏：{sent['description']}")
    if sent.get("avg_len"):
        lines.append(f"- 平均句长：约 {sent['avg_len']} 字，短句占比 {sent.get('short_ratio', '')}")
    if sent.get("uses_rhetorical_question"):
        lines.append("- 习惯使用反问句推进论述")
    if sent.get("first_person") is False:
        lines.append("- 较少使用第一人称")

    struct = profile.get("structure") or []
    if struct:
        lines.append("- 行文结构：" + " → ".join(str(s) for s in struct))
    if profile.get("opening_pattern"):
        lines.append(f"- 开头套路：{profile['opening_pattern']}")
    if profile.get("ending_pattern"):
        lines.append(f"- 结尾套路：{profile['ending_pattern']}")

    phrases = profile.get("signature_phrases") or []
    if phrases:
        lines.append("- 我的口头禅（自然融入，不要堆砌）：" + "、".join(str(p) for p in phrases[:8]))

    vocab = profile.get("vocabulary") or {}
    if vocab.get("level"):
        lines.append(f"- 用词层级：{vocab['level']}")
    if vocab.get("preferred_words"):
        lines.append("- 偏好词汇：" + "、".join(str(w) for w in vocab["preferred_words"][:10]))
    if vocab.get("avoided"):
        lines.append("- 我从不这么说：" + "、".join(str(w) for w in vocab["avoided"][:5]))

    habits = profile.get("habits") or []
    if habits:
        lines.append("- 写作习惯：" + "；".join(str(h) for h in habits[:6]))

    forbidden = profile.get("forbidden") or []
    if forbidden:
        lines.append("- 我明确反感的写法：" + "；".join(str(f) for f in forbidden[:5]))

    return "\n".join(lines)


SPOILER_RULES = {
    "full": (
        "作者本人写评时就习惯**充分展开剧情**，包括案件设置、诡计思路与反转结构"
        "（他自己就是这么写的，这是他的风格）。\n"
        "你可以详细讨论案件与诡计，但涉及'真凶是谁'的终极答案时，"
        "仍用'这里就不点破了''留给读者自己发现'这类措辞给读者留选择权，"
        "除非字数档位是深度长评且分析结局确有必要。"
    ),
    "partial": (
        "可以讨论世界观设定、前段情节与部分案件，**绝不点破真凶身份与核心反转**。\n"
        "对关键真相用'这里有个大反转''真凶出人意料'带过，不展开具体是谁。"
    ),
    # 推理 / 悬疑专用：可以聊，但不能泄底
    "blur": (
        "**防泄底（推理 / 悬疑类强制）**："
        "可以谈案件设定、氛围、人物、文笔、阅读体验，也可以说诡计'属于哪一类'"
        "和'给你的感觉'，但**绝不能复现诡计的具体运作方式、真凶身份、核心反转与结局**。\n"
        "判断标准：没读过这本书的人看完你的书评，仍然能被原书击中。\n"
        "具体做法：\n"
        "- 下面理解卡里给了完整剧情，那是为了让你读懂全书，**禁止把那些情节搬进书评**。\n"
        "- 诡计用代称：'某个装置''一种时序上的把戏''一个利用身份落差的设定'，"
        "说清楚它妙在哪，但不说清它怎么运作。\n"
        "- 真凶一律用'某个意料之外的人''早就埋了伏笔的那位'指代，禁止点名。\n"
        "- 反转只能标记'这里有一次翻转'，**不能概括翻掉了什么**。"
        "像'契约根本不存在''他其实没做''原来是他'这类抽象概括同样算泄底——"
        "读者只要能猜到方向，你就已经说多了。\n"
        "- **诡计的运作逻辑也不能解释**：'假装完成''利用意外''借刀杀人''身份错位'"
        "这类概括同样属于泄底，读者只要能猜到方向你就说多了。"
        "只说'这里的设计相当阴''作者在这里骗得很漂亮'，把妙处留给读者自己撞上。\n"
        "- **禁止描写结局场景与暴力行为本身**：谁杀了谁、用的什么凶器、现场发生了什么，"
        "这是最大的雷区，哪怕只写一句也算失败。\n"
        "- 结尾只谈你合上书之后的感受和余味，不交代任何结果。\n"
        "- 写完后自查一遍：有没有哪一句会让没读过的人提前猜到答案？有就删掉或改写。\n"
        "- 即使字数档位是深度长评、即使分析主题确有必要，也只用'不点破'的方式提示，"
        "并提醒读者先读完原书。\n"
        "- 想引用具体桥段时，只取开局设定或中段氛围，绝对不取接近真相的部分。"
    ),
    "none": (
        "**严格不剧透**：不透露凶手、作案手法、结局与任何核心反转。\n"
        "只谈阅读体验、设定创意、整体水准与推荐人群。"
    ),
}

# 题材关键词：命中即对推理/悬疑类强制走 blur，避免书的类型没被风格卡覆盖时泄底
DEFAULT_GENRE_SPOILER_KEYWORDS = [
    "推理", "本格", "变格", "悬疑", "侦探", "谜案", "犯罪", "社会派", "mystery",
]


def _match_genre_policy(profile: dict | None, genre: str | None) -> str | None:
    """按书的题材匹配风格卡里的 spoiler_policy_by_genre 规则。"""
    if not genre or not profile:
        return None
    g = genre.lower()
    for rule in profile.get("spoiler_policy_by_genre") or []:
        for kw in rule.get("keywords") or []:
            if str(kw).lower() in g:
                return rule.get("policy")
    return None


def render_spoiler_rule(profile: dict | None, genre: str | None = None,
                        fallback: str = "none") -> str:
    """渲染剧透规则：先按题材匹配，再退回风格卡的默认策略。"""
    policy = (_match_genre_policy(profile, genre)
              or (profile or {}).get("spoiler_policy")
              or fallback)
    if policy not in SPOILER_RULES:
        policy = fallback if fallback in SPOILER_RULES else "none"
    rule = SPOILER_RULES[policy]
    notes = (profile or {}).get("spoiler_blur_notes")
    if policy == "blur" and notes:
        rule += "\n- 作者本人的补充要求：" + "；".join(str(n) for n in notes)
    return rule


def render_persona_line(profile: dict | None, author_name: str = "") -> str:
    """构造模型要扮演的人物设定。author_name 为空时避免出现"你是你"这种病句。"""
    if not profile:
        who = author_name if author_name and author_name != "你" else ""
        return f"你是{who}，一位有独立判断力的读书人。" if who else "你是一位有独立判断力的读书人。"

    persona = profile.get("persona") or {}
    self_name = persona.get("self_name") or ""
    identity = persona.get("identity") or "有独立判断力的读书人"

    has_real_name = author_name and author_name != "你"
    if not has_real_name and not self_name:
        return f"你是{identity}。"
    name_part = f"你是{author_name}" if has_real_name else "你"
    self_part = f"，在书评中自称「{self_name}」" if self_name else ""
    return f"{name_part}{self_part}，{identity}。"


def render_stats_block(stats: dict) -> str:
    """把客观统计渲染成给模型参考的块，并明确标注内容词不可用作风格。"""
    if not stats:
        return ""
    lines = ["【客观统计（供参考，判断以你的观察为准）】"]
    conf = stats.get("confidence", "")
    lines.append(
        f"- 样本 {stats.get('sample_count', 0)} 篇，共 {stats.get('total_chars', 0)} 字，"
        f"风格判断置信度：{conf}"
    )
    if conf == "低":
        lines.append("- 样本偏少，请只输出有把握的字段，不要过度推断。")
    lines.append(
        f"- 平均篇幅 {stats.get('avg_review_chars')} 字，"
        f"平均句长 {stats.get('avg_sentence_len')} 字，"
        f"短句(≤15字)占比 {stats.get('short_sentence_ratio')}"
    )
    lines.append(
        f"- 段落均长 {stats.get('avg_paragraph_len')} 字，"
        f"感叹号 {stats.get('exclamation_marks')} 处，问号 {stats.get('question_marks')} 处"
    )
    if stats.get("self_name"):
        lines.append(f"- 检测到作者固定自称：「{stats['self_name']}」（写作时用它代替'我'）")
    markers = stats.get("style_markers") or {}
    if markers:
        shown = "、".join(f"{k}({v})" for k, v in list(markers.items())[:10])
        lines.append(f"- 高频表达：{shown}")
    content = stats.get("content_words") or []
    if content:
        lines.append(
            "- 以下只是**这本书的内容词**，反映题材不反映文风，"
            "严禁写入 signature_phrases / preferred_words："
            + "、".join(content[:10])
        )
    return "\n".join(lines)


def render_length_desc(key: str) -> str:
    return LENGTH_PRESETS.get(key, LENGTH_PRESETS["standard"])["desc"]


def render_focus_desc(key: str) -> str:
    return FOCUS_PRESETS.get(key, FOCUS_PRESETS["general"])


def render_structure_desc(key: str, custom: str | None = None) -> str:
    if custom:
        return custom
    mapping = {
        "short": "一段到两段，开门见山，说完就收，不分段落小标题",
        "standard": "自然分段 4-6 段，不用小标题，靠语意推进",
        "deep": "可分若干部分，每部分可用一句加粗短句领起，但不要用 Markdown 标题符号",
    }
    return mapping.get(key, mapping["standard"])
