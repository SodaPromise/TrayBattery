"""设置窗口：选择显示设备、刷新间隔、任务栏电量条与常规选项。"""
from __future__ import annotations

import time

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
SCROLL_STEP = 56
SCROLL_FRAME_MS = 16
SCROLL_EASE = 0.34        # 每帧吃掉剩余距离的比例：约 7 帧滑到位

INTERVALS = [(30, "30 秒"), (60, "1 分钟"), (120, "2 分钟"), (300, "5 分钟")]
TRAY_MODES = [("cycle", "轮播"), ("first", "固定首个")]
THEMES = [("auto", "跟随系统"), ("light", "浅色"), ("dark", "深色")]


class SettingsWindow(LayerWindow):
    CLASS = "TrayBatterySettings"

    def __init__(self, app) -> None:
        super().__init__(app)
        self.pad = PAD
        self.scroll = 0.0
        self._scroll_target = 0.0
        self._scroll_timer = 0
        self._last_scroll_paint = 0.0
        self._body_cache = None
        self._chrome_cache = None
        self._fade_cache = None
        self._body_hits: list[tuple] = []
        self._content_h = 0.0
        self._body_top = 0.0
        self._body_h = 0.0
        self._panel_h = 0.0
        self._last_panel_h = 0.0
        self._autostart = None

    # ------------------------------------------------------------------
    def refresh(self) -> None:
        self._body_cache = None
        self._autostart = None
        self.invalidate()

    def on_theme_changed(self) -> None:
        self._body_cache = None
        self._chrome_cache = None
        self._fade_cache = None

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
        if self._autostart is None:
            self._autostart = self.app.autostart_enabled()
        return [
            ("toggle", "开机自动启动", "登录 Windows 后自动运行",
             self._autostart, "autostart"),
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
        self._scroll_target = max(0.0, min(self._scroll_target, max_scroll))

    # ------------------------------------------------------------------ 关键矩形
    def _close_box(self):
        return (PAD + W - 46, PAD + 15, PAD + W - 16, PAD + 45)

    def _done_box(self):
        fy = PAD + self._panel_h - FOOTER_H
        return (PAD + W - 24 - 84, fy + 16, PAD + W - 24, fy + 48)

    def _reset_box(self):
        fy = PAD + self._panel_h - FOOTER_H
        done = self._done_box()
        return (done[0] - 100, fy + 18, done[0] - 12, fy + 46)

    # ------------------------------------------------------------------ 静态底图
    def _chrome_image(self):
        """阴影、面板、页眉、页脚这些不随滚动变化的部分只画一次。"""
        key = (round(self.lw, 2), round(self.lh, 2), self.app.theme.dark,
               round(self.scale, 3), round(self._panel_h, 2))
        if self._chrome_cache is not None and self._chrome_cache[0] == key:
            return self._chrome_cache[1]
        theme = self.app.theme
        f = self.app.fonts
        c = Canvas((self.lw, self.lh), self.scale, 2)
        panel = (PAD, PAD, PAD + W, PAD + self._panel_h)
        c.shadow(panel, 16, 12, (0, 0, 0, 255), 60 if not theme.dark else 120, dy=5)
        c.rrect(panel, 16, fill=theme.c("panel"), outline=theme.c("line"), width=1)

        # 页眉
        c.text((PAD + 24, PAD + HEADER_H / 2), "设置", f.get(17, "semibold"),
               theme.c("text"), "lm", tracking=0.3)
        cb = self._close_box()
        cx, cy = (cb[0] + cb[2]) / 2, (cb[1] + cb[3]) / 2
        c.line([(cx - 5, cy - 5), (cx + 5, cy + 5)], theme.c("sub"), 1.6)
        c.line([(cx + 5, cy - 5), (cx - 5, cy + 5)], theme.c("sub"), 1.6)
        c.line([(PAD, PAD + HEADER_H), (PAD + W, PAD + HEADER_H)], theme.c("line"), 1)

        # 页脚
        fy = PAD + self._panel_h - FOOTER_H
        c.line([(PAD, fy), (PAD + W, fy)], theme.c("line"), 1)
        c.text((PAD + 24, fy + FOOTER_H / 2), "电量助手 1.0", f.get(10),
               theme.c("faint"), "lm")
        done = self._done_box()
        c.rrect(done, 8, fill=theme.c("accent"))
        c.text(((done[0] + done[2]) / 2, (done[1] + done[3]) / 2), "完成",
               f.get(12, "semibold"), theme.c("accent_text"), "mm", tracking=0.2)
        reset = self._reset_box()
        c.text((reset[0] + 6, (reset[1] + reset[3]) / 2), "恢复默认",
               f.get(11), theme.c("sub"), "lm")

        image = c.finish()
        self._chrome_cache = (key, image)
        return image

    # ------------------------------------------------------------------ 滚动内容
    def render(self):
        self.layout()
        img = self._base_image().copy()
        body = self._body_image()
        s = self.scale
        if body is not None:
            x = int(round(PAD * s))
            y = int(round(self._body_top * s))
            top = int(round(self.scroll * s))
            height = int(round(self._body_h * s))
            crop = body.crop((0, top, body.width, min(body.height, top + height)))
            if crop.width > img.width - x:
                crop = crop.crop((0, 0, img.width - x, crop.height))
            if crop.height > img.height - y:
                crop = crop.crop((0, 0, crop.width, img.height - y))
            img.alpha_composite(crop, (x, y))

        self._paint_hover(img)
        self._paint_scrollbar(img)
        # 命中区域跟着滚动位置走：基类 hit_at() 只看 self.hits，
        # 不注册的话所有鼠标点击都会落空（滚动后尤其明显）。
        self.set_hits(self._all_hits())
        return img

    def _base_image(self):
        """底图 = 静态外壳 + 上下渐隐。滚动时只复制它，不再重算阴影和页眉页脚。"""
        want_top = self.scroll > 1
        key = (round(self.lw, 2), round(self.lh, 2), self.app.theme.dark,
               round(self.scale, 3), round(self._panel_h, 2), want_top)
        if self._fade_cache is not None and self._fade_cache[0] == key:
            return self._fade_cache[1]
        img = self._chrome_image().copy()
        self._paint_scroll_fades(img, want_top)
        self._fade_cache = (key, img)
        return img

    def _paint_scroll_fades(self, img, want_top: bool) -> None:
        theme = self.app.theme
        s = self.scale
        fade = max(12, int(32 * s))
        x0, x1 = int(round(PAD * s + 1)), int(round((PAD + W) * s - 1))
        width = max(1, x1 - x0)

        def ramp(t: float) -> float:
            # smoothstep：两端都平缓，中段过渡，不会在边缘留下一条硬边
            return t * t * (3 - 2 * t)

        bottom = Image.new("RGBA", (width, fade), (0, 0, 0, 0))
        bd = ImageDraw.Draw(bottom)
        for i in range(fade):
            a = int(255 * ramp(i / max(1, fade - 1)))
            bd.rectangle((0, i, width, i + 1), fill=theme.c("panel", a))
        top_img = None
        if want_top:
            top_img = Image.new("RGBA", (width, fade), (0, 0, 0, 0))
            td = ImageDraw.Draw(top_img)
            for i in range(fade):
                a = int(255 * (1 - ramp(i / max(1, fade - 1))))
                td.rectangle((0, i, width, i + 1), fill=theme.c("panel", a))

        bottom_edge = int(round((self._body_top + self._body_h) * s))
        img.alpha_composite(bottom, (x0, bottom_edge - fade))
        if top_img is not None:
            top_edge = int(round(self._body_top * s))
            img.alpha_composite(top_img, (x0, top_edge))

    def _paint_hover(self, img) -> None:
        theme = self.app.theme
        s = self.scale
        hover = self.hover
        if not hover:
            return
        if hover in ("close", "reset"):
            box = self._close_box() if hover == "close" else self._reset_box()
            self._rounded(img, box, 8, theme.c("card_hover"))
        elif hover == "done":
            # 只在主按钮上叠一层很淡的白，和 Win11 按钮的悬停一致
            self._rounded(img, self._done_box(), 8, theme.c("accent_text", 22))
        else:
            rect = self._hit_rect(hover)
            if rect:
                layer = Image.new("RGBA", (max(1, int((rect[2] - rect[0]) * s)),
                                           max(1, int((rect[3] - rect[1]) * s))), (0, 0, 0, 0))
                ImageDraw.Draw(layer).rounded_rectangle(
                    (0, 0, layer.width - 1, layer.height - 1), radius=int(10 * s),
                    outline=theme.c("accent", 130), width=max(1, int(1.4 * s)))
                img.alpha_composite(layer, (int(round(rect[0] * s)), int(round(rect[1] * s))))

    def _rounded(self, img, box, radius: float, color) -> None:
        s = self.scale
        x0, y0 = int(round(box[0] * s)), int(round(box[1] * s))
        w, h = int(round((box[2] - box[0]) * s)), int(round((box[3] - box[1]) * s))
        if w < 1 or h < 1:
            return
        layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ImageDraw.Draw(layer).rounded_rectangle((0, 0, w - 1, h - 1),
                                                radius=max(1, int(radius * s)), fill=color)
        img.alpha_composite(layer, (x0, y0))

    def _paint_scrollbar(self, img) -> None:
        if self._content_h <= self._body_h + 2:
            return
        theme = self.app.theme
        s = self.scale
        track_y0, track_y1 = self._body_top + 4, self._body_top + self._body_h - 4
        frac = self._body_h / self._content_h
        thumb_h = max(24, (track_y1 - track_y0) * frac)
        max_scroll = self._content_h - self._body_h + 6
        t = self.scroll / max_scroll if max_scroll > 0 else 0
        ty = track_y0 + (track_y1 - track_y0 - thumb_h) * t
        x0 = int(round((PAD + W - 7.5) * s))
        y0 = int(round(ty * s))
        w = max(1, int(round(2.5 * s)))
        h = max(1, int(round(thumb_h * s)))
        layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ImageDraw.Draw(layer).rounded_rectangle(
            (0, 0, w - 1, h - 1), radius=max(1, w // 2),
            fill=theme.mix("faint", "panel", 0.45))
        img.alpha_composite(layer, (x0, y0))

    # ------------------------------------------------------------------
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
        c.text((PAD, y + 12), "显示设备", f.get(12.5, "semibold"), theme.c("text"),
               "lm", tracking=0.3)
        c.text((W - PAD, y + 12), "勾选后显示在托盘与任务栏电量条", f.get(9.6),
               theme.c("faint"), "rm")
        y += 24
        devices = self.devices()
        if not devices:
            c.text((PAD, y + 20), "未发现设备，请确认蓝牙或接收器已连接", f.get(10.5),
                   theme.c("sub"), "lm")
            y += 44
        for dev in devices:
            row_rect = (PAD, y, W - PAD, y + ROW_H)
            checked = self.app.is_selected(dev.key)
            c.rrect(row_rect, 10,
                    fill=theme.mix("accent_soft", "card", 0.72) if checked else theme.c("card"),
                    outline=theme.mix("accent", "card", 0.28) if checked else theme.c("line"),
                    width=1)
            checkbox(c, (PAD + 14, y + 17, PAD + 34, y + 37), checked, theme)
            # 圆形底盘 + 18px 图标：图标墨迹的几何中心与圆心严格重合
            cx0, cy0 = PAD + 59, y + ROW_H / 2
            c.ellipse((cx0 - 15, cy0 - 15, cx0 + 15, cy0 + 15),
                      fill=theme.c("accent_soft") if checked else theme.c("panel_alt"))
            c.paste(device_glyph(dev.kind, self.px(18),
                                 theme.c("accent") if checked else theme.c("sub"),
                                 weight=0.115),
                    (cx0 - 9, cy0 - 9))
            c.text((PAD + 84, y + 19), dev.name, f.get(13, "semibold"),
                   theme.c("text") if checked else theme.c("sub"), "lm", tracking=0.1)
            c.text((PAD + 84, y + 35), f"{dev.kind_label} · {dev.transport}", f.get(10),
                   theme.c("faint"), "lm")
            right = W - PAD - 14
            if dev.status == ONLINE and dev.level is not None:
                color = level_color(theme, dev.level, dev.charging, dev.status)
                pct = f"{dev.level}%"
                font = f.get(13, "semibold", True)
                c.text((right, y + 27), pct, font, color, "rm", tracking=-0.2)
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
                c.text(((box[0] + box[2]) / 2, (box[1] + box[3]) / 2), label, font, fg, "mm")
            hits.append((row_rect, f"dev:{dev.key}", "hand"))
            y += ROW_H + ROW_GAP

        # ------- 显示与刷新
        y += 10
        c.text((PAD, y + 12), "显示与刷新", f.get(12.5, "semibold"), theme.c("text"),
               "lm", tracking=0.3)
        y += 26
        for spec in self._display_rows():
            y = self._row(c, hits, y, spec)

        # ------- 常规
        y += 10
        c.text((PAD, y + 12), "常规", f.get(12.5, "semibold"), theme.c("text"),
               "lm", tracking=0.3)
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
        return (devices, cfg, self.app.selected_keys(), self.app.theme.dark,
                round(self.app.scale, 3))

    def _row(self, c: Canvas, hits, y: float, spec: tuple) -> float:
        if spec[0] == "seg":
            return self._seg_row(c, hits, y, *spec[1:])
        return self._toggle_row(c, hits, y, *spec[1:])

    def _seg_row(self, c: Canvas, hits, y, label, options, index, width, ctrl_id) -> float:
        theme = self.app.theme
        f = self.app.fonts
        center = y + 23
        c.text((PAD, center), label, f.get(12), theme.c("text"), "lm", tracking=0.2)
        box = (W - PAD - width, y + 9, W - PAD, y + 37)
        rects = segmented(c, box, options, index, f, theme)
        for i, rect in enumerate(rects):
            hits.append((rect, f"{ctrl_id}:{i}", "hand"))
        c.line([(PAD, y + 46), (W - PAD, y + 46)], theme.c("line", 150), 0.8)
        return y + 46

    def _toggle_row(self, c: Canvas, hits, y, label, desc, on, ctrl_id) -> float:
        theme = self.app.theme
        f = self.app.fonts
        center = y + 23
        c.text((PAD, center - 8), label, f.get(12), theme.c("text"), "lm", tracking=0.2)
        c.text((PAD, center + 9), desc, f.get(10), theme.c("faint"), "lm")
        box = (W - PAD - 40, center - 10, W - PAD, center + 10)
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

    def _all_hits(self):
        """页眉/页脚的固定按钮 + 当前可见的滚动控件。

        固定按钮不随滚动动；滚动控件的矩形由 _visible_body_hits() 按
        当前 scroll 换算过，并且已经裁到内容可视区内，滚出去的不会误命中。
        """
        fixed = [
            (self._close_box(), "close", "hand"),
            (self._reset_box(), "reset", "hand"),
            (self._done_box(), "done", "hand"),
        ]
        return fixed + list(self._visible_body_hits())

    def _hit_rect(self, hid: str):
        for rect, h, _ in self._visible_body_hits():
            if h == hid:
                return rect
        return None

    # ------------------------------------------------------------------
    def show(self, x=None, y=None, animate=True, activate=True) -> None:
        self._body_cache = None
        self._fade_cache = None
        self.layout()
        if x is None or y is None:
            x, y = self.app.settings_position(self.lw, self.lh)
        super().show(x, y, animate, activate)

    def hide(self) -> None:
        if self._scroll_timer:
            k.KillTimer(self.hwnd, 3)
            self._scroll_timer = 0
        super().hide()

    def on_wheel(self, delta: int) -> None:
        max_scroll = max(0.0, self._content_h - self._body_h + 6)
        if max_scroll <= 0:
            return
        self._scroll_target = max(0.0, min(max_scroll,
                                           self._scroll_target - (delta / 120) * SCROLL_STEP))
        # 滚轮消息本身只推进目标值，真正的重绘交给 16ms 定时器逐帧缓动。
        # 这样连发十几个滚轮事件也只会排队成一次平滑滑动，不会一帧画一次。
        if not self._scroll_timer:
            self._scroll_timer = k.SetTimer(self.hwnd, 3, SCROLL_FRAME_MS, None)

    def _paint_scroll(self) -> bool:
        """缓动一帧，返回是否已经停稳。"""
        self._last_scroll_paint = time.perf_counter()
        delta = self._scroll_target - self.scroll
        if abs(delta) <= 0.75:          # 不足一像素就直接落位，肉眼看不出来
            self.scroll = self._scroll_target
            # 停稳这一帧也要重绘：render() 会按最终位置重建命中区域，
            # 否则最后那不到 1px 的偏差会让点击区域停在上一个位置。
            self.invalidate()
            return True
        # 指数缓动：越接近目标步子越小，停下来的那一帧不会"顿"一下
        self.scroll += delta * SCROLL_EASE
        self.invalidate()
        return False

    def on_timer(self, timer_id: int) -> None:
        if timer_id == 3:
            if self._paint_scroll():
                k.KillTimer(self.hwnd, 3)
                self._scroll_timer = 0
            return
        super().on_timer(timer_id)

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
