"""命令行入口：解析 / 理解卡 / 风格学习 / 生成书评。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .core.config import PRESETS, load_settings
from .core.pipeline import Pipeline
from .core.prompts import FOCUS_PRESETS, LENGTH_PRESETS

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def cmd_ping(args, pipe: Pipeline) -> int:
    ok, msg = pipe.llm.ping()
    print(f"模型: {pipe.settings.llm.model} @ {pipe.settings.llm.base_url}")
    print(("连接正常，回复: " + msg) if ok else ("连接失败: " + msg))
    return 0 if ok else 1


def cmd_config(args, pipe: Pipeline) -> int:
    # switch 子命令只有 provider，其余字段用 getattr 安全读取
    s = pipe.settings
    if getattr(args, "provider", None):
        s.apply_preset(args.provider)
    if getattr(args, "base_url", None):
        s.llm.base_url = args.base_url
    if getattr(args, "model", None):
        s.llm.model = args.model
    if getattr(args, "review_model", None) is not None:
        s.llm.review_model = args.review_model
    if getattr(args, "key", None):
        s.llm.api_key = args.key
    if getattr(args, "concurrency", None):
        s.pipeline.concurrency = args.concurrency
    s.save()
    print("配置已保存:")
    print(f"  服务商      : {s.llm.provider}  (可选: {', '.join(PRESETS)})")
    print(f"  接口地址    : {s.llm.base_url}")
    print(f"  模型        : {s.llm.model}  (分块摘要用)")
    print(f"  生成专用模型: {s.llm.review_model or '(同上)'}")
    print(f"  API Key     : {'已设置 (' + str(len(s.llm.api_key)) + ' 位)' if s.llm.api_key else '未设置'}")
    print(f"  摘要并发数  : {s.pipeline.concurrency}")
    return 0


def cmd_parse(args, pipe: Pipeline) -> int:
    book = pipe.parse(args.file)
    print(book.summary_line())
    print(f"  文件哈希: {book.file_hash}")
    if args.chapters:
        for c in book.chapters[: args.chapters]:
            print(f"  [{c.index:>3}] {c.title or '(无标题)'} — {c.char_count:,} 字")
    if args.dump:
        Path(args.dump).write_text(book.full_text, encoding="utf-8")
        print(f"  正文已导出: {args.dump}")
    return 0


def cmd_digest(args, pipe: Pipeline) -> int:
    book = pipe.parse(args.file)
    print(book.summary_line())
    digest, built = pipe.get_or_build_digest(book, force=args.force)
    print("（新建）" if built else "（命中缓存）")
    print("-" * 60)
    print(digest.to_prompt_block())
    return 0


def cmd_style(args, pipe: Pipeline) -> int:
    pid, profile = pipe.learn_style(args.files, name=args.name, hint=args.hint or "")
    print(f"风格画像已保存: id={pid} 名称={args.name} 样本数={profile.get('_stats', {}).get('sample_count', '?')}")
    print("-" * 60)
    stats = profile.get("_stats", {})
    if stats:
        print(f"平均篇幅 {stats.get('avg_review_chars')} 字 | 平均句长 {stats.get('avg_sentence_len')} 字"
              f" | 短句占比 {stats.get('short_sentence_ratio')}")
    print(f"语气: {profile.get('tone', {}).get('description', '')}")
    print(f"结构: {' → '.join(str(x) for x in profile.get('structure', []))}")
    print(f"口头禅: {'、'.join(str(x) for x in profile.get('signature_phrases', [])[:8])}")
    return 0


def cmd_import_profile(args, pipe: Pipeline) -> int:
    import json
    data = json.loads(Path(args.file).read_text(encoding="utf-8"))
    name = args.name or data.get("name") or Path(args.file).stem

    # 没指定 id 时，若已存在同名卡片则覆盖它，避免列表越堆越长
    target = args.id
    if target is None and not args.as_new:
        row = pipe.db.find_profile_by_name(name)
        if row:
            target = row["id"]
            print(f"检测到同名风格卡 #{target}，将覆盖它（加 --as-new 可强制新建）")

    pid = pipe.db.save_profile(
        name, data, sample_count=data.get("_stats", {}).get("sample_count", 0),
        profile_id=target,
    )
    print(f"已{'更新' if target else '导入'}风格画像: id={pid}  名称={name}")
    persona = data.get("persona") or {}
    if persona.get("self_name"):
        print(f"  自称: {persona['self_name']}")
    print(f"  类型: {data.get('genre_focus', '未指定')}")
    print(f"  剧透: {data.get('spoiler_policy', '未指定')}")
    return 0


def cmd_profiles(args, pipe: Pipeline) -> int:
    if args.clean:
        plan = pipe.db.plan_dedupe_profiles()
        if not plan:
            print("没有发现重复风格画像。")
            return 0
        remove_count = sum(len(group["remove"]) for group in plan)
        for group in plan:
            print(f"  保留 #{group['keep']}，删除: " + ", ".join(
                f"#{item['id']} {item['name']}" for item in group["remove"]
            ))
        if not args.yes:
            answer = input(f"确认删除 {remove_count} 张重复风格画像？[y/N] ").strip().lower()
            if answer not in {"y", "yes"}:
                print("已取消。")
                return 0
        deleted = pipe.db.apply_dedupe_profiles(plan)
        print(f"已清理 {deleted} 张重复风格画像。")
        return 0
    rows = pipe.list_profiles()
    if not rows:
        print("还没有风格画像。用 `style` 命令创建。")
        return 0
    for r in rows:
        print(f"  id={r['id']}  {r['name']}  (样本 {r['sample_count']} 篇)")
    return 0


def cmd_review(args, pipe: Pipeline) -> int:
    book = pipe.parse(args.file)
    print(book.summary_line())
    digest, built = pipe.get_or_build_digest(book, force=args.force)
    print("理解卡: " + ("已生成" if built else "命中缓存"))
    content = pipe.generate_review(
        book, digest,
        profile_id=args.profile,
        length_key=args.length,
        focus_key=args.focus,
        author_name=args.author,
    )
    print("=" * 60)
    print(content)
    print("=" * 60)
    if args.out:
        Path(args.out).write_text(content, encoding="utf-8")
        print(f"已保存: {args.out}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="bookreview", description="个人风格书评生成器（内核 CLI）"
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("ping", help="测试模型连通性").set_defaults(func=cmd_ping)

    c = sub.add_parser("config", help="查看/修改配置")
    c.add_argument("--provider", choices=list(PRESETS), help="切换服务商预设")
    c.add_argument("--base-url", help="自定义接口地址")
    c.add_argument("--model", help="模型名（用于分块摘要）")
    c.add_argument("--review-model", help="生成书评专用模型，留空则复用 --model")
    c.add_argument("--key", help="API Key")
    c.add_argument("--concurrency", type=int, help="摘要并发数")
    c.set_defaults(func=cmd_config)

    sp = sub.add_parser("switch", help="仅切换服务商，保留已填的 Key")
    sp.add_argument("provider", choices=list(PRESETS))
    sp.add_argument("--review-model", help="生成书评专用模型")
    sp.set_defaults(func=cmd_config)

    pa = sub.add_parser("parse", help="解析电子书并打印信息")
    pa.add_argument("file")
    pa.add_argument("--chapters", type=int, default=8, help="打印前 N 章")
    pa.add_argument("--dump", help="导出纯文本到文件")
    pa.set_defaults(func=cmd_parse)

    d = sub.add_parser("digest", help="生成全书理解卡")
    d.add_argument("file")
    d.add_argument("--force", action="store_true", help="忽略缓存重算")
    d.set_defaults(func=cmd_digest)

    s = sub.add_parser("style", help="从书评样本学习风格")
    s.add_argument("files", nargs="+", help="样本文件 txt/md/docx，多篇用 --- 分隔")
    s.add_argument("--name", default="我的风格")
    s.add_argument("--hint", help="对自己风格的补充描述")
    s.set_defaults(func=cmd_style)

    ip = sub.add_parser("import-profile", help="导入风格画像 JSON")
    ip.add_argument("file")
    ip.add_argument("--name")
    ip.add_argument("--id", type=int, help="覆盖指定 id 的卡片")
    ip.add_argument("--as-new", action="store_true", help="强制新建，不覆盖同名卡片")
    ip.set_defaults(func=cmd_import_profile)

    pc = sub.add_parser("profiles", help="列出风格画像")
    pc.add_argument("--clean", action="store_true", help="清理重复卡片（同名只留最新）")
    pc.add_argument("--yes", action="store_true", help="清理时不再确认")
    pc.set_defaults(func=cmd_profiles)

    r = sub.add_parser("review", help="生成书评")
    r.add_argument("file")
    r.add_argument("--profile", type=int, help="风格画像 id")
    r.add_argument("--length", choices=list(LENGTH_PRESETS), default="standard")
    r.add_argument("--focus", choices=list(FOCUS_PRESETS), default="general")
    r.add_argument("--author", default="", help="你的名字；若不填，自动使用风格卡中的自称")
    r.add_argument("--force", action="store_true", help="忽略理解卡缓存")
    r.add_argument("--out", help="输出到文件")
    r.set_defaults(func=cmd_review)

    sub.add_parser("gui", help="启动图形界面").set_defaults(func=cmd_gui)

    return p


def cmd_gui(args, pipe: Pipeline) -> int:
    from .gui import main as gui_main
    return gui_main()


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = load_settings()
    pipe = Pipeline(settings)
    try:
        return args.func(args, pipe)
    except RuntimeError as e:
        print(f"错误: {e}", file=sys.stderr)
        return 1
    finally:
        pipe.close()


if __name__ == "__main__":
    raise SystemExit(main())
