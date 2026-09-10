"""用假模型跑通全链路，验证代码路径与缓存，不消耗 token。"""

from __future__ import annotations

import sys
import os
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
TEST_DATA_DIR = Path(tempfile.mkdtemp(prefix="bookreview_test_"))
os.environ["BOOKREVIEW_DATA_DIR"] = str(TEST_DATA_DIR)

from bookreview.core.chunker import chunk_book  # noqa: E402
from bookreview.core.pipeline import Pipeline  # noqa: E402
from bookreview.core.prompts import (  # noqa: E402
    render_style_block, LENGTH_PRESETS, FOCUS_PRESETS,
)
from bookreview.core.sanitizer import (  # noqa: E402
    sanitize, sanitize_many, looks_ai_generated,
)
from bookreview.core.style import (  # noqa: E402
    compute_stats, split_samples, detect_self_name,
)

SAMPLES_DIR = Path(__file__).parent / "sample_books"
EPUB = SAMPLES_DIR / "薄冰之沼.epub"


class FakeLLM:
    """按提示词特征返回不同结果，模拟真实模型。"""

    def __init__(self):
        self.chat_calls: list[str] = []
        self.json_calls: list[str] = []
        self.models_used: set[str] = set()

    def chat(self, system, user, temperature=None, max_tokens=None,
             json_mode=False, model=None):
        self.chat_calls.append(user)
        if model:
            self.models_used.add(model)
        if "风格" in system and "读书人" in system:
            return "# 书评正文（模拟）\n这是一篇模拟书评。"
        return f"[模拟摘要] 处理了 {len(user)} 字符：情节推进，人物关系变化。"

    def chat_json(self, system, user, temperature=None, max_tokens=None, model=None):
        self.json_calls.append(user)
        if model:
            self.models_used.add(model)
        if "风格画像" in user or "写作风格" in user:
            return {
                "tone": {"formality": 0.6, "emotion": 0.7, "critique_sharpness": 0.8,
                         "humor": 0.3, "description": "真诚犀利，不捧杀"},
                "structure": ["开篇给态度", "用细节论证", "指出短板", "阅读建议"],
                "sentence": {"avg_len": 26, "short_ratio": 0.4,
                             "uses_rhetorical_question": True, "first_person": True,
                             "description": "长短句交错"},
                "signature_phrases": ["说白了", "值得注意的是"],
                "vocabulary": {"level": "文学", "preferred_words": ["克制", "锋利"],
                               "avoided": ["空洞赞美"]},
                "habits": ["先给结论再展开"],
                "opening_pattern": "用一个具体场景切入",
                "ending_pattern": "回到开头的意象",
                "forbidden": ["内容简介"],
            }
        return {
            "one_line": "一部关于沉默与错过的社会派推理",
            "genre": "社会派推理中篇",
            "plot_arc": "雪夜来客引出七年前旧案，沼边女尸牵出跟踪者与真凶。",
            "characters": "光司先生：沉默的未婚夫，背负未言之罪。",
            "themes": "未说出口的话造成的错位",
            "style_notes": "第一人称限知视角，冷峻白描",
            "highlights": "结尾薄冰意象回收全篇",
            "weaknesses": "中段节奏略拖",
        }

    def stream(self, system, user, temperature=None, max_tokens=None, model=None):
        yield "模拟流式输出"
        yield "。"


def test_parse_and_chunk():
    pipe = Pipeline()
    book = pipe.parse(EPUB)
    assert book.chapter_count == 4, f"章节数异常: {book.chapter_count}"
    assert "薄冰之沼" in book.title
    chunks = chunk_book(book, chunk_size=300, chunk_overlap=50)
    assert len(chunks) >= 2, f"分块数异常: {len(chunks)}"
    print(f"  [OK] 解析 {book.chapter_count} 章，切成 {len(chunks)} 块")


def test_digest_with_cache():
    pipe = Pipeline()
    pipe._llm = FakeLLM()
    book = pipe.parse(EPUB)
    pipe.db.clear_digest(book.file_hash)

    digest, built = pipe.get_or_build_digest(book)
    assert built is True, "首次应新建理解卡"
    assert digest.one_line, "理解卡为空"
    assert not digest.is_empty()

    digest2, built2 = pipe.get_or_build_digest(book)
    assert built2 is False, "第二次应命中缓存"
    assert digest2.one_line == digest.one_line
    print(f"  [OK] 理解卡生成 + 缓存命中（{digest.one_line}）")

    digest3, built3 = pipe.get_or_build_digest(book, force=True)
    assert built3 is True, "force=True 应重算"
    print("  [OK] force 重算生效")


def test_style_learning():
    pipe = Pipeline()
    pipe._llm = FakeLLM()
    samples = [
        "这本书我看到第三十页就想扔了。说白了，作者的野心大于能力。"
        "他想在四百页里塞进三代人的命运，结果每个人物都只剩一副骨架。"
        "值得注意的是，第一章的开篇确实漂亮——那场雪写得克制而锋利，"
        "可惜这种水准没能维持到第二章。",
        "读完最后一个字，我在阳台上站了很久。这不是一本让人舒服的书，"
        "但它诚实。作者拒绝给读者任何廉价的安慰，连结尾那点微光都显得吝啬。"
        "你会失望吗？如果你期待的是一个和解的故事，那肯定会。",
    ]
    stats = compute_stats(samples)
    assert stats["sample_count"] == 2
    assert stats["avg_sentence_len"] > 0
    print(f"  [OK] 统计特征：篇均 {stats['avg_review_chars']} 字，"
          f"句均 {stats['avg_sentence_len']} 字，短句占比 {stats['short_sentence_ratio']}")

    tmp = Path(__file__).parent / "_tmp_samples.txt"
    tmp.write_text("\n\n---\n\n".join(samples), encoding="utf-8")
    pid, profile = pipe.learn_style([tmp], name="测试风格")
    assert pid > 0
    assert profile["tone"]["description"]
    print(f"  [OK] 风格画像已存 id={pid}，语气：{profile['tone']['description']}")

    block = render_style_block(profile)
    assert "我的写作风格" in block and "说白了" in block
    print(f"  [OK] 风格卡渲染 {len(block)} 字，含口头禅与结构")

    got = pipe.get_profile(pid)
    assert got and got["name"] == "测试风格"
    print("  [OK] 画像读回一致")

    tmp.unlink(missing_ok=True)


def test_generate_review():
    pipe = Pipeline()
    fake = FakeLLM()
    pipe._llm = fake
    book = pipe.parse(EPUB)
    digest, _ = pipe.get_or_build_digest(book)
    baseline = len(pipe.db.list_reviews(book.file_hash))
    for length in LENGTH_PRESETS:
        content = pipe.generate_review(book, digest, length_key=length)
        assert content, f"{length} 档生成失败"
    reviews = pipe.db.list_reviews(book.file_hash)
    added = len(reviews) - baseline
    assert added == len(LENGTH_PRESETS), f"书评入库数异常: 新增 {added}"
    print(f"  [OK] 三档长度均生成并入库（本次新增 {added} 篇）")

    streamed = "".join(pipe.stream_review(book, digest))
    assert streamed, "流式生成失败"
    print(f"  [OK] 流式生成可用：{streamed}")

    # 摘要用便宜模型、生成用强模型
    pipe.settings.llm.review_model = "deepseek-v4-pro"
    pipe.generate_review(book, digest, length_key="short")
    assert "deepseek-v4-pro" in fake.models_used, "生成阶段未使用 review_model"
    print(f"  [OK] 双模型分流生效，生成阶段使用 {sorted(fake.models_used)}")


def test_split_samples():
    text = "第一篇内容" * 20 + "\n\n---\n\n" + "第二篇内容" * 20
    parts = split_samples(text)
    assert len(parts) == 2, f"样本切分数异常: {len(parts)}"
    print(f"  [OK] 多篇样本切分：{len(parts)} 篇")


MIXED_SAMPLE = """把下面这篇文章润色下并修改下有语病的地方

最近非帅看"龙泉家族"系列有点上头，先看了《孤岛的来访者》，再看了《时间旅行者的沙漏》，
最后看了这部《献给名侦探的甜美死亡》。说实话，内容一本比一本精彩，诡计一本比一本复杂。
这三部作品的共同点，都是"暴风雪山庄"模式，只不过各自所处的环境不同。
今天非帅要讲的就是这本《献给名侦探的甜美死亡》。

这次是由经历过"死野的惨剧"的加茂冬马和破解了"幽世岛之谜"的龙泉佑树，这两位侦探进行组队探案。
没想到方丈老师也会玩多重诡计，反转反转再反转，玩得那么花，而且玩出了新高度。
说实话，看到这里，非帅觉得方丈贵惠这次作品的设定相当有看头，相当给力。

这是我润色后的版本，在保持原文风格的基础上优化了语句流畅度和逻辑结构：

---

#User : 把下面这篇文章改写成小红书的格式

最近沉迷于"龙泉家族"系列，这个系列最吸引人的地方在于每部作品都采用了经典的暴风雪山庄模式。

#DeepSeek : 💥暴风雪山庄还能这样玩？！这本推理新作绝了！！

姐妹们！！最近挖到宝了！！😍
✨高能剧情预警✨
#推理小说 #暴风雪山庄 #本格推理 #书单推荐

主要修改：
1. 调整了部分冗长表述
2. 理顺了逻辑关系
"""


def test_sanitizer_cuts_ai_content():
    cleaned, notes = sanitize(MIXED_SAMPLE)
    assert "非帅" in cleaned, "净化误删了本人原文"
    assert "龙泉家族" in cleaned
    for banned in ["DeepSeek", "姐妹们", "挖到宝", "主要修改", "润色后的版本"]:
        assert banned not in cleaned, f"AI 内容未被剔除: {banned}"
    assert "#推理小说" not in cleaned, "标签行未被剔除"
    assert "😍" not in cleaned, "emoji 未被剔除"
    assert not INSTRUCTION_PATTERN_HIT(cleaned), "指令首行未被剔除"
    print(f"  [OK] 净化后 {len(cleaned)} 字（原 {len(MIXED_SAMPLE)} 字），"
          f"剔除 {len(notes)} 处")

    batch, _ = sanitize_many([MIXED_SAMPLE])
    assert len(batch) == 1 and "非帅" in batch[0]
    print("  [OK] 批量净化保留有效样本")

    assert looks_ai_generated("#DeepSeek: 💥💥💥 #推理 #悬疑 #好书") is True
    assert looks_ai_generated("这本小说的诡计设计相当精巧，我认为值得一读。") is False
    print("  [OK] AI 腔识别有效")


def INSTRUCTION_PATTERN_HIT(text: str) -> bool:
    return text.strip().startswith("把下面这篇文章润色下")


# 真实样本里出现的四种文件结构，逐一固化为回归用例
VARIANT_A = """#User : 把这篇文章润色下，有语病的地方修改下
从去年12月份开始到昨天，我花了快6个月的时间把一部科幻作品集看完。看完之后，不尤得感叹，
中国女性科幻作家，真的是人才辈出！对，你没看错，是中国女性科幻作家。一般人的认知里，
大部分写科幻小说的作家都是男性作家，例如写过《三体》的刘慈欣，而女性作家只有寥寥几人。

修改版：

从去年12月到昨天，我花了将近六个月的时间，读完了一部科幻作品集。合上书页，不禁感叹：
中国女性科幻作家，真是人才辈出！
"""

VARIANT_B = """最近非帅阅读了E伯爵老师的一部短篇集《四季物语》，我原以为收录的作品可能是我国风格的
民间故事二创，没想到E伯爵老师给出的是日本民间妖怪故事短篇集，还是二创版，满满的日式和风。
这部短篇集一共收录了四部作品，分别是：《露草》、《猫之瞳》、《雪女》、《夕阳剧场》。

公众号：

宝子们，最近我挖到了一本宝藏作品——E伯爵老师的《四季物语》。本以为是一本充满中国风的
民间故事新编，没想到一翻开，扑面而来的竟是浓郁的日式和风。
"""

VARIANT_C = """#### **一、科幻外壳下的伦理寓言：后人类时代的生存图景**

翻开杜梨的《孤山骑士》，我仿佛被拽入一个既熟悉又陌生的近未来世界。这里仿生人已成为
家庭的标配成员，他们拥有人类的情感与忠诚，却依然被视作"机械奴隶"。

#### **二、人机之恋：在代码与灵魂之间**

最让我震撼的，是杜梨对"人机关系"的重新定义。咪貉与菊地的情感超越了主仆、父女、恋人的
界限，成为一种无法被标签化的存在。

各位读过《孤山骑士》的朋友，你们是否也曾为菊地与咪貉的命运揪心？欢迎在评论区分享你的阅读体验！

公众号：

当AI学会哭泣，人类是否还记得如何流泪？
"""


def test_sanitizer_variants():
    # A：#User 指令在文件开头，后面跟的其实是作者原文 —— 只能删行，不能截断
    a, _ = sanitize(VARIANT_A)
    assert "从去年12月份开始到昨天" in a, "指令行后的原文被误截断"
    assert "修改版" not in a, "AI 修改版未被截断"
    assert "不禁感叹" not in a, "AI 修改版正文泄漏"
    print(f"  [OK] 变体A（开头#User+原文）：保留 {len(a)} 字原文")

    # B：渠道版本标记「公众号：」后的内容全部是 AI 改写
    b, _ = sanitize(VARIANT_B)
    assert "最近非帅阅读了E伯爵老师" in b, "本人原文被误删"
    assert "宝子们" not in b, "公众号版本未被截断"
    print(f"  [OK] 变体B（公众号：截断）：保留 {len(b)} 字原文")

    # C：通篇是 AI 洗稿（CTA + 分节标题），截断后仍应整篇丢弃
    c, notes = sanitize(VARIANT_C)
    assert c == "", f"AI 洗稿未被识别，残留 {len(c)} 字"
    assert any("AI 生成" in n for n in notes), "未给出丢弃原因"
    print("  [OK] 变体C（整篇 AI 稿）：判定并丢弃")

    # D：#User 出现在原文之后 —— 后面的都是 AI 产出，必须截断
    d = "最近非帅看这个系列有点上头，" * 20 + "\n#User : 把下面这篇文章改写成小红书格式\n姐妹们！！绝了！！"
    cleaned, _ = sanitize(d)
    assert "小红书" not in cleaned and "姐妹们" not in cleaned, "原文后的 AI 产出未被截断"
    assert "非帅" in cleaned, "原文被误删"
    print(f"  [OK] 变体D（原文后#User=AI产出）：保留 {len(cleaned)} 字原文")


def test_detect_self_name():
    assert detect_self_name(MIXED_SAMPLE) == "非帅", "未能识别自称"
    print("  [OK] 识别自称：非帅")

    for t in ["我觉得这本书很好，作者写得不错。我看了三遍。",
              "这本书我觉得一般，故事还算完整，人物塑造有待加强。"]:
        assert detect_self_name(t) == "", f"误报自称: {t[:15]}"
    print("  [OK] 无自称文本不误报")


def test_style_words_vs_content_words():
    """风格词与内容词必须分离：不能把'侦探''诡计'当成文风。"""
    samples = [MIXED_SAMPLE.split("这是我润色后的版本")[0]]
    stats = compute_stats(samples)
    content = stats["content_words"]
    markers = stats["style_markers"]
    assert "说实话" in markers or "相当" in markers, f"未提取到风格词: {markers}"
    for w in list(markers)[:5]:
        assert w not in ("诡计", "侦探", "杀人", "实施"), f"内容词混入风格词: {w}"
    assert stats["self_name"] == "非帅"
    print(f"  [OK] 风格词 {list(markers)[:5]} 与内容词 {content[:5]} 已分离")


def test_prompt_quality_guards():
    from bookreview.core.prompts import (
        REVIEW_SYSTEM, render_persona_line, render_spoiler_rule,
    )
    profile = {
        "persona": {"self_name": "非帅", "identity": "本格推理爱好者"},
        "spoiler_policy": "full",
    }
    sys_text = REVIEW_SYSTEM.format(
        persona_line=render_persona_line(profile, "你"),
        title="测试书",
        style_block="风格",
        spoiler_rule=render_spoiler_rule(profile),
    )
    assert "非帅" in sys_text, "自称未注入人设"
    for banned in ["内容简介", "本书讲述了", "作为AI"]:
        assert banned in sys_text, f"禁忌条目缺失: {banned}"
    print("  [OK] 生成提示词包含全部禁忌约束")

    for k in LENGTH_PRESETS:
        assert LENGTH_PRESETS[k]["max_tokens"] > 0
    for k in FOCUS_PRESETS:
        assert FOCUS_PRESETS[k]
    print(f"  [OK] 长度档 {len(LENGTH_PRESETS)} 种 / 侧重 {len(FOCUS_PRESETS)} 种")


def main():
    tests = [
        test_parse_and_chunk,
        test_digest_with_cache,
        test_style_learning,
        test_generate_review,
        test_split_samples,
        test_sanitizer_cuts_ai_content,
        test_sanitizer_variants,
        test_detect_self_name,
        test_style_words_vs_content_words,
        test_prompt_quality_guards,
    ]
    failed = 0
    for t in tests:
        print(f"\n▶ {t.__name__}")
        try:
            t()
        except AssertionError as e:
            failed += 1
            print(f"  [FAIL] {e}")
        except Exception as e:
            failed += 1
            print(f"  [ERROR] {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
    print("\n" + "=" * 55)
    print(f"总计 {len(tests)} 项，失败 {failed} 项")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
