"""功能冒烟测试：用演示数据启动完整应用，逐项操作托盘、面板、电量条与设置。

用法：python tools/smoke.py
只操作临时配置目录，不读写注册表，不影响正在运行的实例。
"""
from __future__ import annotations

import ctypes
import os
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# 配置与日志写到临时目录，避免动到用户真实设置
TMP = tempfile.mkdtemp(prefix="traybattery-smoke-")
os.environ["APPDATA"] = TMP

from app import startup  # noqa: E402
from app import win32 as k  # noqa: E402
from app.main import App  # noqa: E402
from app.model import KEYBOARD, MOUSE, Device  # noqa: E402

startup.sync = lambda config: None  # 冒烟测试不碰注册表

_checks = 0


def check(cond, message: str) -> None:
    global _checks
    if not cond:
        raise AssertionError(message)
    _checks += 1
    print(f"  ok  {message}")


def pump(ms: int) -> None:
    """跑一小段消息循环，让窗口动画、计时器与后台结果落地。"""
    msg = k.MSG()
    end = time.time() + ms / 1000.0
    while time.time() < end:
        while k.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):
            k.TranslateMessage(ctypes.byref(msg))
            k.DispatchMessageW(ctypes.byref(msg))
        time.sleep(0.01)


def wait_for(fn, message: str, timeout: float = 5.0) -> None:
    end = time.time() + timeout
    while time.time() < end:
        if fn():
            return
        pump(40)
    raise AssertionError(message)


def main() -> int:
    print(f"临时配置目录: {TMP}")
    app = App(demo=True)
    original = {
        "interval": app.config["interval"],
        "tray_mode": app.config["tray_mode"],
        "theme": app.config["theme"],
        "show_bar": app.config["show_bar"],
        "alert": app.config["alert"],
        "enabled": list(app.config["enabled"] or []),
    }
    try:
        # ---------------------------------------------------------- 启动与托盘
        wait_for(lambda: len(app.state.devices) == 3, "演示设备未加载")
        check(len(app.display_devices()) == 1, "首次启动默认只显示鼠标")
        check(app.display_devices()[0].name == "MX Master 3S", "默认选中的是鼠标")
        check(app.tray._added and bool(app.tray.icon), "托盘图标已添加")
        check("MX Master 3S" in app.tooltip_text(), "托盘提示包含设备与电量")
        check("89%" in app.tooltip_text() or "87%" in app.tooltip_text()
              or "88%" in app.tooltip_text(), "托盘提示包含百分比")

        # ---------------------------------------------------------- 电量面板
        app.show_panel()
        pump(260)
        fly = app.flyout_window
        check(fly.visible, "面板可以打开")
        check(fly.w > 0 and fly.h > 0, "面板尺寸有效")
        check(fly.render().getbbox() is not None, "面板渲染出内容")
        work = app._work_area()
        pad_px = int(round(20 * app.scale))        # 面板四周留白（阴影区）
        vx0, vy0 = fly.pos[0] + pad_px, fly.pos[1] + pad_px
        vx1, vy1 = fly.pos[0] + fly.w - pad_px, fly.pos[1] + fly.h - pad_px
        check(work.left <= vx0 and vx1 <= work.right, "面板内容在屏幕水平范围内")
        check(work.top <= vy0 and vy1 <= work.bottom, "面板内容在屏幕垂直范围内")

        before = app.state.last_update
        fly.on_click("refresh")
        wait_for(lambda: not app.state.refreshing, "手动刷新未完成")
        check(app.state.last_update >= before, "手动刷新更新时间")
        fly.toggle()
        check(not fly.visible, "再次点击可以关闭面板")
        app.toggle_flyout()
        check(fly.visible, "托盘开合逻辑正常")
        fly.hide()

        # ---------------------------------------------------------- 任务栏电量条
        check(app.bar_window is not None and app.bar_window.visible, "电量条随启动显示")
        bar = app.bar_window
        old_w = bar.w
        check(old_w > 0, "电量条宽度有效")
        tray_hwnd = k.taskbar_hwnd()
        check(bool(tray_hwnd), "找到任务栏窗口 Shell_TrayWnd")
        check(bar.embedded and k.GetParent(bar.hwnd) == tray_hwnd, "电量条已嵌入任务栏")
        taskbar = k.taskbar_rect()
        check(taskbar.top <= bar.pos[1] and bar.pos[1] + bar.h <= taskbar.bottom,
              "电量条垂直居中于任务栏内")
        tn = k.tray_area_rect()
        if tn:
            check(bar.pos[0] + bar.w <= tn.left + 2, "电量条位于托盘区左侧")
        bar.on_click("bar")
        pump(220)
        check(fly.visible, "点击电量条打开面板")
        check(fly.pos[1] + fly.h <= bar.pos[1] + 2, "面板在任务栏上方，未压住电量条")
        fly.hide()

        # ---------------------------------------------------------- 原生外观
        bar.hover = None            # 鼠标可能正好停在电量条上，先归零再量尺寸
        bar.pressed = None
        image = bar.render()
        check(image.getpixel((0, 0))[3] <= 2, "电量条没有可见底色（左上角几乎全透明）")
        check(image.getpixel((image.width - 1, 0))[3] <= 2, "电量条没有可见底色（右上角几乎全透明）")
        solid = sum(image.getchannel("A").histogram()[9:])
        check(solid < image.width * image.height * 0.55, "电量条大部分是透明的，不是一整块膏药")
        check(abs(bar.h - (taskbar.bottom - taskbar.top)) <= 1, "电量条与任务栏等高")
        check(all(h[2] is None for h in bar.hits), "任务栏上用原生箭头光标")
        if bar.skin.dark:
            check(bar.skin.fg[0] > 200, "深色任务栏上用白墨")
        else:
            check(bar.skin.fg[0] < 60, "浅色任务栏上用深墨")

        bar.hover = "bar"
        hover_img = bar.render()
        mid = hover_img.width // 2
        check(hover_img.getpixel((mid, 2))[3] < 8, "悬停高亮没有顶到任务栏边缘")
        check(hover_img.getpixel((mid, hover_img.height // 2))[3] > 0, "悬停时出现高亮底板")
        bar.hover = None

        # 设备增减后仍要贴住托盘，不能向右压住托盘图标
        more = app.display_devices()
        app.state.devices.append(Device("demo:bar3", "Third Mouse", MOUSE, "2.4G", level=42))
        app.config.set_enabled("demo:bar3", True)
        app.update_bar()
        pump(120)
        check(bar.pos[0] + bar.w <= tn.left + 2, "变宽后仍然停在托盘区左侧")
        app.config.set_enabled("demo:bar3", False)
        app.state.devices = [d for d in app.state.devices if d.key != "demo:bar3"]
        app.update_bar()
        pump(120)
        check(len(app.display_devices()) == len(more), "移除临时设备后恢复")

        # ---------------------------------------------------------- 拖动换位
        band = bar._band()
        check(band is not None and band[1] - band[0] > 100 * app.scale, "电量条有可拖动的任务栏空白段")
        check(bar.drag_target(band[0] - 5000, bar.pos[1])[0] == band[0], "拖动范围左边界会被夹住")
        check(bar.drag_target(band[1] + 5000, bar.pos[1])[0] == band[1], "拖动范围右边界会被夹住")
        check(bar.drag_target(bar.pos[0], bar.pos[1] - 200)[1] == bar.pos[1], "拖动时不会离开任务栏")
        home = bar.pos[0]
        bar.place(band[1] - int(round(60 * app.scale)), bar.pos[1])
        bar.on_drag_end()
        pump(80)
        check(int(app.config["bar_offset"]) >= 56, "拖动后记住新的横向位置")
        check(abs(bar.pos[0] - (home - int(round(int(app.config["bar_offset"]) * app.scale)))) <= 2,
              "重新贴边时按记录的位置摆放")
        check(bar.pos[0] + bar.w <= tn.left + 2, "拖动后仍在托盘区左侧")
        bar.reset_offset()
        pump(80)
        check(app.config["bar_offset"] == 0 and bar.pos[0] == home, "可以回到默认位置")

        # ---------------------------------------------------------- 设置窗口
        app.open_settings()
        pump(260)
        settings = app.settings_window
        check(settings.visible, "设置窗口可以打开")
        check(settings.render().getbbox() is not None, "设置窗口渲染出内容")

        # 追加两台设备，制造可滚动的内容
        extra = [Device("demo:extra1", "Test Mouse 2", MOUSE, "2.4G", level=55),
                 Device("demo:extra2", "Test Keys", KEYBOARD, "蓝牙", level=66)]
        app.state.devices.extend(extra)
        settings.refresh()
        pump(120)
        check(settings._content_h > settings._body_h, "设备较多时内容可滚动")
        # 记录缓动过程里的每一帧：固定 sleep 后再采样会碰上 timer 消息迟到，
        # 偶发把"还没开始动"误判成"滚不动"，改成看帧序列就确定多了。
        frames = []
        orig_step = settings._paint_scroll

        def traced_step():
            done = orig_step()
            frames.append(settings.scroll)
            return done

        settings._paint_scroll = traced_step
        settings.on_wheel(-240)
        wait_for(lambda: not settings._scroll_timer, "滚轮可以滚动", timeout=1.5)
        settings._paint_scroll = orig_step
        check(bool(frames) and frames[-1] > 0, "滚轮可以滚动")
        check(len(frames) >= 3 and frames[0] < frames[-1],
              "滚动是逐帧缓动的，不是瞬间跳过去")
        settings.on_wheel(9999)
        wait_for(lambda: settings.scroll == 0, "滚回顶部会夹住", timeout=1.2)

        settings.on_click("dev:demo:keyboard")
        pump(80)
        check(len(app.display_devices()) == 2, "勾选键盘后显示两台设备")
        check(app.bar_window.w > old_w, "电量条随设备增加变宽")
        check("MX Keys Mini" in app.tooltip_text(), "托盘提示加入键盘")
        app.toggle_device("demo:keyboard")
        pump(80)
        check(len(app.display_devices()) == 1, "取消勾选恢复一台")

        settings.on_click("interval:2")
        check(app.config["interval"] == 120 and app.monitor.interval == 120, "刷新间隔改为 2 分钟")
        settings.on_click("traymode:1")
        check(app.config["tray_mode"] == "first", "托盘图标改为固定首个")
        settings.on_click("theme:2")
        check(app.theme.dark, "切换深色主题")
        settings.on_click("theme:1")
        check(not app.theme.dark, "切换浅色主题")
        settings.on_click("bar")
        check(not app.config["show_bar"] and not app.bar_window.visible, "关闭电量条")
        settings.on_click("bar")
        check(app.config["show_bar"] and app.bar_window.visible, "重新打开电量条")
        settings.on_click("alert")
        check(not app.config["alert"], "关闭低电量提醒")
        settings.on_click("alert")
        settings.on_click("done")
        check(not settings.visible, "完成按钮关闭设置")

        app.state.devices = [d for d in app.state.devices if not d.key.startswith("demo:extra")]

        # ---------------------------------------------------------- 其它状态
        app.toggle_pause()
        check(app.config["paused"], "暂停自动刷新")
        app.toggle_pause()
        check(not app.config["paused"], "恢复自动刷新")

        stamp = app.state.last_update
        app.refresh_now()
        wait_for(lambda: not app.state.refreshing, "刷新状态未复位")
        check(app.state.last_update >= stamp, "刷新后时间戳前进")

        app.on_timer(3)
        app.on_display_change()
        app.on_setting_change(0)
        check(True, "显示变化 / 系统设置变化事件不报错")

        app.reset_settings()
        check(app.config["interval"] == 60, "恢复默认设置")
        check(app.bar_window.visible, "恢复默认后电量条显示")

    finally:
        app.quit()
        pump(120)
        # 还原设置，避免临时配置被后续步骤误用
        for key, value in original.items():
            app.config[key] = value
        app.config.save()

    print(f"\n全部通过：{_checks} 项检查")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except AssertionError as exc:
        print(f"\n失败：{exc}")
        sys.exit(1)
