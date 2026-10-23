"""渲染三套主题的效果图（离屏），用于设计评审。

毛玻璃用系统亚克力提供，离屏渲染拿不到 DWM 合成结果，
所以这里把 glass.apply 打桩成成功，再把窗口贴到一张模拟壁纸上，
比直接看透明 PNG 更接近真实观感。

重要：一次进程只渲染一张图。
在同一个 QApplication 内反复创建 MainWindow 并不会释放旧窗口
（Qt 的窗口在 close() 后仍然存活，全局样式表又会遍历所有已存在控件），
实测第 4 轮构建耗时从 2s 涨到 27s。所以外部按 (主题, 页面) 逐次调用本脚本。
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

_preset = os.environ.get("BOOKREVIEW_DATA_DIR", "").strip()
DATA = Path(_preset) if _preset else Path(tempfile.mkdtemp(prefix="ui_preview_"))
os.environ["BOOKREVIEW_DATA_DIR"] = str(DATA)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPointF, Qt  # noqa: E402
from PySide6.QtGui import (  # noqa: E402
    QColor, QImage, QLinearGradient, QPainter, QRadialGradient,
)
from PySide6.QtWidgets import QApplication  # noqa: E402

import bookreview.ui.glass as glass_mod  # noqa: E402
import bookreview.ui.motion as motion_mod  # noqa: E402

# 让「透明水晶」在离屏环境下也走薄水膜分支
glass_mod.apply = lambda win, dark=False, backdrop="acrylic": {
    "supported": True, "backdrop": True, "dark_titlebar": True, "rounded": True,
}
glass_mod.apply_titlebar_only = lambda win, dark=False: {"supported": True}
# 截图时不要淡入动画，否则会抓到半透明的一帧
motion_mod.fade_in = lambda *args, **kwargs: None

from bookreview.core.pipeline import Pipeline  # noqa: E402
from bookreview.ui.main_window import MainWindow  # noqa: E402

OUT = Path(os.environ.get("PREVIEW_OUT", "").strip() or (ROOT / "outputs"))

PAGES = {0: "generate", 1: "library", 2: "style", 3: "settings"}


def seed(pipe: Pipeline) -> None:
    """塞一点真实感数据，让列表和卡片看起来不是空的。"""
    pipe.db.save_profile(
        "非帅·推理向",
        {
            "persona": {"self_name": "非帅", "identity": "本格推理爱好者"},
            "genre_focus": "本格推理 / 社会派",
            "spoiler_policy": "blur",
            "structure": ["开篇给态度", "用细节论证", "指出短板", "阅读建议"],
            "signature_phrases": ["说实话", "没想到", "相当"],
            "tone": {"description": "真诚犀利，不捧杀"},
        },
        sample_count=3,
    )
    for title, length in (
        ("十诫", "standard"),
        ("十字杀手", "deep"),
        ("性压抑时代的密室消失", "short"),
    ):
        pipe.db.save_review(
            f"hash-{title}", title, None, length, "general",
            f"《{title}》这篇书评的正文示例。说实话，这一本的诡计密度相当高，"
            "但真正打动我的不是手法的精巧，而是作者对沉默的处理方式。"
            "如果你在期待一个爽快的解谜，可能会有点失望。",
        )


def wallpaper(width: int, height: int) -> QImage:
    """模拟一张深色渐变壁纸。"""
    img = QImage(width, height, QImage.Format_ARGB32)
    img.fill(QColor("#0B1E2D"))

    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)

    base = QLinearGradient(0, 0, width, height)
    base.setColorAt(0.0, QColor("#0C2340"))
    base.setColorAt(0.45, QColor("#123A5B"))
    base.setColorAt(0.75, QColor("#2B4C6F"))
    base.setColorAt(1.0, QColor("#4A3B66"))
    p.fillRect(0, 0, width, height, base)

    for cx, cy, radius, color in (
        (0.18, 0.22, 0.55, QColor(90, 200, 255, 120)),
        (0.82, 0.30, 0.48, QColor(160, 120, 255, 110)),
        (0.55, 0.88, 0.60, QColor(255, 150, 120, 90)),
    ):
        g = QRadialGradient(QPointF(cx * width, cy * height), radius * min(width, height))
        g.setColorAt(0.0, color)
        g.setColorAt(1.0, QColor(color.red(), color.green(), color.blue(), 0))
        p.fillRect(0, 0, width, height, g)
    p.end()
    return img


def render_one(theme_key: str, page: int, out_dir: Path,
               width: int = 1120, height: int = 740) -> Path:
    """渲染单张效果图并返回路径。调用方负责本进程只调用一次。"""
    app = QApplication.instance() or QApplication(sys.argv)
    pipe = Pipeline()
    seed(pipe)

    win = MainWindow(pipe)
    win.resize(width, height)
    win.apply_theme(theme_key)
    win.show()
    win.nav_list.setCurrentRow(page)
    app.processEvents()
    for _ in range(4):
        app.processEvents()

    shot = win.grab().toImage()
    canvas = wallpaper(width + 160, height + 160)
    p = QPainter(canvas)
    p.drawImage(80, 80, shot)
    p.end()

    out_dir.mkdir(parents=True, exist_ok=True)
    suffix = PAGES.get(page, "generate")
    path = out_dir / f"preview_{theme_key}_{suffix}.png"
    path.unlink(missing_ok=True)
    ok = canvas.save(str(path))
    pipe.close()
    if not ok:
        raise RuntimeError(f"保存失败: {path}")
    return path


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if len(argv) >= 2:
        theme_key, page = argv[0], int(argv[1])
    else:
        theme_key, page = "crystal", 0
    path = render_one(theme_key, page, OUT)
    print(f"saved {path.name}  theme={theme_key}  page={PAGES.get(page)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
