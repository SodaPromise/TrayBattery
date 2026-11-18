"""Pillow 绘制工具：抗锯齿画布、电池图标、设备图标。"""
from __future__ import annotations

from PIL import Image, ImageDraw, ImageFilter

from .theme import Theme


class Canvas:
    """设计坐标（逻辑像素）× zoom 得到物理像素，形状再按 ss 超采样，文字按物理分辨率绘制。"""

    def __init__(self, size: tuple[int, int], zoom: float = 1.0, ss: int = 2) -> None:
        self.zoom = zoom
        self.lw, self.lh = float(size[0]), float(size[1])
        self.w = max(1, int(round(self.lw * zoom)))
        self.h = max(1, int(round(self.lh * zoom)))
        self.ss = ss
        self.img = Image.new("RGBA", (self.w * ss, self.h * ss), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.img)
        self._ops: list[tuple] = []

    # -- 坐标换算
    def S(self, v: float) -> int:
        return int(round(v * self.zoom * self.ss))

    def box(self, b) -> tuple[int, int, int, int]:
        return tuple(int(round(v * self.zoom * self.ss)) for v in b)

    # -- 形状
    def rrect(self, b, r: float, fill=None, outline=None, width: float = 1.0):
        self.d.rounded_rectangle(
            self.box(b), radius=max(0, self.S(r)), fill=fill, outline=outline,
            width=max(1, self.S(width)) if outline else 1,
        )

    def ellipse(self, b, fill=None, outline=None, width: float = 1.0):
        self.d.ellipse(
            self.box(b), fill=fill, outline=outline,
            width=max(1, self.S(width)) if outline else 1,
        )

    def line(self, pts, fill, width: float = 1.0):
        self.d.line([(self.S(x), self.S(y)) for x, y in pts], fill=fill,
                    width=max(1, self.S(width)), joint="curve")

    def shadow(self, b, r: float, blur: float, color, alpha: int, dy: float = 0) -> None:
        pad = int(blur * 2.2 * self.ss)
        w_, h_ = self.img.size
        layer = Image.new("L", (w_, h_), 0)
        d = ImageDraw.Draw(layer)
        box = self.box((b[0], b[1] + dy, b[2], b[3] + dy))
        d.rounded_rectangle(box, radius=self.S(r), fill=alpha)
        layer = layer.filter(ImageFilter.GaussianBlur(max(0.5, blur * self.zoom * self.ss)))
        tint = Image.new("RGBA", (w_, h_), color)
        tint.putalpha(layer)
        self.img.alpha_composite(tint)

    # -- 文字 / 位图（延后绘制）
    def text(self, xy, s: str, font, fill, anchor: str = "lm") -> None:
        self._ops.append(("text", (xy[0] * self.zoom, xy[1] * self.zoom), s, font, fill, anchor))

    def paste(self, im: Image.Image, xy) -> None:
        self._ops.append(("paste", (int(round(xy[0] * self.zoom)), int(round(xy[1] * self.zoom))), im))

    def finish(self) -> Image.Image:
        img = self.img.resize((self.w, self.h), Image.LANCZOS) if self.ss != 1 else self.img
        d = ImageDraw.Draw(img)
        for op in self._ops:
            if op[0] == "text":
                _, xy, s, font, fill, anchor = op
                d.text(xy, s, font=font, fill=fill, anchor=anchor)
            else:
                _, xy, im = op
                if im.mode != "RGBA":
                    im = im.convert("RGBA")
                img.alpha_composite(im, xy)
        return img


def ellipsize(draw: ImageDraw.ImageDraw, text: str, font, max_w: float) -> str:
    if not text:
        return ""
    if draw.textlength(text, font=font) <= max_w:
        return text
    ell = "…"
    while text and draw.textlength(text + ell, font=font) > max_w:
        text = text[:-1]
    return text + ell


# ------------------------------------------------------------------ 电池
def battery_glyph(size: int, level: int | None, color, charging: bool = False,
                  outline=None, track=None) -> Image.Image:
    """横向电池图标，返回 size×size 的 RGBA。"""
    px = size * 4
    im = Image.new("RGBA", (px, px), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    stroke = max(2, int(px * 0.085))
    body_w = int(px * 0.82)
    body_h = int(px * 0.50)
    x0 = int(px * 0.03)
    y0 = (px - body_h) // 2
    radius = int(body_h * 0.30)
    cap_w = max(2, int(px * 0.065))
    cap_h = int(body_h * 0.34)
    cap_x = x0 + body_w + int(px * 0.02)
    cap_y = y0 + (body_h - cap_h) // 2
    d.rounded_rectangle((x0, y0, x0 + body_w, y0 + body_h), radius=radius,
                        outline=outline or color, width=stroke)
    d.rounded_rectangle((cap_x, cap_y, cap_x + cap_w, cap_y + cap_h),
                        radius=max(1, cap_w // 2), fill=outline or color)
    if level is not None and not charging:
        inner_pad = max(2, stroke // 2 + 1)
        avail = body_w - inner_pad * 2
        frac = max(0.0, min(1.0, level / 100.0))
        if frac > 0:
            fill_w = max(int(avail * frac), max(2, inner_pad))
            d.rounded_rectangle(
                (x0 + inner_pad, y0 + inner_pad, x0 + inner_pad + fill_w, y0 + body_h - inner_pad),
                radius=max(1, radius - inner_pad), fill=color,
            )
    if charging:
        cx = x0 + body_w // 2
        cy = y0 + body_h // 2
        s_ = body_h * 0.62
        pts = [
            (cx + s_ * 0.10, cy - s_ * 0.55),
            (cx - s_ * 0.32, cy + s_ * 0.06),
            (cx - s_ * 0.02, cy + s_ * 0.06),
            (cx - s_ * 0.14, cy + s_ * 0.58),
            (cx + s_ * 0.34, cy - s_ * 0.08),
            (cx + s_ * 0.02, cy - s_ * 0.08),
        ]
        d.polygon(pts, fill=color)
    return im.resize((size, size), Image.LANCZOS)


def level_color(theme: Theme, level: int | None, charging: bool = False, status: str = "online"):
    if status != "online":
        return theme.c("faint")
    if charging:
        return theme.c("accent")
    if level is None:
        return theme.c("faint")
    if level <= 15:
        return theme.c("red")
    if level <= 35:
        return theme.c("amber")
    return theme.c("green")


# ------------------------------------------------------------------ 设备图标
def device_glyph(kind: str, px: int, color, weight: float = 0.085) -> Image.Image:
    """按 4 倍绘制再缩小，得到平滑的小图标。weight 是线宽占图标边长的比例。"""
    s = px * 4
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    lw = max(2, int(round(s * weight)))

    if kind == "mouse":
        # 机身
        body = (s * 0.29, s * 0.06, s * 0.71, s * 0.94)
        d.rounded_rectangle(body, radius=int(s * 0.21), outline=color, width=lw)
        # 中缝
        d.line([(s * 0.5, s * 0.10), (s * 0.5, s * 0.40)], fill=color, width=lw)
        # 滚轮
        d.rounded_rectangle(
            (s * 0.455, s * 0.20, s * 0.545, s * 0.33),
            radius=int(s * 0.045), fill=color,
        )
    elif kind == "keyboard":
        d.rounded_rectangle(
            (s * 0.04, s * 0.26, s * 0.96, s * 0.74), radius=int(s * 0.10),
            outline=color, width=lw,
        )
        dot = int(s * 0.075)
        for row, y in enumerate((s * 0.40, s * 0.56)):
            cols = (5, 4)[row]
            total_w = cols * dot * 2.0
            start = (s - total_w) / 2 + dot * 0.5
            for i in range(cols):
                cx = start + i * dot * 2.1
                d.rounded_rectangle(
                    (cx, y, cx + dot, y + dot * 0.78), radius=max(1, dot // 3), fill=color
                )
    elif kind == "headset":
        # 头梁
        d.arc((s * 0.16, s * 0.12, s * 0.84, s * 0.80), 180, 360, fill=color, width=lw)
        d.line([(s * 0.16, s * 0.46), (s * 0.16, s * 0.58)], fill=color, width=lw)
        d.line([(s * 0.84, s * 0.46), (s * 0.84, s * 0.58)], fill=color, width=lw)
        # 耳罩
        d.rounded_rectangle((s * 0.08, s * 0.52, s * 0.30, s * 0.84), radius=int(s * 0.09), fill=color)
        d.rounded_rectangle((s * 0.70, s * 0.52, s * 0.92, s * 0.84), radius=int(s * 0.09), fill=color)
    else:
        r = s * 0.30
        d.rounded_rectangle((s * 0.5 - r, s * 0.5 - r, s * 0.5 + r, s * 0.5 + r),
                            radius=int(s * 0.10), outline=color, width=lw)
        d.ellipse((s * 0.44, s * 0.44, s * 0.56, s * 0.56), fill=color)

    return im.resize((px, px), Image.LANCZOS)


def charge_bolt(size: int, color, plate=None) -> Image.Image:
    """充电角标：一枚小闪电，贴在设备图标右下角（和系统电池图标一个意思）。"""
    s = size * 4
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    if plate is not None:
        ImageDraw.Draw(im).ellipse((0, 0, s - 1, s - 1), fill=plate)
    d = ImageDraw.Draw(im)
    pad = s * 0.20
    w_ = s - pad * 2
    pts = [
        (s * 0.58, pad),
        (s * 0.30, s * 0.55),
        (s * 0.47, s * 0.55),
        (s * 0.40, pad + w_),
        (s * 0.68, s * 0.44),
        (s * 0.50, s * 0.44),
    ]
    d.polygon(pts, fill=color)
    return im.resize((size, size), Image.LANCZOS)


def app_mark(size: int, theme: Theme) -> Image.Image:
    """应用标识：圆角方块 + 电池。"""
    s = size * 4
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    mask = Image.new("L", (s, s), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, s - 1, s - 1), radius=int(s * 0.29), fill=255)
    grad = Image.new("RGBA", (s, s))
    gd = ImageDraw.Draw(grad)
    top, bottom = (86, 152, 255, 255), (37, 99, 235, 255)
    for y in range(s):
        t = y / max(1, s - 1)
        gd.line([(0, y), (s, y)], fill=tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(4)))
    im.paste(grad, (0, 0), mask)
    glyph = battery_glyph(int(size * 0.66 * 4), 72, (255, 255, 255, 255), outline=(255, 255, 255, 255))
    im.alpha_composite(glyph, ((s - glyph.width) // 2, (s - glyph.height) // 2))
    return im.resize((size, size), Image.LANCZOS)
