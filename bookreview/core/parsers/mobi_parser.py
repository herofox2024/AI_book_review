"""MOBI / AZW3 解析：mobi 解包优先，Calibre 转换降级，DRM 明确报错。"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from bs4 import BeautifulSoup

from .base import BaseParser, ParseError
from ..models import Book

CALIBRE_CANDIDATES = [
    "ebook-convert",
    "ebook-convert.exe",
    r"C:\Program Files\Calibre2\ebook-convert.exe",
    r"C:\Program Files (x86)\Calibre2\ebook-convert.exe",
    r"C:\Program Files\Calibre\ebook-convert.exe",
]

META_CANDIDATES = [
    "ebook-meta",
    "ebook-meta.exe",
    r"C:\Program Files\Calibre2\ebook-meta.exe",
    r"C:\Program Files (x86)\Calibre2\ebook-meta.exe",
    r"C:\Program Files\Calibre\ebook-meta.exe",
]


def find_tool(candidates: list[str]) -> str | None:
    for c in candidates:
        if os.path.isabs(c):
            if Path(c).exists():
                return c
            continue
        found = shutil.which(c)
        if found:
            return found
    return None


def natural_key(name: str):
    return [int(s) if s.isdigit() else s.lower() for s in re.split(r"(\d+)", name)]


class MobiParser(BaseParser):
    formats = (".mobi", ".azw3", ".azw", ".prc")

    def parse(self, path: Path) -> Book:
        fmt = path.suffix.lower().lstrip(".")
        title, author, language = self._read_meta(path)

        # 路径 1：mobi 库解包
        blocks: list[tuple[str, str]] = []
        err1 = ""
        try:
            blocks = self._extract_with_mobi_lib(path)
        except ImportError as e:
            err1 = f"mobi 库未安装: {e}"
        except Exception as e:
            err1 = f"mobi 解包失败: {type(e).__name__}: {e}"

        # 路径 2：Calibre 转换
        if not blocks:
            blocks = self._convert_with_calibre(path)

        if not blocks:
            raise ParseError(
                f"无法解析 {fmt.upper()} 文件。\n"
                f"· 主路径失败：{err1 or '无'}\n"
                f"· 降级路径失败：未找到可用的 Calibre（ebook-convert）\n"
                f"若文件带 DRM 版权保护，任何工具都无法提取正文，请先去除 DRM。\n"
                f"建议：安装 Calibre 后重试，或手动转换为 EPUB 再导入。"
            )

        if not title:
            title = path.stem
        return self.build_book(path, title, author, fmt, blocks, language=language)

    # ---------- 路径 1 ----------
    def _extract_with_mobi_lib(self, path: Path) -> list[tuple[str, str]]:
        import mobi  # 延迟导入，缺失时不影响其他格式

        tmp_dir, _main_file = mobi.extract(str(path))
        tmp_path = Path(tmp_dir)
        try:
            # KF8 解包后可能直接带 epub
            epubs = sorted(tmp_path.rglob("*.epub"))
            if epubs:
                from .epub_parser import EpubParser
                b = EpubParser().parse(epubs[0])
                return [(c.title, c.text) for c in b.chapters]

            htmls = [p for p in tmp_path.rglob("*")
                     if p.suffix.lower() in (".html", ".xhtml", ".htm")]
            htmls.sort(key=lambda p: natural_key(str(p.relative_to(tmp_path))))

            blocks: list[tuple[str, str]] = []
            for hf in htmls:
                try:
                    raw = hf.read_bytes()
                except Exception:
                    continue
                soup = BeautifulSoup(raw, "html.parser")
                for tag in soup(["script", "style", "nav"]):
                    tag.decompose()
                heading = ""
                for tag_name in ("h1", "h2", "h3", "title"):
                    h = soup.find(tag_name)
                    if h and h.get_text(strip=True):
                        cand = h.get_text(strip=True)
                        if len(cand) <= 60:
                            heading = cand
                            break
                body = soup.get_text("\n")
                if body.strip():
                    blocks.append((heading, body))
            return blocks
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    # ---------- 路径 2 ----------
    def _convert_with_calibre(self, path: Path) -> list[tuple[str, str]]:
        tool = find_tool(CALIBRE_CANDIDATES)
        if not tool:
            return []
        tmp_dir = Path(tempfile.mkdtemp(prefix="br_calibre_"))
        out_epub = tmp_dir / "converted.epub"
        try:
            proc = subprocess.run(
                [tool, str(path), str(out_epub)],
                capture_output=True, text=True, timeout=300,
                encoding="utf-8", errors="ignore",
            )
            if proc.returncode != 0 or not out_epub.exists():
                # 再退一步：转成 txt
                out_txt = tmp_dir / "converted.txt"
                proc2 = subprocess.run(
                    [tool, str(path), str(out_txt)],
                    capture_output=True, text=True, timeout=300,
                    encoding="utf-8", errors="ignore",
                )
                if proc2.returncode == 0 and out_txt.exists():
                    text = out_txt.read_text(encoding="utf-8", errors="ignore")
                    return self.fallback_split(text)
                return []
            from .epub_parser import EpubParser
            b = EpubParser().parse(out_epub)
            return [(c.title, c.text) for c in b.chapters]
        except Exception:
            return []
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    # ---------- 元数据 ----------
    def _read_meta(self, path: Path) -> tuple[str, str, str]:
        tool = find_tool(META_CANDIDATES)
        if not tool:
            return "", "", ""
        try:
            proc = subprocess.run(
                [tool, str(path)], capture_output=True, text=True,
                timeout=30, encoding="utf-8", errors="ignore",
            )
            title = author = ""
            for line in proc.stdout.splitlines():
                if ":" not in line:
                    continue
                k, _, v = line.partition(":")
                k, v = k.strip().lower(), v.strip()
                if k == "title" and not title:
                    title = v
                elif k in ("author(s)", "author") and not author:
                    author = v.split("&")[0].split(",")[0].strip()
                    if "," in v:
                        parts = [x.strip() for x in v.split(",")]
                        if len(parts) >= 2:
                            author = f"{parts[1]} {parts[0]}"
            return title, author, ""
        except Exception:
            return "", "", ""
