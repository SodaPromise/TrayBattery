"""分层窗口基类：无边框、圆角、阴影、悬停与拖拽。"""
from __future__ import annotations

import ctypes
from ctypes import wintypes as w

from PIL import Image, ImageDraw

from .. import win32 as k
from ..draw import Canvas
from ..theme import Fonts


class LayerWindow:
    CLASS = "TrayBatteryLayerWindow"

    def __init__(self, app) -> None:
        self.app = app
        self.pad = 0
        self.lw = 10.0
        self.lh = 10.0
        self.w = 10
        self.h = 10
        self.hwnd = k.create_window(
            self.CLASS, 10, 10,
            k.WS_EX_LAYERED | k.WS_EX_TOOLWINDOW | k.WS_EX_TOPMOST,
        )
        k.bind_window(self.hwnd, self)
        self.canvas = k.LayeredCanvas()
        self.visible = False
        self.alpha = 255
        self.hover: str | None = None
        self.pressed: str | None = None
        self.hits: list[tuple[tuple[int, int, int, int], str, str | None]] = []
        self.pos = (0, 0)
        self._dirty = True
        self._dragging = False
        self._drag_offset = (0, 0)
        self._drag_moved = False
        self._tracking_leave = False
        self._anim_timer = 0
        self._measure = ImageDraw.Draw(Image.new("RGBA", (4, 4)))

    # ------------------------------------------------------------------ 尺寸
    @property
    def scale(self) -> float:
        return self.app.scale

    def px(self, v: float) -> int:
        return max(1, int(round(v * self.scale)))

    def measure(self, text: str, font) -> float:
        return self._measure.textlength(text, font=font) / self.scale

    def set_size(self, w_: int, h_: int) -> None:
        if (w_, h_) != (self.lw, self.lh):
            self.lw, self.lh = float(w_), float(h_)
            self.w = max(1, int(round(self.lw * self.scale)))
            self.h = max(1, int(round(self.lh * self.scale)))
            self._dirty = True

    def set_hits(self, hits) -> None:
        s = self.scale
        self.hits = [
            (tuple(int(round(v * s)) for v in rect), hid, cur) for rect, hid, cur in hits
        ]

    # ------------------------------------------------------------------ 绘制
    def render(self) -> Image.Image:
        raise NotImplementedError

    def paint(self, alpha: int = 255) -> None:
        image = self.render()
        if image.size != (self.w, self.h):
            self.w, self.h = image.size
        self.canvas.upload(image)
        self.canvas.present(self.hwnd, self.pos[0], self.pos[1], alpha)
        self._dirty = False

    def invalidate(self) -> None:
        if self.visible:
            self.paint(self.alpha)

    # ------------------------------------------------------------------ 显隐
    def place(self, x: int, y: int) -> None:
        self.pos = (int(x), int(y))
        k.SetWindowPos(self.hwnd, None, self.pos[0], self.pos[1], self.w, self.h,
                       k.SWP_NOZORDER | k.SWP_NOACTIVATE)

    def show(self, x: int | None = None, y: int | None = None, animate: bool = True,
             activate: bool = True) -> None:
        if x is not None and y is not None:
            self.pos = (int(x), int(y))
        self._dirty = True
        self.visible = True
        flags = k.SWP_NOACTIVATE if not activate else 0
        k.SetWindowPos(self.hwnd, k.HWND_TOPMOST, self.pos[0], self.pos[1], self.w, self.h,
                       k.SWP_SHOWWINDOW | flags)
        k.ShowWindow(self.hwnd, k.SW_SHOWNOACTIVATE if not activate else k.SW_SHOW)
        if activate:
            k.SetForegroundWindow(self.hwnd)
        if animate:
            self.alpha = 0
            self.paint(0)
            k.SetTimer(self.hwnd, 1, 15, None)
        else:
            self.alpha = 255
            self.paint(255)

    def hide(self) -> None:
        if not self.visible:
            return
        k.KillTimer(self.hwnd, 1)
        k.KillTimer(self.hwnd, 2)
        self.visible = False
        self.alpha = 255
        k.ShowWindow(self.hwnd, k.SW_HIDE)

    def toggle(self, x: int | None = None, y: int | None = None) -> None:
        if self.visible:
            self.hide()
        else:
            self.show(x, y)

    # ------------------------------------------------------------------ 消息
    def on_message(self, msg, wp, lp):
        if msg == k.WM_MOUSEMOVE:
            self._on_mouse_move()
            return 0
        if msg == k.WM_LBUTTONDOWN:
            self._on_mouse_down()
            return 0
        if msg == k.WM_LBUTTONUP:
            self._on_mouse_up()
            return 0
        if msg == k.WM_MOUSEWHEEL:
            delta = ctypes.c_short((wp >> 16) & 0xFFFF).value
            self.on_wheel(delta)
            return 0
        if msg == k.WM_MOUSELEAVE:
            if self.hover is not None:
                self.hover = None
                self.invalidate()
            self._tracking_leave = False
            return 0
        if msg == k.WM_SETCURSOR:
            cur = self.cursor_at(*k.cursor_pos())
            if cur is not None:
                k.SetCursor(k._load_cursor(cur))
                return 1
            return 0
        if msg == k.WM_KEYDOWN:
            if wp == 0x1B:  # ESC
                self.hide()
                return 0
        if msg == k.WM_TIMER:
            self.on_timer(int(wp))
            return 0
        if msg == k.WM_ACTIVATE:
            if (wp & 0xFFFF) == k.WA_INACTIVE:
                self.on_deactivate()
            return 0
        if msg == k.WM_DPICHANGED:
            dpi = (wp & 0xFFFF) or 96
            self.app.on_dpi_changed(dpi)
            return 0
        if msg == k.WM_DESTROY:
            self.on_destroy()
            return 0
        return k.DefWindowProcW(self.hwnd, msg, wp, lp)

    # ------------------------------------------------------------------ 交互
    def local_cursor(self) -> tuple[int, int]:
        x, y = k.cursor_pos()
        pt = k.POINT(x, y)
        k.ScreenToClient(self.hwnd, ctypes.byref(pt))
        return pt.x, pt.y

    def cursor_at(self, sx: int, sy: int) -> int | None:
        lx = sx - self.pos[0]
        ly = sy - self.pos[1]
        for (x0, y0, x1, y1), _id, cursor in reversed(self.hits):
            if x0 <= lx <= x1 and y0 <= ly <= y1:
                return {"hand": k.IDC_HAND, "size": k.IDC_SIZENS}.get(cursor or "")
        return None

    def hit_at(self) -> tuple[str | None, tuple | None]:
        x, y = self.local_cursor()
        for rect, hid, _cursor in reversed(self.hits):
            if rect[0] <= x <= rect[2] and rect[1] <= y <= rect[3]:
                return hid, rect
        return None, None

    def _on_mouse_move(self) -> None:
        if not self._tracking_leave:
            tme = k.TRACKMOUSEEVENT(ctypes.sizeof(k.TRACKMOUSEEVENT), k.TME_LEAVE, self.hwnd, k.HOVER_DEFAULT)
            k.TrackMouseEvent(ctypes.byref(tme))
            self._tracking_leave = True
        if self._dragging:
            x, y = k.cursor_pos()
            nx, ny = x - self._drag_offset[0], y - self._drag_offset[1]
            if abs(nx - self.pos[0]) + abs(ny - self.pos[1]) > 2:
                self._drag_moved = True
            self.pos = (nx, ny)
            k.SetWindowPos(self.hwnd, None, nx, ny, self.w, self.h, k.SWP_NOZORDER | k.SWP_NOACTIVATE)
            return
        hid, _rect = self.hit_at()
        if hid != self.hover:
            self.hover = hid
            self.invalidate()

    def _on_mouse_down(self) -> None:
        hid, rect = self.hit_at()
        self.pressed = hid
        if hid and self.is_drag_handle(hid):
            self._dragging = True
            self._drag_moved = False
            x, y = k.cursor_pos()
            self._drag_offset = (x - self.pos[0], y - self.pos[1])
            k.SetCapture(self.hwnd)
            return
        if hid:
            self.invalidate()

    def _on_mouse_up(self) -> None:
        if self._dragging:
            self._dragging = False
            k.ReleaseCapture()
            if self._drag_moved:
                self.on_drag_end()
                return
            hid = self.pressed
            self.pressed = None
            if hid and hid == self.hit_at()[0]:
                self.on_click(hid)
            return
        hid, _rect = self.hit_at()
        was = self.pressed
        self.pressed = None
        if hid and hid == was:
            self.on_click(hid)
        else:
            self.invalidate()

    def on_wheel(self, delta: int) -> None:
        pass

    def on_click(self, hid: str) -> None:
        pass

    def on_timer(self, timer_id: int) -> None:
        if timer_id == 1:
            self.alpha = min(255, self.alpha + 42)
            self.paint(self.alpha)
            if self.alpha >= 255:
                k.KillTimer(self.hwnd, 1)

    def on_deactivate(self) -> None:
        pass

    def on_theme_changed(self) -> None:
        """主题或缩放变化时重建与颜色/字体相关的缓存。"""

    def on_destroy(self) -> None:
        k.KillTimer(self.hwnd, 1)
        k.KillTimer(self.hwnd, 2)
        self.canvas.close()
        k.unbind_window(self.hwnd)
        self.hwnd = None

    def is_drag_handle(self, hid: str) -> bool:
        return False

    def on_drag_end(self) -> None:
        pass

    def destroy(self) -> None:
        if self.hwnd:
            k.DestroyWindow(self.hwnd)


# ------------------------------------------------------------------ 控件绘制
def toggle(c: Canvas, box, on: bool, theme, hover: bool = False) -> None:
    x0, y0, x1, y1 = box
    r = (y1 - y0) / 2
    c.rrect(box, r, fill=theme.c("accent") if on else theme.c("track"))
    knob_r = r - 2.5
    cx = (x1 - r) if on else (x0 + r)
    c.ellipse((cx - knob_r, (y0 + y1) / 2 - knob_r, cx + knob_r, (y0 + y1) / 2 + knob_r),
              fill=theme.c("overlay"))


def checkbox(c: Canvas, box, checked: bool, theme, hover: bool = False) -> None:
    x0, y0, x1, y1 = box
    if checked:
        c.rrect(box, 5.5, fill=theme.c("accent"))
        c.line([(x0 + (x1 - x0) * 0.26, y0 + (y1 - y0) * 0.52),
                (x0 + (x1 - x0) * 0.44, y0 + (y1 - y0) * 0.70),
                (x0 + (x1 - x0) * 0.76, y0 + (y1 - y0) * 0.32)],
               fill=theme.c("accent_text"), width=1.7)
    else:
        c.rrect(box, 5.5, fill=theme.c("overlay"), outline=theme.c("line"), width=1.2)


def segmented(c: Canvas, box, options: list[str], index: int, fonts: Fonts, theme,
              hover_index: int | None = None) -> list[tuple]:
    """绘制分段控件，返回每段的命中矩形（图片坐标）。"""
    x0, y0, x1, y1 = box
    c.rrect(box, 7, fill=theme.c("panel_alt"))
    seg_w = (x1 - x0) / len(options)
    rects = []
    for i, opt in enumerate(options):
        sx0 = x0 + seg_w * i
        sx1 = sx0 + seg_w
        rect = (sx0, y0, sx1, y1)
        rects.append(rect)
        if i == index:
            c.rrect((sx0 + 2, y0 + 2, sx1 - 2, y1 - 2), 5.5, fill=theme.c("overlay"))
            c.rrect((sx0 + 2, y0 + 2, sx1 - 2, y1 - 2), 5.5, outline=theme.c("line"), width=0.8)
        c.text(((sx0 + sx1) / 2, (y0 + y1) / 2 + 0.5), opt,
               fonts.get(11, "semibold" if i == index else "regular"),
               theme.c("text") if i == index else theme.c("sub"), "mm")
    return rects


def gear_icon(size: int, color) -> Image.Image:
    s = size * 4
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    cx = cy = s / 2
    import math
    for i in range(8):
        a = math.pi / 4 * i
        r1, r2 = s * 0.24, s * 0.42
        w_ = max(2, int(s * 0.085))
        d.line([(cx + math.cos(a) * r1, cy + math.sin(a) * r1),
                (cx + math.cos(a) * r2, cy + math.sin(a) * r2)], fill=color, width=w_)
    d.ellipse((cx - s * 0.30, cy - s * 0.30, cx + s * 0.30, cy + s * 0.30),
              outline=color, width=max(2, int(s * 0.10)))
    d.ellipse((cx - s * 0.075, cy - s * 0.075, cx + s * 0.075, cy + s * 0.075), fill=color)
    return im.resize((size, size), Image.LANCZOS)
