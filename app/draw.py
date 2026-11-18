"""Pillow 绘制工具：抗锯齿画布、文字渲染、电池图标、设备图标。"""
from __future__ import annotations

import math
from collections import OrderedDict
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .theme import Theme

# 文字超采样倍率：先把字形按 3 倍尺寸绘制再 LANCZOS 降采样。
# 直接在 12~16px 上绘制时，FreeType 的栅格化会让横竖笔画粗细不匀（尤其中文），
# 3 倍超采样能把笔画边缘摊到更多灰阶上，小字号看起来才细腻。
TEXT_SS = 3
_TEXT_CACHE: "OrderedDict[tuple, Image.Image]" = OrderedDict()
_TEXT_CACHE_MAX = 512


@lru_cache(maxsize=96)
def _font_at(path: str, px: int, index: int, var: str | None):
    font = ImageFont.truetype(path, px, index=index)
    if var:
        try:
            font.set_variation_by_name(var)
        except Exception:
            pass
    return font


def _font_meta(font) -> tuple:
    meta = getattr(font, "_tb", None)
    if meta is None:
        # load_default() 的 path 是 BytesIO 而不是文件路径，没法按字号重建；
        # 统一当成"无重建信息"，交给 render_text 的 1× 降级分支。
        path = getattr(font, "path", "")
        if not isinstance(path, str):
            path = ""
        meta = (path, getattr(font, "size", 12),
                getattr(font, "index", 0), None, 0.0, None)
    return meta


def _is_cjk(ch: str) -> bool:
    """汉字、假名、韩文、全角标点都归到中文字体，其余（拉丁、数字、半角符号）走西文字体。"""
    o = ord(ch)
    return (0x2E80 <= o <= 0x9FFF or 0xF900 <= o <= 0xFAFF
            or 0xFE30 <= o <= 0xFE4F or 0xFF00 <= o <= 0xFFEF
            or 0x1100 <= o <= 0x11FF or 0x3130 <= o <= 0x318F
            or 0xAC00 <= o <= 0xD7AF)


def _split_runs(s: str) -> list[tuple[str, bool]]:
    """切成"中文段 / 西文段"，同段内才能保留正常字距调整（kerning）。"""
    if not s:
        return []
    runs: list[tuple[str, bool]] = []
    buf = s[0]
    flag = _is_cjk(s[0])
    for ch in s[1:]:
        f = _is_cjk(ch)
        if f == flag:
            buf += ch
        else:
            runs.append((buf, flag))
            buf, flag = ch, f
    runs.append((buf, flag))
    return runs


def _blend(img: Image.Image, src: Image.Image, x: float, y: float) -> None:
    """把 src 贴到 img 上，自动裁掉越界部分（alpha_composite 不允许越界）。"""
    x, y = int(round(x)), int(round(y))
    if src.width < 1 or src.height < 1:
        return
    if x >= img.width or y >= img.height or x + src.width <= 0 or y + src.height <= 0:
        return
    left, top = max(0, -x), max(0, -y)
    right = min(src.width, img.width - x)
    bottom = min(src.height, img.height - y)
    if (left, top, right, bottom) != (0, 0, src.width, src.height):
        src = src.crop((left, top, right, bottom))
    if x < 0:
        x = 0
    if y < 0:
        y = 0
    img.alpha_composite(src, (x, y))


def render_text(s: str, font, fill, tracking: float = 0.0) -> Image.Image:
    """把一段文字渲染成紧贴墨迹的位图（物理像素），带 LRU 缓存。

    tracking 是字距（物理像素，可为负）；中文标题加一点正字距会更透气，
    任务栏上的百分比则用一点负字距，数字才不会散。

    中英混排按字符分流：汉字走微软雅黑，拉丁字母和数字走 Segoe UI Variable，
    和系统原生界面的做法一致——整段都用雅黑的话，英文会明显偏宽偏矮。
    两段共用同一条基线，混排时不会一高一低。
    """
    path, px, index, var, boost, latin = _font_meta(font)
    fill = tuple(fill[:3]) + ((fill[3] if len(fill) > 3 else 255),)
    if not s:
        return Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    key = (path, px, index, var, boost, latin, s, fill, round(tracking, 2))
    cached = _TEXT_CACHE.get(key)
    if cached is not None:
        _TEXT_CACHE.move_to_end(key)
        return cached

    if path:
        ss = TEXT_SS
        hi_px = max(1, px * ss)
        hi = _font_at(path, hi_px, index, var)
        lat = _font_at(latin[0], hi_px, latin[1], latin[2]) if latin else hi
    else:
        # 外部传入的字体（例如 Pillow 默认字体）没有重建信息：
        # 退回 1× 直接绘制，功能不残废，只是少了超采样。
        ss = 1
        hi_px = max(1, getattr(font, "size", 12))
        hi = lat = font
    stroke = boost * ss
    pad = 4 * ss
    probe = ImageDraw.Draw(Image.new("RGBA", (2, 2)))

    # 分段：每段用自己的字体；描边只加在中文上（西文有真字重，不需要伪造加粗）
    parts = []
    for text, cjk in _split_runs(s):
        parts.append((text, hi if cjk else lat, stroke if cjk else 0.0))

    width = sum(probe.textlength(t, font=f) for t, f, _ in parts)
    if tracking:
        width += tracking * ss * max(0, len(s) - 1)

    ascent = max(f.getmetrics()[0] for _, f, _ in parts)
    layer = Image.new("RGBA",
                      (int(width * 1.12) + pad * 2, int(hi_px * 1.9) + pad * 2),
                      (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    baseline = pad + ascent
    x = float(pad)
    for text, f, sw in parts:
        if tracking:
            for ch in text:
                d.text((x, baseline), ch, font=f, fill=fill, anchor="ls",
                       stroke_width=sw, stroke_fill=fill)
                x += probe.textlength(ch, font=f) + tracking * ss
        else:
            d.text((x, baseline), text, font=f, fill=fill, anchor="ls",
                   stroke_width=sw, stroke_fill=fill)
            x += probe.textlength(text, font=f)

    ink = layer.getbbox()
    if ink is None:
        out = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    else:
        ink = layer.crop(ink)
        out = ink.resize((max(1, int(round(ink.width / ss))),
                          max(1, int(round(ink.height / ss)))), Image.LANCZOS)
    _TEXT_CACHE[key] = out
    if len(_TEXT_CACHE) > _TEXT_CACHE_MAX:
        _TEXT_CACHE.popitem(last=False)
    return out


def clear_text_cache() -> None:
    _TEXT_CACHE.clear()


class Canvas:
    """设计坐标（逻辑像素）× zoom 得到物理像素，形状再按 ss 超采样。

    文字不参与形状的超采样：它在 finish() 里按物理分辨率单独合成，
    这样字形不会被形状缩放二次模糊。
    """

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
        """投影只模糊它所在的一小块，并在半分辨率上做高斯模糊。

        阴影是低频图形，半分辨率模糊再放大肉眼看不出来，
        但省掉了整张画布的分配和几十毫秒的模糊时间。
        """
        pad = int(blur * 2.8 * self.zoom * self.ss) + 2
        x0, y0, x1, y1 = self.box((b[0], b[1] + dy, b[2], b[3] + dy))
        left, top = max(0, x0 - pad), max(0, y0 - pad)
        right, bottom = min(self.img.width, x1 + pad), min(self.img.height, y1 + pad)
        if right - left < 2 or bottom - top < 2:
            return
        q = 0.5
        sw, sh = max(1, int(round((right - left) * q))), max(1, int(round((bottom - top) * q)))
        layer = Image.new("L", (sw, sh), 0)
        ImageDraw.Draw(layer).rounded_rectangle(
            ((x0 - left) * q, (y0 - top) * q, (x1 - left) * q, (y1 - top) * q),
            radius=max(1, int(round(self.S(r) * q))), fill=alpha)
        layer = layer.filter(ImageFilter.GaussianBlur(
            max(0.5, blur * self.zoom * self.ss * q)))
        layer = layer.resize((right - left, bottom - top), Image.BILINEAR)
        tint = Image.new("RGBA", layer.size, color)
        tint.putalpha(layer)
        self.img.alpha_composite(tint, (left, top))

    # -- 文字 / 位图（延后绘制）
    def text(self, xy, s: str, font, fill, anchor: str = "lm", tracking: float = 0.0) -> None:
        """anchor 的纵向以"墨迹"为准：m 表示字形实心的垂直中点，不是基线盒。

        这样 95%、设置、完成 这些不同字体/字号的文字，混排时视觉中线才对得齐。
        """
        self._ops.append(("text", (xy[0] * self.zoom, xy[1] * self.zoom), s, font,
                          fill, anchor, tracking * self.zoom))

    def paste(self, im: Image.Image, xy) -> None:
        self._ops.append(("paste", (int(round(xy[0] * self.zoom)), int(round(xy[1] * self.zoom))), im))

    def finish(self) -> Image.Image:
        img = self.img.resize((self.w, self.h), Image.LANCZOS) if self.ss != 1 else self.img
        for op in self._ops:
            if op[0] == "text":
                _, xy, s, font, fill, anchor, tracking = op
                bmp = render_text(s, font, fill, tracking)
                ax, ay = anchor[0], anchor[1]
                dx = 0.0 if ax == "l" else (-bmp.width / 2 if ax == "m" else -bmp.width)
                dy = 0.0 if ay in "ta" else (-bmp.height / 2 if ay in "ms" else -bmp.height)
                _blend(img, bmp, xy[0] + dx, xy[1] + dy)
            else:
                _, xy, im = op
                if im.mode != "RGBA":
                    im = im.convert("RGBA")
                _blend(img, im, xy[0], xy[1])
        return img


def text_width(s: str, font) -> float:
    """按实际渲染规则量宽度：中文用 font，西文用它的 Segoe 搭档。

    直接拿中文字体量 "HUAWEI FreeBuds 6i" 会偏宽一截，省略号会提前出现。
    """
    latin = _font_meta(font)[5]
    probe = ImageDraw.Draw(Image.new("RGBA", (2, 2)))
    if not latin:
        return probe.textlength(s, font=font)
    lat = _font_at(latin[0], max(1, getattr(font, "size", 12)), latin[1], latin[2])
    total = 0.0
    for text, cjk in _split_runs(s):
        total += probe.textlength(text, font=font if cjk else lat)
    return total


def ellipsize(text: str, font, max_w: float) -> str:
    if not text:
        return ""
    if text_width(text, font) <= max_w:
        return text
    ell = "…"
    while text and text_width(text + ell, font) > max_w:
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
def _mouse_outline(s: int, hw: float, hh: float, n: float = 2.4,
                   taper: float = 0.08, steps: int = 180):
    """俯视鼠标的轮廓点：超椭圆主体 + 上端（按键端）收窄。

    纯圆角矩形在 16px 下像一根胶囊，看不出"鼠标头宽尾窄"的特征；
    超椭圆指数 n=2.4 保留了圆润的肩部，taper 让前端略窄，比例更像真鼠标。
    """
    cx, cy = s / 2, s / 2
    pts = []
    for i in range(steps):
        th = 2 * math.pi * i / steps
        c, sn = math.cos(th), math.sin(th)
        x = hw * math.copysign(abs(c) ** (2.0 / n), c)
        y = hh * math.copysign(abs(sn) ** (2.0 / n), sn)
        if y < 0:
            x *= 1.0 - taper * (-y / hh)
        pts.append((cx + x, cy + y))
    return pts


def device_glyph(kind: str, px: int, color, weight: float = 0.085) -> Image.Image:
    """按 4 倍绘制再缩小，得到平滑的小图标。weight 是线宽占图标边长的比例。

    鼠标一律画实心剪影再挖缝：16px 下描边只剩一圈细线，整只鼠标比旁边的
    键盘、耳机单薄一大截；挖空的分缝反而更像系统自带的状态图标。
    """
    s = px * 4
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    lw = max(2, int(round(s * weight)))

    if kind == "mouse":
        # 俯视鼠标：机身 0.60×0.87（约 1:1.45），比真鼠标略宽——
        # 16px 下按真实比例画会瘦成一根胶囊，和旁边的键盘图标也不成比例。
        # 关键是那道"横向分缝"：把前段切成左右两个按键，再用竖缝当滚轮分界。
        hw, hh = s * 0.300, s * 0.435
        split = s * 0.375
        gap = max(2, int(s * 0.070))
        mask = Image.new("L", (s, s), 0)
        md = ImageDraw.Draw(mask)
        md.polygon(_mouse_outline(s, hw, hh), fill=255)
        md.line([(0, split), (s, split)], fill=0, width=gap)
        md.line([(s * 0.5, 0), (s * 0.5, split)], fill=0, width=gap)
        im.paste(Image.new("RGBA", (s, s), color), (0, 0), mask)
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
