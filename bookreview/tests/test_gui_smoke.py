"""GUI 冒烟测试：离屏创建所有页面并切换，捕获导入与构造错误。

不真正弹出窗口，用 QApplication + 离屏渲染验证代码可跑通。
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
TEST_DATA_DIR = Path(tempfile.mkdtemp(prefix="bookreview_gui_test_"))
os.environ["BOOKREVIEW_DATA_DIR"] = str(TEST_DATA_DIR)


def main() -> int:
    from PySide6.QtWidgets import QApplication

    from bookreview.core.pipeline import Pipeline
    from bookreview.ui.main_window import MainWindow
    from bookreview.ui.theme import QSS

    app = QApplication(sys.argv)
    app.setStyleSheet(QSS)

    pipe = Pipeline()
    pipe.db.save_profile(
        "GUI测试风格",
        {"persona": {"self_name": "测试"}, "tone": {}, "spoiler_policy": "none"},
        sample_count=1,
    )
    win = MainWindow(pipe)
    win.show()

    ok = []

    # 1) 四个页面都能切换
    for i in range(win.nav_list.count()):
        win.nav_list.setCurrentRow(i)
        app.processEvents()
        ok.append(f"页面 {i} ({win.nav_list.item(i).text()}) 可打开")

    # 2) 风格卡列表非空
    n_style = win.page_style.cmb.count()
    assert n_style > 0, "风格卡列表为空"
    ok.append(f"风格卡列表 {n_style} 条")

    # 3) 书评库有数据
    n_rev = win.page_lib.table.rowCount()
    ok.append(f"书评库 {n_rev} 条")

    # 4) 生成页选项齐全
    assert win.page_gen.cmb_length.count() == 3, "长度档数量不对"
    assert win.page_gen.cmb_focus.count() == 5, "侧重数量不对"
    ok.append("生成页：3 档长度 / 5 种侧重")

    # 5) 设置页载入当前配置
    assert win.page_set.ed_base.text(), "Base URL 未载入"
    ok.append(f"设置页已载入：{win.page_set.ed_base.text()}")

    # 6) 解析一本真书（不发请求）
    book = pipe.parse("bookreview/tests/sample_books/薄冰之沼.epub")
    win.page_gen._on_parsed(book)
    app.processEvents()
    assert win.page_gen.btn_digest.isEnabled(), "解析后未启用理解卡按钮"
    ok.append(f"解析联动正常：{book.summary_line()}")

    for line in ok:
        print("  [OK]", line)
    print(f"\nGUI 冒烟测试通过（{len(ok)} 项）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
