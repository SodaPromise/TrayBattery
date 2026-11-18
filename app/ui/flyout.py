"""托盘面板：设备电量列表。"""
from __future__ import annotations

import time

from .. import win32 as k
from ..draw import Canvas, app_mark, battery_glyph, device_glyph, ellipsize, level_color
from ..model import OFFLINE, ONLINE, UNSUPPORTED, ERROR
from .base import LayerWindow, gear_icon

VK_LBUTTON = 0x01
VK_RBUTTON = 0x02

PANEL_W = 344
PAD = 20
HEADER_H = 64
ROW_H = 68
FOOTER_H = 50
MAX_ROWS = 5


class FlyoutWindow(LayerWindow):
    CLASS = "TrayBatteryFlyout"
    anchor = (1.0, 1.0)      # 从右下角（托盘方向）长出来
    ANIM_MS = 160

    def __init__(self, app) -> None:
        super().__init__(app)
        self.pad = PAD
        self._last_panel_h = 0.0
        self._auto_pos = True
        self._fg0 = 0
        self._btn = False

    # ------------------------------------------------------------------
    def rows(self):
        return self.app.display_devices()[:MAX_ROWS]

    def extra_count(self) -> int:
        return max(0, len(self.app.display_devices()) - MAX_ROWS)

    def panel_height(self) -> float:
        rows = self.rows()
        if not rows:
            return HEADER_H + 156 + FOOTER_H
        return HEADER_H + len(rows) * ROW_H + 10 + FOOTER_H

    def layout(self) -> tuple[float, float, float]:
        panel_h = self.panel_height()
        self.set_size(PANEL_W + PAD * 2, panel_h + PAD * 2)
        if self.visible and self._auto_pos and abs(self._last_panel_h - panel_h) > 0.5:
            self.pos = self.app.flyout_position(PANEL_W, panel_h, PAD)
        self._last_panel_h = panel_h
        return PANEL_W, panel_h, PAD

    # ------------------------------------------------------------------
    def render(self):
        panel_w, panel_h, pad = self.layout()
        theme = self.app.theme
        f = self.app.fonts
        c = Canvas((self.lw, self.lh), self.scale, 2)
        panel = (pad, pad, pad + panel_w, pad + panel_h)
        c.shadow(panel, 16, 10, (0, 0, 0, 255), 54 if not theme.dark else 110, dy=4)
        c.rrect(panel, 16, fill=theme.c("panel"), outline=theme.c("line"), width=1)

        hits = []
        c.paste(app_mark(self.px(30), theme), (pad + 18, pad + 17))
        c.text((pad + 58, pad + 23), "设备电量", f.get(15, "semibold"),
               theme.c("text"), "lm", tracking=0.3)
        c.text((pad + 58, pad + 41), self._subtitle(), f.get(10.5), theme.c("sub"), "lm")

        gb = (pad + panel_w - 46, pad + 16, pad + panel_w - 12, pad + 48)
        if self.hover == "gear":
            c.rrect(gb, 9, fill=theme.c("card_hover"))
        c.paste(gear_icon(self.px(17), theme.c("sub")), (gb[0] + 7.5, gb[1] + 7.5))
        hits.append((gb, "gear", "hand"))

        c.line([(pad + 16, pad + HEADER_H - 6), (pad + panel_w - 16, pad + HEADER_H - 6)],
               theme.c("line"), 1)

        rows = self.rows()
        if not rows:
            self._draw_empty(c, pad, hits)
        else:
            top = pad + HEADER_H
            for i, dev in enumerate(rows):
                ry = top + i * ROW_H
                self._draw_row(c, dev, pad, panel_w, ry, i, hits)
                if i < len(rows) - 1:
                    c.line([(pad + 62, ry + ROW_H - 1), (pad + panel_w - 18, ry + ROW_H - 1)],
                           theme.c("line"), 0.8)
            if self.extra_count():
                c.text((pad + panel_w - 18, top + len(rows) * ROW_H + 10),
                       f"另有 {self.extra_count()} 台设备", f.get(9.5), theme.c("faint"), "rm")

        fy = pad + panel_h - FOOTER_H
        c.line([(pad + 16, fy), (pad + panel_w - 16, fy)], theme.c("line"), 1)
        stamp = time.strftime("%H:%M", time.localtime(self.app.state.last_update or time.time()))
        c.text((pad + 18, fy + FOOTER_H / 2),
               "已暂停自动刷新" if self.app.config["paused"] else f"{stamp} 更新",
               f.get(10), theme.c("faint"), "lm")

        btn_set = (pad + panel_w - 16 - 56, fy + 12, pad + panel_w - 16, fy + 38)
        btn_ref = (btn_set[0] - 8 - 50, fy + 12, btn_set[0] - 8, fy + 38)
        if self.hover == "refresh":
            c.rrect(btn_ref, 8, fill=theme.c("card_hover"))
        c.text(((btn_ref[0] + btn_ref[2]) / 2, fy + 25),
               "刷新中" if self.app.state.refreshing else "刷新",
               f.get(11), theme.c("sub"), "mm")
        hits.append((btn_ref, "refresh", "hand"))

        c.rrect(btn_set, 8, fill=theme.c("accent"))
        c.text(((btn_set[0] + btn_set[2]) / 2, fy + 25), "设置",
               f.get(11, "semibold"), theme.c("accent_text"), "mm")
        hits.append((btn_set, "settings", "hand"))

        self.set_hits(hits)
        return c.finish()

    # ------------------------------------------------------------------
    def _subtitle(self) -> str:
        state = self.app.state
        if self.app.config["paused"]:
            return "已暂停自动刷新"
        if state.refreshing:
            return "正在刷新…"
        return f"{len(self.app.display_devices())} 台设备 · {self.app.interval_text()}"

    def _draw_row(self, c: Canvas, dev, pad, panel_w, ry, index, hits) -> None:
        theme = self.app.theme
        f = self.app.fonts
        cy = ry + ROW_H / 2
        row_rect = (pad + 8, ry + 2, pad + panel_w - 8, ry + ROW_H - 2)
        if self.hover == f"row{index}":
            c.rrect(row_rect, 11, fill=theme.c("card_hover"))
        hits.append((row_rect, f"row{index}", None))

        c.ellipse((pad + 18, cy - 17, pad + 52, cy + 17),
                  fill=theme.c("accent_soft") if dev.status == ONLINE else theme.c("panel_alt"))
        c.paste(device_glyph(dev.kind, self.px(18),
                             theme.c("accent") if dev.status == ONLINE else theme.c("faint")),
                (pad + 26, cy - 9))

        max_text_w = panel_w - 62 - 116
        name = ellipsize(self._measure, dev.name, f.get(13, "semibold"), max_text_w * self.scale)
        c.text((pad + 62, cy - 9), name, f.get(13, "semibold"), theme.c("text"),
               "lm", tracking=0.1)
        c.text((pad + 62, cy + 10), dev.status_text(), f.get(10.5), theme.c("sub"), "lm")

        right = pad + panel_w - 18
        if dev.status == ONLINE and dev.level is not None:
            color = level_color(theme, dev.level, dev.charging, dev.status)
            pct = f"{dev.level}%"
            font = f.get(14, "semibold", True)
            c.text((right, cy), pct, font, color, "rm", tracking=-0.2)
            tw = self.measure(pct, font)
            c.paste(battery_glyph(self.px(24), dev.level, color, charging=dev.charging,
                                  outline=theme.c("faint", 185)),
                    (right - tw - 8 - 24, cy - 12))
        else:
            label, fg, tint = {
                OFFLINE: ("离线", theme.c("sub"), "sub"),
                UNSUPPORTED: ("不支持", theme.c("amber"), "amber"),
                ERROR: ("读取失败", theme.c("red"), "red"),
            }.get(dev.status, ("未知", theme.c("faint"), "faint"))
            font = f.get(10)
            tw = self.measure(label, font)
            box = (right - tw - 18, cy - 10, right, cy + 10)
            c.rrect(box, 10, fill=theme.mix(tint, "panel", 0.16))
            c.text(((box[0] + box[2]) / 2, cy), label, font, fg, "mm")

    def _draw_empty(self, c: Canvas, pad, hits) -> None:
        theme = self.app.theme
        f = self.app.fonts
        cx = pad + PANEL_W / 2
        top = pad + HEADER_H
        c.paste(battery_glyph(self.px(38), None, theme.c("faint"),
                              outline=theme.c("faint", 150)), (cx - 19, top + 18))
        c.text((cx, top + 78), "暂无可显示的设备", f.get(12.5, "semibold"),
               theme.c("text"), "mm", tracking=0.3)
        c.text((cx, top + 97), "在设置中选择要显示的鼠标、键盘或耳机", f.get(10), theme.c("sub"), "mm")
        box = (cx - 44, top + 114, cx + 44, top + 142)
        c.rrect(box, 8, fill=theme.c("accent"))
        c.text((cx, top + 128), "打开设置", f.get(11, "semibold"), theme.c("accent_text"), "mm")
        hits.append((box, "settings", "hand"))

    # ------------------------------------------------------------------
    def show(self, x=None, y=None, animate=True, activate=True) -> None:
        if x is None or y is None:
            x, y = self.app.flyout_position(PANEL_W, self.panel_height(), PAD)
            self._auto_pos = True
        else:
            self._auto_pos = False
        super().show(x, y, animate, activate)
        self._fg0 = k.GetForegroundWindow()
        self._btn = self._pressed()
        k.SetTimer(self.hwnd, 2, 120, None)

    def hide(self) -> None:
        if not self.visible:
            return
        k.KillTimer(self.hwnd, 2)
        super().hide()

    @staticmethod
    def _pressed() -> bool:
        return bool(k.GetAsyncKeyState(VK_LBUTTON) & 0x8000
                    or k.GetAsyncKeyState(VK_RBUTTON) & 0x8000)

    def _in_window(self, win, mx: int, my: int, pad: int = 6) -> bool:
        return bool(win is not None and win.visible
                    and win.pos[0] - pad <= mx <= win.pos[0] + win.w + pad
                    and win.pos[1] - pad <= my <= win.pos[1] + win.h + pad)

    def on_timer(self, timer_id: int) -> None:
        if timer_id == 1:
            super().on_timer(timer_id)
            return
        if timer_id != 2 or not self.visible:
            return
        mx, my = k.cursor_pos()
        inside = (self.pos[0] - 6 <= mx <= self.pos[0] + self.w + 6
                  and self.pos[1] - 6 <= my <= self.pos[1] + self.h + 6)
        pressed = self._pressed()
        clicked = pressed and not self._btn
        self._btn = pressed
        if inside:
            return
        # 电量条、设置窗口上的点击不应关闭面板
        if self._in_window(getattr(self.app, "bar_window", None), mx, my):
            return
        if self._in_window(getattr(self.app, "settings_window", None), mx, my):
            return
        fg = k.GetForegroundWindow()
        if clicked:
            # 点在任务栏/托盘上时交给托盘自己的开合逻辑，避免"关了又被打开"
            work = self.app._work_area()
            if not (work.left <= mx < work.right and work.top <= my < work.bottom):
                self.hide()
                return
        if fg != self.hwnd and fg != self._fg0:
            self.hide()

    def on_click(self, hid: str) -> None:
        if hid in ("gear", "settings"):
            self.hide()
            self.app.open_settings()
        elif hid == "refresh":
            self.app.refresh_now()
