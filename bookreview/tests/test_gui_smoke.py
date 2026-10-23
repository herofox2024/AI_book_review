"""GUI 冒烟测试：离屏创建所有页面并切换，捕获导入与构造错误。

既是 pytest 用例（`test_gui_smoke`），也能直接跑：
    python bookreview/tests/test_gui_smoke.py

不真正弹出窗口，用 QApplication + 离屏渲染验证代码可跑通。
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
TEST_DATA_DIR = Path(tempfile.mkdtemp(prefix="bookreview_gui_test_"))
os.environ["BOOKREVIEW_DATA_DIR"] = str(TEST_DATA_DIR)

SAMPLE_EPUB = Path(__file__).parent / "sample_books" / "薄冰之沼.epub"

_app = None


def _get_app():
    """整个进程只能有一个 QApplication，重复创建会直接 abort。"""
    global _app
    from PySide6.QtWidgets import QApplication

    if _app is None:
        _app = QApplication.instance() or QApplication(sys.argv[:1])
        from bookreview.ui.theme import QSS

        _app.setStyleSheet(QSS)
    return _app


def test_gui_smoke() -> None:
    app = _get_app()

    from bookreview.core.pipeline import Pipeline
    from bookreview.ui.main_window import MainWindow
    from bookreview.ui.pages import generate_page

    pipe = Pipeline()
    pipe.db.save_profile(
        "GUI测试风格",
        {"persona": {"self_name": "测试"}, "tone": {}, "spoiler_policy": "none"},
        sample_count=1,
    )
    win = MainWindow(pipe)
    win.show()
    try:
        # 1) 四个页面都能切换，且 stack 跟着走
        for i in range(win.nav_list.count()):
            win.nav_list.setCurrentRow(i)
            app.processEvents()
            assert win.stack.currentIndex() == i, f"切换到页面 {i} 失败"

        # 2) 风格卡列表非空
        assert win.page_style.cmb.count() > 0, "风格卡列表为空"

        # 3) 生成页选项齐全
        assert win.page_gen.cmb_length.count() == 3, "长度档数量不对"
        assert win.page_gen.cmb_focus.count() == 5, "侧重数量不对"

        # 4) 设置页载入当前配置
        assert win.page_set.ed_base.text(), "Base URL 未载入"

        # 5) 拖放与文件过滤器（回归：acceptDrops 没开时拖放完全失效）
        assert win.page_gen.acceptDrops(), "生成页未开启 acceptDrops，拖放会失效"
        assert ".txt" not in generate_page.FILE_FILTER, "文件过滤器列了解析器不支持的格式"

        # 6) 解析一本真书（不发请求），联动启用理解卡按钮
        book = pipe.parse(SAMPLE_EPUB)
        win.page_gen._on_parsed(book)
        app.processEvents()
        assert win.page_gen.btn_digest.isEnabled(), "解析后未启用理解卡按钮"
    finally:
        win.close()


def main() -> int:
    test_gui_smoke()
    print("GUI 冒烟测试通过（6 项）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
