"""任务栏悬浮条：常驻显示已选设备电量。"""
from __future__ import annotations

from ..draw import Canvas, device_glyph, level_color
from ..model import ERROR, OFFLINE, ONLINE, UNSUPPORTED
from .base import LayerWindow

H = 34
PAD = 12
MAX_CHIPS = 4


class BarWindow(LayerWindow):
    CLASS = "TrayBatteryBar"

    def __init__(self, app) -> None:
        super().__init__(app)
        self.pad = PAD

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
        return max(120, w)

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
        self.set_size(pw + PAD * 2, H + PAD * 2)
        return pw, H

    def render(self):
        old_w = self.lw
        pw, ph = self.layout()
        if self.visible and abs(old_w - self.lw) > 0.5 and not self.app.config["bar_pos"]:
            self.pos = self.app.bar_default_position(self.w, self.h)
        theme = self.app.theme
        f = self.app.fonts
        c = Canvas((self.lw, self.lh), self.scale, 2)
        panel = (PAD, PAD, PAD + pw, PAD + ph)
        c.shadow(panel, 11, 7, (0, 0, 0, 255), 46 if not theme.dark else 100, dy=2)
        fill = theme.mix("card_hover", "panel", 0.85) if self.hover == "bar" else theme.c("panel", 250)
        c.rrect(panel, 11, fill=fill, outline=theme.c("line"), width=1)

        devs, extra = self.chips()
        hits = [(panel, "bar", "hand")]
        if not devs:
            c.text((PAD + pw / 2, PAD + ph / 2), "未选择设备", f.get(10.5), theme.c("faint"), "mm")
            self.set_hits(hits)
            return c.finish()

        x = PAD + 12
        cy = PAD + ph / 2
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

    # ------------------------------------------------------------------
    def place_default(self) -> None:
        pos = self.app.config["bar_pos"]
        if pos and self.app.is_reachable(pos[0], pos[1], self.w, self.h):
            self.place(int(pos[0]), int(pos[1]))
            return
        x, y = self.app.bar_default_position(self.w, self.h)
        self.place(x, y)

    def show(self, x=None, y=None, animate=False, activate=False) -> None:
        self.layout()
        if x is None or y is None:
            self.place_default()
            x, y = self.pos
        super().show(x, y, animate, activate)

    def is_drag_handle(self, hid: str) -> bool:
        return hid == "bar"

    def on_drag_end(self) -> None:
        self.app.config["bar_pos"] = [self.pos[0], self.pos[1]]
        self.app.config.save()

    def on_click(self, hid: str) -> None:
        if hid == "bar":
            self.app.toggle_flyout_near_bar(self)
