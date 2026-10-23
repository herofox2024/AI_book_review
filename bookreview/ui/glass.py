"""Windows 窗口材质：亚克力 / Mica 背景、深色标题栏、圆角。

Windows 11（build >= 22000）用 ``DwmSetWindowAttribute`` 就能拿到系统级毛玻璃，
不需要任何 hook。其他系统或调用失败时静默降级，由主题层退回不透明底色。

注意：所有函数都必须容错 —— 这里是 UI 装饰层，没有任何理由让它把应用带崩。
"""

from __future__ import annotations

import ctypes
import sys

# DwmSetWindowAttribute 的属性号（Windows 11 SDK）
DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWA_SYSTEMBACKDROP_TYPE = 38

# 背景材质
DWMSBT_AUTO = 0
DWMSBT_NONE = 1
DWMSBT_MAINWINDOW = 2        # Mica：跟随桌面壁纸着色
DWMSBT_TRANSIENTWINDOW = 3   # Acrylic：更强的模糊，适合「水晶」质感
DWMSBT_TABBEDWINDOW = 4

# 窗口圆角
DWMWCP_DEFAULT = 0
DWMWCP_DONOTROUND = 1
DWMWCP_ROUND = 2
DWMWCP_ROUNDSMALL = 3

_BACKDROPS = {
    "none": DWMSBT_NONE,
    "mica": DWMSBT_MAINWINDOW,
    "acrylic": DWMSBT_TRANSIENTWINDOW,
    "tabbed": DWMSBT_TABBEDWINDOW,
}


def windows_build() -> int:
    if sys.platform != "win32":
        return 0
    try:
        return int(sys.getwindowsversion().build)
    except Exception:
        return 0


def is_supported() -> bool:
    """是否支持系统毛玻璃（Windows 11 起步）。"""
    return sys.platform == "win32" and windows_build() >= 22000


def _dwm():
    if sys.platform != "win32":
        return None
    try:
        return ctypes.WinDLL("dwmapi")
    except OSError:
        return None


def _set_attr(hwnd: int, attr: int, value: int) -> bool:
    dwm = _dwm()
    if dwm is None or not hwnd:
        return False
    try:
        value_ref = ctypes.c_int(value)
        hr = dwm.DwmSetWindowAttribute(
            ctypes.c_void_p(hwnd),
            ctypes.c_uint(attr),
            ctypes.byref(value_ref),
            ctypes.sizeof(value_ref),
        )
        return hr == 0
    except Exception:
        return False


def apply(win, dark: bool = False, backdrop: str = "acrylic") -> dict:
    """给顶层窗口套上材质，返回各项结果（便于日志与排查）。

    win 必须已经创建原生窗口（``win.winId()`` 非零），通常在 showEvent 里调用。
    """
    if not is_supported():
        return {"supported": False}

    result: dict = {"supported": True}
    try:
        hwnd = int(win.winId())
    except Exception:
        return {"supported": True, "hwnd": False}

    result["backdrop"] = _set_attr(
        hwnd, DWMWA_SYSTEMBACKDROP_TYPE, _BACKDROPS.get(backdrop, DWMSBT_TRANSIENTWINDOW)
    )
    result["dark_titlebar"] = _set_attr(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, 1 if dark else 0)
    result["rounded"] = _set_attr(hwnd, DWMWA_WINDOW_CORNER_PREFERENCE, DWMWCP_ROUND)
    return result


def apply_titlebar_only(win, dark: bool = False) -> dict:
    """只改标题栏深浅与圆角（不透明主题用），保持系统默认背景。"""
    if not is_supported():
        return {"supported": False}
    try:
        hwnd = int(win.winId())
    except Exception:
        return {"supported": True, "hwnd": False}
    return {
        "supported": True,
        "dark_titlebar": _set_attr(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, 1 if dark else 0),
        "rounded": _set_attr(hwnd, DWMWA_WINDOW_CORNER_PREFERENCE, DWMWCP_ROUND),
        "backdrop": _set_attr(hwnd, DWMWA_SYSTEMBACKDROP_TYPE, DWMSBT_NONE),
    }
