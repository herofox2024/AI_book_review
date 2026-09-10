"""GUI 入口：python -m bookreview.gui"""

from __future__ import annotations

import sys


def main() -> int:
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        print("缺少 PySide6，请先安装：pip install PySide6")
        return 1

    # 用绝对导入：`python -m bookreview.gui` 时相对导入会越过顶层包
    from bookreview.core.pipeline import Pipeline
    from bookreview.ui.main_window import MainWindow
    from bookreview.ui.theme import QSS

    app = QApplication(sys.argv)
    app.setStyleSheet(QSS)
    win = MainWindow(Pipeline())
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
