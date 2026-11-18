"""应用主逻辑：托盘、窗口、状态汇总与交互。"""
from __future__ import annotations

import ctypes
import threading
import time

from . import startup
from . import win32 as k
from .config import APP_TITLE, Config
from .model import (
    AppState, Device, MOUSE, OFFLINE, ONLINE, STATUS_LABEL,
)
from .monitor import Monitor
from .theme import Fonts, forget_bar_skin, resolve_theme
from .tray import (
    MENU_AUTOSTART, MENU_BAR, MENU_BAR_HOME, MENU_DEVICE_BASE, MENU_OPEN, MENU_PAUSE,
    MENU_QUIT, MENU_REFRESH, MENU_SETTINGS, TrayHost,
    WM_REFRESHING, WM_SHOW_PANEL, WM_SHOW_SETTINGS,
)
from .ui.bar import BarWindow
from .ui.flyout import PANEL_W as FLYOUT_W, PAD as FLYOUT_PAD, FlyoutWindow
from .ui.settings import SettingsWindow


def _same_device(a: str, b: str) -> bool:
    """判断两个设备名是否指向同一台物理设备。

    蓝牙链路的名字常带 `-05` / `-01718` 之类的配对后缀，而 USB 接收器
    链路用裸型号名。只接受「一方是另一方前缀且差异很小」，避免把
    CD28S 和 CD28S Pro 这类不同型号误合并。
    """
    def norm(text: str) -> str:
        return "".join(ch for ch in (text or "").lower() if ch.isalnum())

    x, y = norm(a), norm(b)
    if not x or not y:
        return False
    if x == y:
        return True
    short, long_ = (x, y) if len(x) <= len(y) else (y, x)
    return long_.startswith(short) and len(long_) - len(short) <= 4


class App:
    def __init__(self, demo: bool = False, open_panel: bool = False,
                 open_settings: bool = False) -> None:
        k.enable_dpi_awareness()
        self.demo = demo
        self.config = Config()
        self.theme = resolve_theme(self.config["theme"])
        self.scale = k.scale_for_dpi(k.system_dpi())
        self.fonts = Fonts(self.scale)
        self.state = AppState()
        self.pending = None
        self._pending_lock = threading.Lock()
        self._alerted: set[str] = set()
        self._menu_keys: list[str] = []
        self.settings_window: SettingsWindow | None = None
        self.bar_window: BarWindow | None = None

        self.host = TrayHost(self)
        self.tray = self.host
        self.flyout_window = FlyoutWindow(self)
        self.monitor = Monitor(self)
        self.monitor.start()
        k.SetTimer(self.host.hwnd, 3, 5000, None)
        startup.sync(self.config)

        if open_panel:
            self.show_panel()
        if open_settings:
            self.open_settings()

    # ------------------------------------------------------------------ 状态
    def all_devices(self) -> list[Device]:
        return self.state.devices

    def is_selected(self, key: str) -> bool:
        return self.config.is_enabled(key)

    def selected_keys(self) -> tuple:
        return tuple(self.config["enabled"] or [])

    def display_devices(self) -> list[Device]:
        return [d for d in self.state.devices if self.config.is_enabled(d.key)]

    def tray_device(self):
        devs = self.display_devices()
        if not devs:
            return None
        if self.config["tray_mode"] == "cycle" and len(devs) > 1:
            return devs[self.state.cycle % len(devs)]
        return devs[0]

    def interval_text(self) -> str:
        sec = int(self.config["interval"])
        if sec % 60 == 0:
            return f"每 {sec // 60} 分钟刷新"
        return f"每 {sec} 秒刷新"

    def tooltip_text(self) -> str:
        if self.config["paused"]:
            return f"{APP_TITLE} · 已暂停"
        devs = self.display_devices()
        if not devs:
            return f"{APP_TITLE} · 未选择显示设备"
        lines = []
        for d in devs[:4]:
            if d.status == ONLINE and d.level is not None:
                extra = " · 充电中" if d.charging else ""
                lines.append(f"{d.name}  {d.level}%{extra}")
            else:
                lines.append(f"{d.name}  {STATUS_LABEL.get(d.status, '未知')}")
        return "\n".join(lines)

    # ------------------------------------------------------------------ 数据
    def mark_refreshing(self, flag: bool, notify: bool = False) -> None:
        self.state.refreshing = flag
        if notify and self.host and self.host.hwnd:
            k.PostMessageW(self.host.hwnd, WM_REFRESHING, 0, 0)

    def handle_devices(self) -> None:
        with self._pending_lock:
            data = self.pending
            self.pending = None
        if not data:
            return
        found, ts = data
        if not self.config["initialized"]:
            self._apply_default_selection(found)
        for d in found:
            self.config.remember(d)
        self._prune_known({d.key for d in found})
        self.state.devices = sorted(self._merge_offline(found), key=lambda d: d.sort_key())
        self.state.last_update = ts
        self.state.refreshing = False
        self.config.save()
        self.tray.update_icon()
        self.update_bar()
        if self.flyout_window.visible:
            self.flyout_window.invalidate()
        if self.settings_window and self.settings_window.visible:
            self.settings_window.refresh()
        self._check_low_battery(found)

    def _apply_default_selection(self, found: list[Device]) -> None:
        mice = [d for d in found if d.kind == MOUSE]
        pick = [d for d in mice if d.status == ONLINE] or mice
        if not pick:
            pick = [d for d in found if d.status == ONLINE][:1]
        for d in pick:
            self.config.set_enabled(d.key, True)
        self.config["initialized"] = True

    def _merge_offline(self, found: list[Device]) -> list[Device]:
        keys = {d.key for d in found}
        enabled = set(self.config["enabled"] or [])
        out = list(found)
        online = [d for d in found if d.status != OFFLINE]
        for key in enabled:
            if key in keys:
                continue
            info = self.config.known.get(key)
            if not info:
                continue
            name = info.get("name", "设备")
            twin = next((d for d in online if _same_device(name, d.name)), None)
            if twin is not None:
                # 同一台设备换了链路（2.4G 接收器 → 蓝牙）。旧的离线行不再补，
                # 勾选状态迁到当前在线的那条，避免列表里出现两行同名设备。
                if twin.key not in enabled:
                    self.config.set_enabled(key, False)
                    self.config.set_enabled(twin.key, True)
                continue
            out.append(Device(
                key=key,
                name=name,
                kind=info.get("kind", "other"),
                transport=info.get("transport", "蓝牙"),
                status=OFFLINE,
                last_level=info.get("last_level"),
            ))
        return out

    def _prune_known(self, present: set[str]) -> None:
        enabled = set(self.config["enabled"] or [])
        now = time.time()
        for key, info in list(self.config.known.items()):
            if key in present or key in enabled:
                continue
            if now - float(info.get("last_seen", 0)) > 45 * 86400:
                self.config.known.pop(key, None)

    def _check_low_battery(self, found: list[Device]) -> None:
        if not self.config["alert"]:
            return
        threshold = int(self.config["alert_threshold"])
        for d in found:
            if d.status != ONLINE or d.level is None or not self.config.is_enabled(d.key):
                continue
            if d.level <= threshold and d.key not in self._alerted:
                self._alerted.add(d.key)
                self.tray.balloon(f"{d.name} 电量偏低", f"剩余 {d.level}%，建议充电。")
            elif d.level > threshold + 5:
                self._alerted.discard(d.key)

    # ------------------------------------------------------------------ 刷新
    def refresh_now(self) -> None:
        if self.state.refreshing:
            return
        self.mark_refreshing(True)
        self.monitor.trigger(force=True)
        if self.flyout_window.visible:
            self.flyout_window.invalidate()
        if self.settings_window and self.settings_window.visible:
            self.settings_window.invalidate()

    def on_device_change(self) -> None:
        k.KillTimer(self.host.hwnd, 4)
        k.SetTimer(self.host.hwnd, 4, 1200, None)

    def on_timer(self, timer_id: int) -> None:
        if timer_id == 3:
            devs = self.display_devices()
            if self.config["tray_mode"] == "cycle" and len(devs) > 1 and not self.config["paused"]:
                self.state.cycle = (self.state.cycle + 1) % len(devs)
                self.tray.update_icon()
                if not self.flyout_window.visible:
                    self.tray.refresh_tooltip()
        elif timer_id == 4:
            k.KillTimer(self.host.hwnd, 4)
            self.refresh_now()

    # ------------------------------------------------------------------ 窗口
    def show_panel(self) -> None:
        self.flyout_window.show()

    def toggle_flyout(self) -> None:
        if self.flyout_window.visible:
            self.flyout_window.hide()
        else:
            self.flyout_window.show()

    def toggle_flyout_near_bar(self, bar: BarWindow) -> None:
        fly = self.flyout_window
        if fly.visible:
            fly.hide()
            return
        s = self.scale
        win_w = int(round((FLYOUT_W + FLYOUT_PAD * 2) * s))
        win_h = int(round((fly.panel_height() + FLYOUT_PAD * 2) * s))
        work = self._work_area()
        gap = int(round(8 * s))
        # 面板右边缘对齐电量条，再夹到工作区内
        x = bar.pos[0] + bar.w - win_w
        x = max(work.left + gap, min(x, work.right - win_w - gap))
        # 电量条嵌在任务栏里时，pos[1] 会低于工作区底边，这里统一贴工作区底部
        y = min(bar.pos[1], work.bottom) - win_h - gap
        if y < work.top + gap:
            y = min(bar.pos[1], work.bottom) + gap
        fly.show(x, y)

    def open_settings(self) -> None:
        if self.settings_window is None:
            self.settings_window = SettingsWindow(self)
        self.settings_window.show()

    def update_bar(self) -> None:
        show = bool(self.config["show_bar"]) and bool(self.display_devices())
        if show:
            if self.bar_window is None:
                self.bar_window = BarWindow(self)
            if not self.bar_window.visible:
                self.bar_window.show()
            else:
                self.bar_window.invalidate()
        elif self.bar_window and self.bar_window.visible:
            self.bar_window.hide()

    # ------------------------------------------------------------------ 设置项
    def toggle_device(self, key: str) -> None:
        self.config.toggle_enabled(key)
        self.config.save()
        self.tray.update_icon()
        self.update_bar()
        if self.flyout_window.visible:
            self.flyout_window.invalidate()
        if self.settings_window and self.settings_window.visible:
            self.settings_window.refresh()

    def set_interval(self, seconds: int) -> None:
        self.config["interval"] = int(seconds)
        self.config.save()
        self.monitor.set_interval(int(seconds))
        if self.flyout_window.visible:
            self.flyout_window.invalidate()

    def set_tray_mode(self, mode: str) -> None:
        self.config["tray_mode"] = mode
        self.config.save()
        self.state.cycle = 0
        self.tray.update_icon()

    def set_theme(self, mode: str) -> None:
        self.config["theme"] = mode
        self.config.save()
        self.apply_theme()

    def apply_theme(self) -> None:
        self._apply_visuals()

    def _apply_visuals(self) -> None:
        """主题或缩放变化后重建字体、缓存与可见窗口。"""
        self.theme = resolve_theme(self.config["theme"])
        self.fonts = Fonts(self.scale)
        self.tray.update_icon()
        for win in (self.flyout_window, self.settings_window, self.bar_window):
            if win is None:
                continue
            win.on_theme_changed()
            if win.visible:
                win.paint()

    def toggle_show_bar(self) -> None:
        self.config["show_bar"] = not bool(self.config["show_bar"])
        if not self.config["show_bar"]:
            self.config["bar_pos"] = None
            self.config["bar_offset"] = 0
        self.config.save()
        self.update_bar()

    def toggle_alert(self) -> None:
        self.config["alert"] = not bool(self.config["alert"])
        self.config.save()

    def autostart_enabled(self) -> bool:
        return startup.is_enabled()

    def toggle_autostart(self) -> None:
        enabled = startup.is_enabled()
        startup.set_enabled(not enabled)
        self.config["autostart"] = not enabled
        self.config.save()

    def toggle_pause(self) -> None:
        self.config["paused"] = not bool(self.config["paused"])
        self.config.save()
        self.monitor.trigger(force=not self.config["paused"])
        self.tray.update_icon()
        if self.flyout_window.visible:
            self.flyout_window.invalidate()

    def reset_settings(self) -> None:
        self.config["interval"] = 60
        self.config["tray_mode"] = "cycle"
        self.config["show_bar"] = True
        self.config["bar_offset"] = 0
        self.config["alert"] = True
        self.config["theme"] = "auto"
        self.config.save()
        self.monitor.set_interval(60)
        self.apply_theme()
        self.update_bar()
        self.tray.update_icon()

    # ------------------------------------------------------------------ 菜单
    def show_menu(self) -> None:
        menu = k.CreatePopupMenu()
        k.AppendMenuW(menu, k.MF_STRING, MENU_OPEN, "打开电量面板")
        k.SetMenuDefaultItem(menu, MENU_OPEN, 0)
        k.AppendMenuW(menu, k.MF_SEPARATOR, 0, None)

        self._menu_keys = []
        devices = self.state.devices[:12]
        if devices:
            for d in devices:
                idx = MENU_DEVICE_BASE + len(self._menu_keys)
                self._menu_keys.append(d.key)
                if d.status == ONLINE and d.level is not None:
                    label = f"{d.name}   {d.level}%"
                else:
                    label = f"{d.name}   {STATUS_LABEL.get(d.status, '未知')}"
                flags = k.MF_STRING | (k.MF_CHECKED if self.config.is_enabled(d.key) else 0)
                k.AppendMenuW(menu, flags, idx, label)
            k.AppendMenuW(menu, k.MF_SEPARATOR, 0, None)

        k.AppendMenuW(menu, k.MF_STRING, MENU_REFRESH, "立即刷新")
        k.AppendMenuW(menu, k.MF_STRING | (k.MF_CHECKED if self.config["paused"] else 0),
                      MENU_PAUSE, "暂停自动刷新")
        k.AppendMenuW(menu, k.MF_STRING | (k.MF_CHECKED if self.config["show_bar"] else 0),
                      MENU_BAR, "显示任务栏电量条")
        if self.config["show_bar"] and int(self.config["bar_offset"] or 0) > 0:
            k.AppendMenuW(menu, k.MF_STRING, MENU_BAR_HOME, "电量条回到原位")
        k.AppendMenuW(menu, k.MF_STRING, MENU_SETTINGS, "设置…")
        k.AppendMenuW(menu, k.MF_STRING | (k.MF_CHECKED if startup.is_enabled() else 0),
                      MENU_AUTOSTART, "开机自动启动")
        k.AppendMenuW(menu, k.MF_SEPARATOR, 0, None)
        k.AppendMenuW(menu, k.MF_STRING, MENU_QUIT, "退出")

        x, y = k.cursor_pos()
        k.SetForegroundWindow(self.host.hwnd)
        cmd = k.TrackPopupMenu(
            menu, k.TPM_RETURNCMD | k.TPM_RIGHTBUTTON | k.TPM_TOPALIGN,
            x, y, 0, self.host.hwnd, None,
        )
        k.PostMessageW(self.host.hwnd, k.WM_NULL, 0, 0)
        k.DestroyMenu(menu)
        if cmd:
            self._dispatch_menu(int(cmd))

    def _dispatch_menu(self, cmd: int) -> None:
        if cmd == MENU_OPEN:
            self.toggle_flyout()
        elif cmd == MENU_REFRESH:
            self.refresh_now()
        elif cmd == MENU_SETTINGS:
            self.open_settings()
        elif cmd == MENU_PAUSE:
            self.toggle_pause()
        elif cmd == MENU_BAR:
            self.toggle_show_bar()
            if self.settings_window and self.settings_window.visible:
                self.settings_window.refresh()
        elif cmd == MENU_BAR_HOME:
            if self.bar_window is not None:
                self.bar_window.reset_offset()
        elif cmd == MENU_AUTOSTART:
            self.toggle_autostart()
        elif cmd == MENU_QUIT:
            self.quit()
        elif cmd >= MENU_DEVICE_BASE:
            i = cmd - MENU_DEVICE_BASE
            if 0 <= i < len(getattr(self, "_menu_keys", [])):
                self.toggle_device(self._menu_keys[i])

    # ------------------------------------------------------------------ 位置
    def _work_area(self) -> k.RECT:
        return k.monitor_work_area(*k.cursor_pos())

    def flyout_position(self, panel_w: float, panel_h: float, pad: float) -> tuple[int, int]:
        s = self.scale
        work = self._work_area()
        x = work.right - int(round((pad + panel_w) * s)) - int(round(10 * s))
        y = work.bottom - int(round((pad + panel_h) * s)) - int(round(8 * s))
        bar = self.bar_window
        if bar is not None and bar.visible and not bar.embedded:
            win_w = int(round((pad * 2 + panel_w) * s))
            if x < bar.pos[0] + bar.w and x + win_w > bar.pos[0]:
                above = bar.pos[1] - int(round((panel_h + pad * 2) * s)) - int(round(6 * s))
                if above > work.top + 8:
                    y = above
        if x < work.left + 8:
            x = work.left + 8
        if y < work.top + 8:
            y = work.top + 8
        return x, y

    def bar_default_position(self, w: int, h: int) -> tuple[int, int]:
        s = self.scale
        work = self._work_area()
        x = work.right - w - int(round(14 * s))
        y = work.bottom - h - int(round(6 * s))
        return max(work.left, x), max(work.top, y)

    def settings_position(self, lw: float, lh: float) -> tuple[int, int]:
        s = self.scale
        work = self._work_area()
        w_px, h_px = int(round(lw * s)), int(round(lh * s))
        x = work.left + (work.right - work.left - w_px) // 2
        y = work.top + max(int(round(36 * s)), (work.bottom - work.top - h_px) // 2 - int(20 * s))
        y = min(y, work.bottom - h_px - int(round(16 * s)))
        y = max(y, work.top + int(round(16 * s)))
        return x, y

    def max_panel_height(self) -> float:
        work = self._work_area()
        return max(380.0, min(720.0, (work.bottom - work.top) / self.scale - 56))

    def is_reachable(self, x: int, y: int, w: int, h: int) -> bool:
        r = k.RECT(x, y, x + w, y + h)
        mi = k.MONITORINFO()
        mi.cbSize = ctypes.sizeof(k.MONITORINFO)
        hm = k.MonitorFromPoint(k.POINT(x + w // 2, y + h // 2), k.MONITOR_DEFAULTTONEAREST)
        if not hm:
            return False
        if not k.GetMonitorInfoW(hm, ctypes.byref(mi)):
            return False
        inter_w = min(r.right, mi.rcWork.right) - max(r.left, mi.rcWork.left)
        inter_h = min(r.bottom, mi.rcWork.bottom) - max(r.top, mi.rcWork.top)
        return inter_w > w // 3 and inter_h > h // 2

    # ------------------------------------------------------------------ 系统事件
    def on_setting_change(self, lp: int) -> None:
        try:
            text = ctypes.wstring_at(lp) if lp else ""
        except Exception:
            text = ""
        if text != "ImmersiveColorSet":
            return
        # 任务栏可能是深色 / 浅色 / 强调色，改完要重新采样墨色
        forget_bar_skin()
        if self.config["theme"] == "auto":
            self.apply_theme()
        elif self.bar_window and self.bar_window.visible:
            self.bar_window.invalidate()

    def on_display_change(self) -> None:
        """分辨率/显示器变化后把常驻窗口拉回可见区域。"""
        if self.flyout_window.visible:
            self.flyout_window.hide()
        if self.bar_window and self.bar_window.visible:
            self.bar_window.refresh_position()

    def rebuild_bar(self) -> None:
        """任务栏重建后，旧的子窗口已被系统销毁，只能重建。"""
        if self.bar_window is not None:
            try:
                self.bar_window.destroy()
            except Exception:
                pass
            self.bar_window = None
        self.update_bar()

    def on_dpi_changed(self, dpi: int) -> None:
        new_scale = k.scale_for_dpi(dpi)
        if abs(new_scale - self.scale) < 0.01:
            return
        self.scale = new_scale
        self._apply_visuals()

    # ------------------------------------------------------------------ 生命周期
    def quit(self) -> None:
        self.monitor.stop()
        try:
            self.tray.remove()
        except Exception:
            pass
        for win in (self.bar_window, self.settings_window, self.flyout_window):
            if win is not None:
                win.destroy()
        k.PostQuitMessage(0)

    def run(self) -> None:
        k.run_message_loop()


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="任务栏设备电量显示")
    parser.add_argument("--demo", action="store_true", help="使用演示设备")
    parser.add_argument("--panel", action="store_true", help="启动后打开面板")
    parser.add_argument("--settings", action="store_true", help="启动后打开设置")
    parser.add_argument("--quit", action="store_true", help="关闭已运行的实例")
    args = parser.parse_args(argv)

    # CreateMutexW 成功创建新对象时不会清零 LastError，必须先置 0 再判断，
    # 否则可能读到本线程之前残留的 183（ERROR_ALREADY_EXISTS）而误判。
    k.kernel32.SetLastError(0)
    mutex = k.kernel32.CreateMutexW(None, False, "TrayBattery.SingleInstance")
    already = ctypes.get_last_error() == 183
    # mutex 句柄要一直持有到进程结束，否则单实例约束就失效了
    _keep_alive = mutex
    if already and mutex:
        hwnd = k.FindWindowW("TrayBatteryHost", None)
        if hwnd:
            if args.quit:
                k.PostMessageW(hwnd, k.WM_CLOSE, 0, 0)
            elif args.settings:
                k.PostMessageW(hwnd, WM_SHOW_SETTINGS, 0, 0)
            else:
                k.PostMessageW(hwnd, WM_SHOW_PANEL, 0, 0)
            return 0
    app = App(demo=args.demo, open_panel=args.panel, open_settings=args.settings)
    app.run()
    return 0
