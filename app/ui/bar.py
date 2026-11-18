"""任务栏电量条：做成任务栏原生的状态项。

设计约束（对齐 Windows 11 任务栏自身的样子）：
* 没有底色、没有描边、没有阴影，直接"印"在任务栏上，随任务栏深浅自动换墨色；
* 只用黑白，低于 10% 才用系统的告警红（和系统电池图标一致）；
* 尺寸、间距、字号取任务栏托盘图标的规格，垂直居中于任务栏；
* 鼠标移上去才浮出 Windows 那种圆角高亮，点一下弹出面板，右键出菜单；
* 可以在任务栏空白段上左右拖动并记住位置（Win11 自己已经不让拖图标了，
  这里给电量条补上这个手感）。
"""
from __future__ import annotations

import ctypes

from .. import win32 as k
from ..draw import Canvas, charge_bolt, device_glyph
from ..model import ERROR, OFFLINE, ONLINE, UNSUPPORTED
from ..theme import bar_skin, card_skin, forget_bar_skin
from .base import LayerWindow

GLYPH = 16          # 与托盘图标同尺寸（逻辑像素）
GAP_GLYPH = 5       # 图标与数字之间
GAP_CHIP = 12       # 两台设备之间
PAD_X = 8           # 左右内边距
ITEM_H = 28         # 悬停高亮高度
PAD = 12            # 没有任务栏可嵌时的悬浮留白
H_FLOAT = 32
MAX_CHIPS = 4
MAX_SHIFT = 240     # 最多能沿任务栏向左拖多远（逻辑像素）
SNAP_HOME = 14      # 离默认位置多近就吸回去


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

    @staticmethod
    def _label(dev) -> str:
        if dev.status == ONLINE and dev.level is not None:
            return f"{dev.level}%"
        return {OFFLINE: "离线", UNSUPPORTED: "不支持", ERROR: "读取失败"}.get(dev.status, "—")

    def _chip_specs(self):
        """(设备, 文本, 字体, 文本宽度, 颜色)"""
        f = self.app.fonts
        skin = self.skin
        specs = []
        for dev in self.chips()[0]:
            numeric = dev.status == ONLINE and dev.level is not None
            font = f.get(11.5, "semibold" if numeric else "regular", numeric)
            label = self._label(dev)
            specs.append((dev, label, font, self.measure(label, font),
                          self._dev_color(dev, skin)))
        return specs, self.chips()[1]

    def _dev_color(self, dev, skin=None):
        if self.embedded:
            return (skin or self.skin).level_color(dev.level, dev.status, dev.charging)
        return card_skin(self.app.theme).level_color(dev.level, dev.status, dev.charging)

    def content_width(self) -> float:
        specs, extra = self._chip_specs()
        if not specs:
            return 84.0
        w = PAD_X * 2 + sum(GLYPH + GAP_GLYPH + s[3] for s in specs)
        w += GAP_CHIP * max(0, len(specs) - 1)
        if extra:
            w += GAP_CHIP + 15
        return max(56.0, w)

    # ------------------------------------------------------------------ 皮肤
    @property
    def skin(self):
        return bar_skin(self._sample_box())

    def _sample_box(self):
        """在电量条左侧取一小条任务栏做亮度采样（那里一定是任务栏本身）。"""
        tray = k.taskbar_rect()
        if not tray:
            return None
        tn = k.tray_area_rect()
        s = self.scale
        right = min(self.pos[0] - int(round(6 * s)),
                    (tn.left if tn else tray.right) - int(round(18 * s)))
        left = max(tray.left + int(round(4 * s)), right - int(round(80 * s)))
        if right - left < 10:
            return None
        return (left, tray.top + int(round(8 * s)), right, tray.bottom - int(round(8 * s)))

    def on_theme_changed(self) -> None:
        forget_bar_skin()

    # ------------------------------------------------------------------ 排版
    def layout(self) -> tuple[float, float]:
        w = self.content_width()
        if self.embedded:
            self.pad = 0
            h = self._taskbar_height()
            self.set_size(w, h)
            return w, h
        self.pad = PAD
        self.set_size(w + PAD * 2, H_FLOAT + PAD * 2)
        return w, H_FLOAT

    def _taskbar_height(self) -> float:
        tray = k.taskbar_rect()
        if tray and tray.bottom > tray.top:
            return max(24.0, (tray.bottom - tray.top) / self.scale)
        return 40.0

    # ------------------------------------------------------------------ 绘制
    def render(self):
        w, h = self.layout()
        theme = self.app.theme
        f = self.app.fonts
        skin = self.skin
        specs, extra = self._chip_specs()
        c = Canvas((self.lw, self.lh), self.scale, 2)

        if self.embedded:
            # alpha=1 的全幅底：分层窗口是按 alpha 做命中测试的，
            # 不垫这一层，鼠标只能点中字和图标本身，悬停高亮就出不来。
            c.rrect((0, 0, self.lw, self.lh), 0, fill=(0, 0, 0, 1))
            cy = self.lh / 2
            box = (0, cy - ITEM_H / 2, self.lw, cy + ITEM_H / 2)
            if self.pressed == "bar":
                c.rrect(box, 4, fill=skin.pressed)
            elif self.hover == "bar":
                c.rrect(box, 4, fill=skin.hover)
            ox = 0.0
        else:
            panel = (PAD, PAD, PAD + w, PAD + h)
            c.shadow(panel, 11, 7, (0, 0, 0, 255), 46 if not theme.dark else 100, dy=2)
            fill = (theme.mix("card_hover", "panel", 0.85) if self.hover == "bar"
                    else theme.c("panel", 250))
            c.rrect(panel, 11, fill=fill, outline=theme.c("line"), width=1)
            ox = PAD
            cy = PAD + h / 2

        if not specs:
            c.text((ox + w / 2, cy), "未选择设备", f.get(10.5), self._dim_color(), "mm")
            self._set_hits(w)
            return c.finish()

        x = ox + PAD_X
        for i, (dev, label, font, width, color) in enumerate(specs):
            if i:
                x += GAP_CHIP
            c.paste(device_glyph(dev.kind, self.px(GLYPH), color, weight=0.10),
                    (x, cy - GLYPH / 2))
            if dev.charging and dev.status == ONLINE:
                c.paste(charge_bolt(self.px(9), color),
                        (x + GLYPH - 5.5, cy + GLYPH / 2 - 5))
            # +0.5：小字号下把基线压回视觉中心
            c.text((x + GLYPH + GAP_GLYPH, cy + 0.5), label, font, color, "lm")
            x += GLYPH + GAP_GLYPH + width

        if extra:
            c.text((x + GAP_CHIP, cy + 0.5), f"+{extra}", f.get(10, "semibold"),
                   self._dim_color(), "lm")

        self._set_hits(w)
        return c.finish()

    def _dim_color(self):
        return self.skin.dim if self.embedded else card_skin(self.app.theme).dim

    def _set_hits(self, w: float) -> None:
        # 任务栏上原生元素用的是普通箭头，不用小手
        if self.embedded:
            cy = self.lh / 2
            self.set_hits([((0, cy - ITEM_H / 2, self.lw, cy + ITEM_H / 2), "bar", None)])
        else:
            self.set_hits([((PAD, PAD, PAD + w, PAD + H_FLOAT), "bar", "hand")])

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
            forget_bar_skin()
        self.embedded = True
        return True

    def unembed(self) -> None:
        if self.embedded or self.parent_hwnd:
            k.set_child(self.hwnd, None)
            self.parent_hwnd = None
            self.embedded = False
            forget_bar_skin()

    def _gap_px(self) -> int:
        return max(2, int(round(8 * self.scale)))

    def _band(self) -> tuple[int, int] | None:
        """电量条在任务栏上允许占用的横向区间（屏幕坐标，物理像素）。"""
        tray = k.taskbar_rect()
        if not tray:
            return None
        tn = k.tray_area_rect()
        anch = tn.left if tn else tray.right - int(round(150 * self.scale))
        hi = anch - self._gap_px() - self.w
        lo = max(hi - int(round(MAX_SHIFT * self.scale)),
                 tray.left + int(round(96 * self.scale)))
        return (min(lo, hi), hi)

    def place_taskbar(self) -> bool:
        """贴到托盘区左边缘，垂直居中于任务栏。"""
        tray = k.taskbar_rect()
        if not tray:
            return False
        height = tray.bottom - tray.top
        if tray.right - tray.left <= height:      # 竖排任务栏不做嵌入
            return False
        band = self._band()
        if band is None:
            return False
        x = band[1] - int(round(self.offset() * self.scale))
        y = tray.top + max(0, (height - self.h) // 2)
        self.place(x, y)
        return True

    # ------------------------------------------------------------------ 拖动
    def offset(self) -> int:
        try:
            value = int(self.app.config["bar_offset"] or 0)
        except (TypeError, ValueError):
            value = 0
        return max(0, min(MAX_SHIFT, value))

    def drag_target(self, nx: int, ny: int) -> tuple[int, int]:
        if not self.embedded:
            return nx, ny
        tray = k.taskbar_rect()
        band = self._band()
        if not tray or band is None:
            return nx, ny
        nx = max(band[0], min(band[1], nx))
        ny = tray.top + max(0, ((tray.bottom - tray.top) - self.h) // 2)
        return nx, ny

    def on_drag_end(self) -> None:
        if not self.embedded:
            self.app.config["bar_pos"] = [self.pos[0], self.pos[1]]
            self.app.config.save()
            return
        band = self._band()
        if band is None:
            return
        off = (band[1] - self.pos[0]) / self.scale
        # 靠近默认位置就吸回去，否则按 4px 对齐，手感更"卡槽"
        off = 0 if off < SNAP_HOME else int(round(off / 4) * 4)
        self.app.config["bar_offset"] = max(0, min(MAX_SHIFT, off))
        self.app.config.save()
        self.layout()
        self.place_taskbar()
        self.invalidate()

    def reset_offset(self) -> None:
        self.app.config["bar_offset"] = 0
        self.app.config.save()
        self.layout()
        self.place_taskbar()
        self.invalidate()

    def cursor_at(self, sx: int, sy: int) -> int | None:
        if self._dragging:
            return k.IDC_SIZEWE
        return super().cursor_at(sx, sy)

    # ------------------------------------------------------------------ 定位
    def _present(self, image, alpha: int) -> None:
        self.canvas.upload(image)
        if self.embedded:
            # 子窗口由 place() 负责位置，交给 ULW 定位会与父窗口坐标系冲突
            self.canvas.present(self.hwnd, alpha=alpha)
        else:
            self.canvas.present(self.hwnd, self.pos[0], self.pos[1], alpha)

    def paint(self, alpha: int = 255) -> None:
        # 设备增减会改变宽度；电量条是右对齐的，得先按新宽度重新贴边再上传，
        # 否则会先向右长出去、压住托盘图标一帧。
        if self.embedded and self.visible:
            self.layout()
            self.place_taskbar()
        super().paint(alpha)

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

    def _apply_geometry(self) -> None:
        if self.embed():
            self.layout()
            if self.place_taskbar():
                return
        self.unembed()
        self.layout()
        self.place_default()

    def show(self, x=None, y=None, animate=False, activate=False) -> None:
        self._apply_geometry()
        super().show(animate=False, activate=False)

    def refresh_position(self) -> None:
        """任务栏重建 / 分辨率变化 / DPI 变化后重新贴合。"""
        if not self.visible:
            return
        self._apply_geometry()
        self.invalidate()

    # ------------------------------------------------------------------
    def is_drag_handle(self, hid: str) -> bool:
        return hid == "bar"

    def on_click(self, hid: str) -> None:
        if hid == "bar":
            self.app.toggle_flyout_near_bar(self)

    def on_right_click(self) -> None:
        self.app.show_menu()
