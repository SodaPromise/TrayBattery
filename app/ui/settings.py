"""设置窗口：选择显示设备、刷新间隔、任务栏电量条与常规选项。"""
from __future__ import annotations

from PIL import Image, ImageDraw

from .. import win32 as k
from ..draw import Canvas, battery_glyph, device_glyph, level_color
from ..model import OFFLINE, ONLINE, UNSUPPORTED, ERROR
from .base import LayerWindow, checkbox, segmented, toggle

W = 520
PAD = 22
HEADER_H = 60
FOOTER_H = 64
CONTENT_W = W - PAD * 2
ROW_H = 54
ROW_GAP = 6

INTERVALS = [(30, "30 秒"), (60, "1 分钟"), (120, "2 分钟"), (300, "5 分钟")]
TRAY_MODES = [("cycle", "轮播"), ("first", "固定首个")]
THEMES = [("auto", "跟随系统"), ("light", "浅色"), ("dark", "深色")]


class SettingsWindow(LayerWindow):
    CLASS = "TrayBatterySettings"

    def __init__(self, app) -> None:
        super().__init__(app)
        self.pad = PAD
        self.scroll = 0.0
        self._body_cache = None
        self._body_hits: list[tuple] = []
        self._content_h = 0.0
        self._body_top = 0.0
        self._body_h = 0.0
        self._panel_h = 0.0
        self._last_panel_h = 0.0

    # ------------------------------------------------------------------
    def refresh(self) -> None:
        self._body_cache = None
        self.invalidate()

    def on_theme_changed(self) -> None:
        self._body_cache = None

    def devices(self):
        return self.app.all_devices()

    # ------------------------------------------------------------------
    def _display_rows(self) -> list[tuple]:
        cfg = self.app.config
        interval_idx = next((i for i, (v, _) in enumerate(INTERVALS) if v == cfg["interval"]), 1)
        tray_idx = 0 if cfg["tray_mode"] == "cycle" else 1
        return [
            ("seg", "自动刷新间隔", INTERVALS_OPTIONS, interval_idx, 208, "interval"),
            ("seg", "托盘图标", [o for _, o in TRAY_MODES], tray_idx, 132, "traymode"),
            ("toggle", "任务栏电量条", "在托盘区左侧显示，跟随任务栏深浅，可左右拖动",
             bool(cfg["show_bar"]), "bar"),
            ("toggle", "低电量提醒", f"电量低于 {cfg['alert_threshold']}% 时提醒",
             bool(cfg["alert"]), "alert"),
        ]

    def _general_rows(self) -> list[tuple]:
        theme_idx = next((i for i, (v, _) in enumerate(THEMES) if v == self.app.config["theme"]), 0)
        return [
            ("toggle", "开机自动启动", "登录 Windows 后自动运行",
             self.app.autostart_enabled(), "autostart"),
            ("seg", "主题", [o for _, o in THEMES], theme_idx, 180, "theme"),
        ]

    # ------------------------------------------------------------------
    def content_height(self) -> float:
        n = max(1, len(self.devices()))
        h = 4 + 24 + n * (ROW_H + ROW_GAP) + 10
        h += 26 + len(self._display_rows()) * 46
        h += 10 + 26 + len(self._general_rows()) * 46
        return h

    def layout(self) -> None:
        content_h = self.content_height()
        max_panel = self.app.max_panel_height()
        panel_h = min(content_h + HEADER_H + FOOTER_H + 10, max_panel)
        panel_h = max(panel_h, 380)
        self._content_h = content_h
        self._panel_h = panel_h
        self._body_top = PAD + HEADER_H
        self._body_h = panel_h - HEADER_H - FOOTER_H
        self.set_size(W + PAD * 2, panel_h + PAD * 2)
        if self.visible and abs(self._last_panel_h - panel_h) > 0.5:
            self.pos = self.app.settings_position(self.lw, self.lh)
        self._last_panel_h = panel_h
        max_scroll = max(0.0, content_h - self._body_h + 6)
        self.scroll = max(0.0, min(self.scroll, max_scroll))

    # ------------------------------------------------------------------
    def render(self):
        self.layout()
        theme = self.app.theme
        f = self.app.fonts
        c = Canvas((self.lw, self.lh), self.scale, 2)
        panel = (PAD, PAD, PAD + W, PAD + self._panel_h)
        c.shadow(panel, 16, 12, (0, 0, 0, 255), 60 if not theme.dark else 120, dy=5)
        c.rrect(panel, 16, fill=theme.c("panel"), outline=theme.c("line"), width=1)

        hits: list[tuple] = []
        body = self._body_image()
        if body is not None:
            crop = body.crop((0, int(round(self.scroll * self.scale)), body.width,
                              int(round((self.scroll + self._body_h) * self.scale))))
            c.paste(crop, (PAD, self._body_top))
            hits.extend(self._visible_body_hits())

        # 头部
        c.text((PAD + 24, PAD + HEADER_H / 2), "设置", f.get(17, "semibold"), theme.c("text"), "lm")
        cb = (PAD + W - 46, PAD + 15, PAD + W - 16, PAD + 45)
        if self.hover == "close":
            c.rrect(cb, 8, fill=theme.c("card_hover"))
        cx, cy = (cb[0] + cb[2]) / 2, (cb[1] + cb[3]) / 2
        c.line([(cx - 5, cy - 5), (cx + 5, cy + 5)], theme.c("sub"), 1.6)
        c.line([(cx + 5, cy - 5), (cx - 5, cy + 5)], theme.c("sub"), 1.6)
        hits.append((cb, "close", "hand"))
        c.line([(PAD, PAD + HEADER_H), (PAD + W, PAD + HEADER_H)], theme.c("line"), 1)

        # 底部
        fy = PAD + self._panel_h - FOOTER_H
        c.line([(PAD, fy), (PAD + W, fy)], theme.c("line"), 1)
        c.text((PAD + 24, fy + FOOTER_H / 2), "电量助手 1.0", f.get(10), theme.c("faint"), "lm")
        done = (PAD + W - 24 - 84, fy + 15, PAD + W - 24, fy + 47)
        if self.hover == "done":
            c.rrect(done, 8, fill=theme.c("accent", 235))
        else:
            c.rrect(done, 8, fill=theme.c("accent"))
        c.text(((done[0] + done[2]) / 2, fy + 31), "完成", f.get(12, "semibold"), theme.c("accent_text"), "mm")
        hits.append((done, "done", "hand"))

        reset = (done[0] - 100, fy + 17, done[0] - 12, fy + 45)
        if self.hover == "reset":
            c.rrect(reset, 8, fill=theme.c("card_hover"))
        c.text((reset[0] + 6, fy + 31), "恢复默认", f.get(11), theme.c("sub"), "lm")
        hits.append((reset, "reset", "hand"))

        # 滚动条
        if self._content_h > self._body_h + 2:
            track_y0, track_y1 = self._body_top + 4, self._body_top + self._body_h - 4
            frac = self._body_h / self._content_h
            thumb_h = max(24, (track_y1 - track_y0) * frac)
            max_scroll = self._content_h - self._body_h + 6
            t = self.scroll / max_scroll if max_scroll > 0 else 0
            ty = track_y0 + (track_y1 - track_y0 - thumb_h) * t
            c.rrect((PAD + W - 8, ty, PAD + W - 5, ty + thumb_h), 1.5,
                    fill=theme.mix("faint", "panel", 0.55))

        self.set_hits(hits)
        img = c.finish()
        return self._post_paint(img, theme)

    # ------------------------------------------------------------------
    def _post_paint(self, img, theme):
        s = self.scale
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay)
        if self._content_h > self._body_h + 2:
            fade = max(10, int(24 * s))
            x0, x1 = PAD * s + 1, (PAD + W) * s - 1
            bottom_edge = (self._body_top + self._body_h) * s - 2
            top_edge = self._body_top * s + 2
            for i in range(fade):
                a = int(255 * ((i + 1) / fade) ** 2)
                od.rectangle((x0, bottom_edge - fade + i, x1, bottom_edge - fade + i + 1),
                             fill=theme.c("panel", a))
                if self.scroll > 1:
                    a = int(255 * (1 - i / fade) ** 2)
                    od.rectangle((x0, top_edge + i, x1, top_edge + i + 1),
                                 fill=theme.c("panel", a))
        if self.hover and self.hover not in ("close", "done", "reset"):
            rect = self._hit_rect(self.hover)
            if rect:
                od.rounded_rectangle(
                    (rect[0] * s, rect[1] * s, rect[2] * s, rect[3] * s),
                    radius=10 * s, outline=theme.c("accent", 130), width=max(1, int(1.4 * s)),
                )
        img.alpha_composite(overlay)
        return img

    def _body_image(self):
        key = self._cache_key()
        if self._body_cache is not None and self._body_cache[0] == key:
            return self._body_cache[1]
        theme = self.app.theme
        f = self.app.fonts
        ch = max(self._content_h, 10)
        c = Canvas((W, ch), self.scale, 2)
        hits: list[tuple] = []
        y = 4.0

        # ------- 显示设备
        c.text((PAD, y + 11), "显示设备", f.get(12.5, "semibold"), theme.c("text"), "lm")
        c.text((W - PAD, y + 11), "勾选后显示在托盘与任务栏电量条", f.get(9.8), theme.c("faint"), "rm")
        y += 24
        devices = self.devices()
        if not devices:
            c.text((PAD, y + 20), "未发现设备，请确认蓝牙或接收器已连接", f.get(10.5), theme.c("sub"), "lm")
            y += 44
        for dev in devices:
            row_rect = (PAD, y, W - PAD, y + ROW_H)
            checked = self.app.is_selected(dev.key)
            c.rrect(row_rect, 10,
                    fill=theme.mix("accent_soft", "card", 0.72) if checked else theme.c("card"),
                    outline=theme.mix("accent", "card", 0.28) if checked else theme.c("line"),
                    width=1)
            checkbox(c, (PAD + 14, y + 17, PAD + 34, y + 37), checked, theme)
            c.ellipse((PAD + 44, y + 12, PAD + 74, y + 42),
                      fill=theme.c("accent_soft") if checked else theme.c("panel_alt"))
            c.paste(device_glyph(dev.kind, self.px(16),
                                 theme.c("accent") if checked else theme.c("faint")),
                    (PAD + 51, y + 19))
            c.text((PAD + 84, y + 20), dev.name, f.get(12.5, "semibold"),
                   theme.c("text") if checked else theme.c("sub"), "lm")
            c.text((PAD + 84, y + 37), f"{dev.kind_label} · {dev.transport}", f.get(9.8),
                   theme.c("faint"), "lm")
            right = W - PAD - 14
            if dev.status == ONLINE and dev.level is not None:
                color = level_color(theme, dev.level, dev.charging, dev.status)
                pct = f"{dev.level}%"
                font = f.get(12.5, "semibold", True)
                c.text((right, y + 27), pct, font, color, "rm")
                tw = self.measure(pct, font)
                c.paste(battery_glyph(self.px(20), dev.level, color, charging=dev.charging,
                                      outline=theme.c("faint", 175)), (right - tw - 7 - 20, y + 17))
            else:
                label, fg, tint = {
                    OFFLINE: ("离线", theme.c("sub"), "sub"),
                    UNSUPPORTED: ("不支持电量", theme.c("amber"), "amber"),
                    ERROR: ("读取失败", theme.c("red"), "red"),
                }.get(dev.status, ("未知", theme.c("faint"), "faint"))
                font = f.get(9.8)
                tw = self.measure(label, font)
                box = (right - tw - 16, y + 17, right, y + 37)
                c.rrect(box, 10, fill=theme.mix(tint, "card", 0.16))
                c.text(((box[0] + box[2]) / 2, y + 27), label, font, fg, "mm")
            hits.append((row_rect, f"dev:{dev.key}", "hand"))
            y += ROW_H + ROW_GAP

        # ------- 显示与刷新
        y += 10
        c.text((PAD, y + 11), "显示与刷新", f.get(12.5, "semibold"), theme.c("text"), "lm")
        y += 26
        for spec in self._display_rows():
            y = self._row(c, hits, y, spec)

        # ------- 常规
        y += 10
        c.text((PAD, y + 11), "常规", f.get(12.5, "semibold"), theme.c("text"), "lm")
        y += 26
        for spec in self._general_rows():
            y = self._row(c, hits, y, spec)

        image = c.finish()
        self._body_hits = hits
        self._body_cache = (key, image)
        return image

    def _cache_key(self):
        devices = tuple((d.key, d.name, d.level, d.status, d.charging) for d in self.devices())
        cfg = tuple(self.app.config[k] for k in
                    ("interval", "tray_mode", "show_bar", "alert", "alert_threshold", "theme"))
        return (devices, cfg, self.app.selected_keys(), self.app.theme.dark, round(self.app.scale, 3),
                self.app.autostart_enabled())

    def _row(self, c: Canvas, hits, y: float, spec: tuple) -> float:
        if spec[0] == "seg":
            return self._seg_row(c, hits, y, *spec[1:])
        return self._toggle_row(c, hits, y, *spec[1:])

    def _seg_row(self, c: Canvas, hits, y, label, options, index, width, ctrl_id) -> float:
        theme = self.app.theme
        f = self.app.fonts
        c.text((PAD, y + 23), label, f.get(12), theme.c("text"), "lm")
        box = (W - PAD - width, y + 9, W - PAD, y + 37)
        rects = segmented(c, box, options, index, f, theme)
        for i, rect in enumerate(rects):
            hits.append((rect, f"{ctrl_id}:{i}", "hand"))
        c.line([(PAD, y + 46), (W - PAD, y + 46)], theme.c("line", 150), 0.8)
        return y + 46

    def _toggle_row(self, c: Canvas, hits, y, label, desc, on, ctrl_id) -> float:
        theme = self.app.theme
        f = self.app.fonts
        c.text((PAD, y + 17), label, f.get(12), theme.c("text"), "lm")
        c.text((PAD, y + 35), desc, f.get(9.8), theme.c("faint"), "lm")
        box = (W - PAD - 40, y + 12, W - PAD, y + 34)
        toggle(c, box, on, theme)
        hits.append((box, ctrl_id, "hand"))
        c.line([(PAD, y + 46), (W - PAD, y + 46)], theme.c("line", 150), 0.8)
        return y + 46

    # ------------------------------------------------------------------
    def _visible_body_hits(self):
        top = self._body_top
        bottom = top + self._body_h
        out = []
        for rect, hid, cur in self._body_hits:
            x0, y0, x1, y1 = rect
            ay0 = top + y0 - self.scroll
            ay1 = top + y1 - self.scroll
            if ay1 < top + 2 or ay0 > bottom - 2:
                continue
            out.append(((x0 + PAD, max(top, ay0), x1 + PAD, min(bottom, ay1)), hid, cur))
        return out

    def _hit_rect(self, hid: str):
        for rect, h, _ in self._visible_body_hits():
            if h == hid:
                return rect
        return None

    # ------------------------------------------------------------------
    def show(self, x=None, y=None, animate=True, activate=True) -> None:
        self._body_cache = None
        self.layout()
        if x is None or y is None:
            x, y = self.app.settings_position(self.lw, self.lh)
        super().show(x, y, animate, activate)

    def on_wheel(self, delta: int) -> None:
        max_scroll = max(0.0, self._content_h - self._body_h + 6)
        step = 56
        self.scroll = max(0.0, min(max_scroll, self.scroll - (delta / 120) * step))
        self.invalidate()

    def on_click(self, hid: str) -> None:
        app = self.app
        if hid == "close" or hid == "done":
            self.hide()
            return
        if hid == "reset":
            app.reset_settings()
            self.refresh()
            return
        if hid.startswith("dev:"):
            app.toggle_device(hid[4:])
            self.refresh()
            return
        if hid.startswith("interval:"):
            app.set_interval(INTERVALS[int(hid.split(":")[1])][0])
            self.refresh()
            return
        if hid.startswith("traymode:"):
            app.set_tray_mode(TRAY_MODES[int(hid.split(":")[1])][0])
            self.refresh()
            return
        if hid.startswith("theme:"):
            app.set_theme(THEMES[int(hid.split(":")[1])][0])
            self.refresh()
            return
        if hid == "bar":
            app.toggle_show_bar()
            self.refresh()
            return
        if hid == "alert":
            app.toggle_alert()
            self.refresh()
            return
        if hid == "autostart":
            app.toggle_autostart()
            self.refresh()
            return


INTERVALS_OPTIONS = [label for _, label in INTERVALS]
