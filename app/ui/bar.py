"""任务栏电量条：作为 Shell_TrayWnd 的子窗口，贴在托盘 / 输入法指示器左侧。"""
from __future__ import annotations

import ctypes

from .. import win32 as k
from ..draw import Canvas, device_glyph, level_color
from ..model import ERROR, OFFLINE, ONLINE, UNSUPPORTED
from .base import LayerWindow

H = 34
PAD = 12          # 独立悬浮时的阴影留白
PAD_EMBED = 5     # 嵌进任务栏后只需要一点点内缩
MAX_CHIPS = 4


class BarWindow(LayerWindow):
    CLASS = "TrayBatteryBar"
    EX_STYLE = k.WS_EX_LAYERED | k.WS_EX_TOOLWINDOW | k.WS_EX_NOACTIVATE
    ANIM = False
    topmost = False

    def __init__(self, app) -> None:
        super().__init__(app)
        self.pad = PAD
        self.embedded = False
        self.parent_hwnd = None

    # ------------------------------------------------------------------ 内容
    def chips(self):
        devs = self.app.display_devices()
        return devs[:MAX_CHIPS], max(0, len(devs) - MAX_CHIPS)

    def panel_width(self) -> float:
        devs, extra = self.chips()
        if not devs:
            return 150
        f = self.app.fonts
        w = 12
        for i, d in enumerate(devs):
            label = self._label(d)
            w += 16 + 5 + self.measure(label, self._font(d)) + 10
            if i:
                w += 12
        if extra:
            w += self.measure(f"+{extra}", f.get(10, "semibold")) + 14
        return max(96 if self.embedded else 120, w)

    @staticmethod
    def _label(dev) -> str:
        if dev.status == ONLINE and dev.level is not None:
            return f"{dev.level}%"
        return {OFFLINE: "离线", UNSUPPORTED: "不支持", ERROR: "读取失败"}.get(dev.status, "—")

    def _font(self, dev):
        """数字用 Segoe UI 等宽数字更整齐，中文必须回落到雅黑。"""
        numeric = dev.status == ONLINE and dev.level is not None
        return self.app.fonts.get(11, "semibold", numeric)

    def layout(self) -> tuple[float, float]:
        pw = self.panel_width()
        self.pad = PAD_EMBED if self.embedded else PAD
        self.set_size(pw + self.pad * 2, H + self.pad * 2)
        return pw, H

    def render(self):
        pw, ph = self.layout()
        theme = self.app.theme
        f = self.app.fonts
        pad = self.pad
        c = Canvas((self.lw, self.lh), self.scale, 2)
        panel = (pad, pad, pad + pw, pad + ph)
        if not self.embedded:
            c.shadow(panel, 11, 7, (0, 0, 0, 255), 46 if not theme.dark else 100, dy=2)
        fill = theme.mix("card_hover", "panel", 0.85) if self.hover == "bar" else theme.c("panel", 250)
        c.rrect(panel, 9 if self.embedded else 11, fill=fill, outline=theme.c("line"), width=1)

        devs, extra = self.chips()
        hits = [(panel, "bar", "hand")]
        if not devs:
            c.text((pad + pw / 2, pad + ph / 2), "未选择设备", f.get(10.5), theme.c("faint"), "mm")
            self.set_hits(hits)
            return c.finish()

        x = pad + 12
        cy = pad + ph / 2
        for i, dev in enumerate(devs):
            if i:
                c.line([(x, cy - 7), (x, cy + 7)], theme.c("line"), 1)
                x += 12
            color = level_color(theme, dev.level, dev.charging, dev.status)
            if dev.status != ONLINE:
                color = theme.c("faint")
            c.paste(device_glyph(dev.kind, self.px(15), color), (x, cy - 7.5))
            x += 20
            label = self._label(dev)
            font = self._font(dev)
            c.text((x, cy), label, font, color, "lm")
            x += self.measure(label, font) + 10

        if extra:
            c.text((x, cy), f"+{extra}", f.get(10, "semibold"), theme.c("faint"), "lm")

        self.set_hits(hits)
        return c.finish()

    # ------------------------------------------------------------------ 嵌入任务栏
    def embed(self) -> bool:
        """挂到 Shell_TrayWnd 下；任务栏重建后需要重新调用。"""
        tray = k.taskbar_hwnd()
        if not tray:
            self.unembed()
            return False
        if self.parent_hwnd != tray:
            k.set_child(self.hwnd, tray)
            self.parent_hwnd = tray
        self.embedded = True
        return True

    def unembed(self) -> None:
        if self.embedded or self.parent_hwnd:
            k.set_child(self.hwnd, None)
            self.parent_hwnd = None
            self.embedded = False

    def place_taskbar(self) -> bool:
        """贴到托盘区左边缘，垂直居中于任务栏。"""
        tray = k.taskbar_rect()
        if not tray:
            return False
        width, height = tray.right - tray.left, tray.bottom - tray.top
        if width <= height:            # 竖排任务栏不做嵌入，退回悬浮
            return False
        tn = k.tray_area_rect()
        gap = max(2, int(round(6 * self.scale)))
        pad = int(round(self.pad * self.scale))
        if tn and tn.left > tray.left + width // 3:
            right = tn.left - gap
        else:
            right = tray.right - int(round(140 * self.scale))
        x = right - self.w + pad
        y = tray.top + max(0, (height - self.h) // 2)
        self.place(x, y)
        return True

    # ------------------------------------------------------------------ 绘制 / 定位
    def _present(self, image, alpha: int) -> None:
        self.canvas.upload(image)
        if self.embedded:
            # 子窗口由 place() 负责位置，交给 ULW 定位会与父窗口坐标系冲突
            self.canvas.present(self.hwnd, alpha=alpha)
        else:
            self.canvas.present(self.hwnd, self.pos[0], self.pos[1], alpha)

    def place(self, x: int, y: int) -> None:
        self.pos = (int(x), int(y))
        if self.embedded and self.parent_hwnd:
            pt = k.POINT(self.pos[0], self.pos[1])
            k.ScreenToClient(self.parent_hwnd, ctypes.byref(pt))
            k.SetWindowPos(self.hwnd, None, pt.x, pt.y, self.w, self.h,
                           k.SWP_NOZORDER | k.SWP_NOACTIVATE)
        else:
            super().place(x, y)

    def place_default(self) -> None:
        pos = self.app.config["bar_pos"]
        if pos and self.app.is_reachable(pos[0], pos[1], self.w, self.h):
            self.place(int(pos[0]), int(pos[1]))
            return
        x, y = self.app.bar_default_position(self.w, self.h)
        self.place(x, y)

    def show(self, x=None, y=None, animate=False, activate=False) -> None:
        self.layout()
        if not self.embed() or not self.place_taskbar():
            self.unembed()
            self.layout()
            self.place_default()
        super().show(animate=False, activate=False)

    def refresh_position(self) -> None:
        """任务栏重建 / 分辨率变化 / DPI 变化后重新贴合。"""
        if not self.visible:
            return
        self.layout()
        if not self.embed() or not self.place_taskbar():
            self.unembed()
            self.layout()
            self.place_default()
        self.invalidate()

    # ------------------------------------------------------------------
    def is_drag_handle(self, hid: str) -> bool:
        return False if self.embedded else hid == "bar"

    def on_drag_end(self) -> None:
        self.app.config["bar_pos"] = [self.pos[0], self.pos[1]]
        self.app.config.save()

    def on_click(self, hid: str) -> None:
        if hid == "bar":
            self.app.toggle_flyout_near_bar(self)
