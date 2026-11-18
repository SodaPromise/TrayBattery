"""系统托盘：图标渲染、通知区域消息、右键菜单。"""
from __future__ import annotations

import ctypes

from PIL import Image

from . import win32 as k
from .draw import battery_glyph, level_color
from .model import ONLINE

WM_TRAY = k.WM_APP + 1
WM_DATA = k.WM_APP + 2
WM_REFRESHING = k.WM_APP + 4
WM_SHOW_PANEL = k.WM_APP + 9
WM_MENU = k.WM_APP + 10
WM_SHOW_SETTINGS = k.WM_APP + 11

MENU_OPEN = 1
MENU_REFRESH = 2
MENU_SETTINGS = 3
MENU_PAUSE = 4
MENU_BAR = 5
MENU_AUTOSTART = 6
MENU_QUIT = 7
MENU_BAR_HOME = 8
MENU_DEVICE_BASE = 100

# 资源管理器重启后会广播这条消息，收到后要重新添加图标
WM_TASKBARCREATED = k.register_window_message("TaskbarCreated")

_ICON_FLAGS = k.NIF_MESSAGE | k.NIF_ICON | k.NIF_TIP | k.NIF_SHOWTIP


def tray_icon_image(device, size: int, theme, paused: bool = False) -> Image.Image:
    if device is None:
        return battery_glyph(size, None, theme.c("faint"), outline=theme.c("text", 200))
    if paused:
        return battery_glyph(size, None, theme.c("faint"), outline=theme.c("faint"))
    if device.status == ONLINE and device.level is not None:
        color = level_color(theme, device.level, device.charging, device.status)
        return battery_glyph(size, device.level, color, charging=device.charging,
                             outline=theme.c("text", 225))
    return battery_glyph(size, None, theme.c("faint"), outline=theme.c("text", 165))


class TrayHost:
    """隐藏的顶层窗口：接收托盘回调、设备变化、计时器。"""

    CLASS = "TrayBatteryHost"

    def __init__(self, app) -> None:
        self.app = app
        self.hwnd = k.create_window(self.CLASS, 1, 1, k.WS_EX_TOOLWINDOW)
        k.bind_window(self.hwnd, self)
        self.icon = None
        self.nid = k.NOTIFYICONDATAW()
        self.nid.cbSize = ctypes.sizeof(k.NOTIFYICONDATAW)
        self.nid.hWnd = self.hwnd
        self.nid.uID = 1
        self.nid.uFlags = _ICON_FLAGS
        self.nid.uCallbackMessage = WM_TRAY
        self.nid.uVersion = k.NOTIFYICON_VERSION_4
        self._added = False
        self.update_icon()

    # ------------------------------------------------------------------
    def icon_size(self) -> int:
        try:
            return int(k.GetSystemMetricsForDpi(k.SM_CXSMICON, k.system_dpi()))
        except Exception:
            return 16

    def update_icon(self) -> None:
        app = self.app
        hicon = k.hicon_from_image(
            tray_icon_image(app.tray_device(), self.icon_size(), app.theme, app.config["paused"])
        )
        self.nid.hIcon = hicon
        self.nid.szTip = app.tooltip_text()[:126]
        if not self._added:
            self._added = bool(k.shell32.Shell_NotifyIconW(k.NIM_ADD, ctypes.byref(self.nid)))
            if self._added:
                k.shell32.Shell_NotifyIconW(k.NIM_SETVERSION, ctypes.byref(self.nid))
        else:
            self.nid.uFlags = _ICON_FLAGS
            k.shell32.Shell_NotifyIconW(k.NIM_MODIFY, ctypes.byref(self.nid))
        if self.icon:
            k.destroy_icon(self.icon)
        self.icon = hicon

    def refresh_tooltip(self) -> None:
        self.nid.uFlags = k.NIF_TIP | k.NIF_SHOWTIP
        self.nid.szTip = self.app.tooltip_text()[:126]
        k.shell32.Shell_NotifyIconW(k.NIM_MODIFY, ctypes.byref(self.nid))
        self.nid.uFlags = _ICON_FLAGS

    def balloon(self, title: str, text: str) -> None:
        if not self._added:
            return
        nid = k.NOTIFYICONDATAW()
        nid.cbSize = self.nid.cbSize
        nid.hWnd = self.hwnd
        nid.uID = 1
        nid.uFlags = k.NIF_INFO
        nid.szInfo = text[:255]
        nid.szInfoTitle = title[:63]
        nid.dwInfoFlags = k.NIIF_INFO
        k.shell32.Shell_NotifyIconW(k.NIM_MODIFY, ctypes.byref(nid))

    # ------------------------------------------------------------------
    def on_message(self, msg, wp, lp):
        if msg == WM_TRAY:
            code = lp & 0xFFFF
            if code in (k.NIN_SELECT, k.NIN_KEYSELECT):
                self.app.toggle_flyout()
            elif code in (k.WM_CONTEXTMENU, k.WM_RBUTTONUP):
                self.app.show_menu()
            return 0
        if msg == WM_DATA:
            self.app.handle_devices()
            return 0
        if WM_TASKBARCREATED and msg == WM_TASKBARCREATED:
            self._added = False
            self.update_icon()
            self.app.rebuild_bar()      # 子窗口会随旧任务栏一起销毁，需要重建
            return 0
        if msg == WM_REFRESHING:
            if self.app.flyout_window.visible:
                self.app.flyout_window.invalidate()
            return 0
        if msg == WM_SHOW_PANEL:
            self.app.show_panel()
            return 0
        if msg == WM_SHOW_SETTINGS:      # 已有实例收到 --settings
            self.app.open_settings()
            return 0
        if msg == WM_MENU:
            self.app.show_menu()
            return 0
        if msg == k.WM_TIMER:
            self.app.on_timer(int(wp))
            return 0
        if msg == k.WM_DEVICECHANGE:
            if wp in (k.DBT_DEVNODES_CHANGED, 0x0002, 0x8000):  # 节点变化 / 到达 / 自定义
                self.app.on_device_change()
            return 0
        if msg == k.WM_DISPLAYCHANGE:
            self.app.on_display_change()
            return 0
        if msg == 0x001A:  # WM_SETTINGCHANGE
            self.app.on_setting_change(lp)
            return 0
        if msg == k.WM_CLOSE:
            self.app.quit()
            return 0
        return k.DefWindowProcW(self.hwnd, msg, wp, lp)

    # ------------------------------------------------------------------
    def remove(self) -> None:
        if self._added:
            k.shell32.Shell_NotifyIconW(k.NIM_DELETE, ctypes.byref(self.nid))
            self._added = False
        if self.icon:
            k.destroy_icon(self.icon)
            self.icon = None
