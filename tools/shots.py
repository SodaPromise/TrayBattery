"""生成 README 用的截图：把电量条放到真实任务栏上抓图。

用法：python tools/shots.py
只写临时目录里的配置，不动用户自己的设置；截完自动退出。
"""
from __future__ import annotations

import ctypes
import os
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

OUT = os.path.join(ROOT, "assets")
TMP = tempfile.mkdtemp(prefix="traybattery-shots-")
os.environ["APPDATA"] = TMP

from app import startup  # noqa: E402
from app import win32 as k  # noqa: E402
from app.main import App  # noqa: E402

startup.sync = lambda config: None

try:
    ctypes.windll.shcore.SetProcessDpiAwarenessContext(-4)
except Exception:
    pass


def pump(ms: int) -> None:
    msg = k.MSG()
    end = time.time() + ms / 1000.0
    while time.time() < end:
        while k.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):
            k.TranslateMessage(ctypes.byref(msg))
            k.DispatchMessageW(ctypes.byref(msg))
        time.sleep(0.01)


def grab(box, path: str) -> None:
    from PIL import ImageGrab

    x0, y0, x1, y1 = (int(round(v)) for v in box)
    ImageGrab.grab(bbox=(x0, y0, x1, y1), all_screens=True).save(path)
    print(f"  -> {path}  {(x1 - x0)}×{(y1 - y0)}")


def grab_window(win, path: str, pad: int = 16) -> None:
    """抓整个窗口，四周留一圈给阴影落下去。"""
    x, y = win.pos
    grab((x - pad, y - pad, x + win.w + pad, y + win.h + pad), path)


def main() -> int:
    app = App(demo=True)
    try:
        end = time.time() + 8
        while time.time() < end and not app.display_devices():
            pump(60)
        bar = app.bar_window
        if bar is None or not bar.visible:
            print("电量条没有出现，先打开 --demo 再试")
            return 1
        pump(500)

        tray = k.taskbar_rect()
        tn = k.tray_area_rect()
        # 抓电量条 + 一段任务栏 + 托盘区，才有"原生"的语境
        left = max(tray.left, bar.pos[0] - int(round(150 * app.scale)))
        right = min(tray.right, (tn.left if tn else bar.pos[0] + bar.w) + int(round(120 * app.scale)))
        box = (left, tray.top, right, tray.bottom)

        grab(box, os.path.join(OUT, "screenshot-bar-dark.png"))

        bar.hover = "bar"
        bar.invalidate()
        pump(200)
        grab(box, os.path.join(OUT, "screenshot-bar-hover.png"))

        # 面板与设置页：趁只有一台设备时抓，标题和内容都清爽
        bar.hover = None
        bar.invalidate()
        app.toggle_flyout_near_bar(bar)
        pump(420)
        grab_window(app.flyout_window, os.path.join(OUT, "screenshot-flyout-dark.png"))
        app.flyout_window.hide()
        pump(160)

        app.open_settings()
        pump(600)
        grab_window(app.settings_window, os.path.join(OUT, "screenshot-settings-dark.png"))
        app.settings_window.hide()
        pump(160)

        # 两台设备的样子
        keys = [d.key for d in app.state.devices[:2]]
        for key in keys:
            app.config.set_enabled(key, True)
        app.update_bar()
        pump(300)
        grab(box, os.path.join(OUT, "screenshot-bar-multi.png"))
        return 0
    finally:
        app.quit()
        pump(200)


if __name__ == "__main__":
    sys.exit(main())
