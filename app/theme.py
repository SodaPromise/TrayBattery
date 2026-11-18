"""配色与字体。"""
from __future__ import annotations

import os
import time
import winreg
from dataclasses import dataclass

FONT_DIR = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")


def _hex(c: str, a: int = 255) -> tuple[int, int, int, int]:
    c = c.lstrip("#")
    return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16), a)


@dataclass
class Theme:
    dark: bool
    panel: str
    panel_alt: str
    card: str
    card_hover: str
    text: str
    sub: str
    faint: str
    line: str
    track: str
    accent: str
    accent_text: str
    accent_soft: str
    green: str
    amber: str
    red: str
    shadow_alpha: int
    overlay: str

    def c(self, name: str, alpha: int = 255):
        return _hex(getattr(self, name), alpha)

    def mix(self, fg: str, bg: str, alpha: float):
        """把 fg 按 alpha 混到 bg 上，得到不透明颜色（分层窗口需要）。"""
        f = _hex(getattr(self, fg))
        b = _hex(getattr(self, bg))
        a = max(0.0, min(1.0, alpha))
        return tuple(int(round(f[i] * a + b[i] * (1 - a))) for i in range(3)) + (255,)


LIGHT = Theme(
    dark=False,
    panel="#FBFBFD",
    panel_alt="#F4F5F8",
    card="#FFFFFF",
    card_hover="#F3F5F9",
    text="#16181D",
    sub="#6A7280",
    faint="#8B93A0",
    line="#E8EAF0",
    track="#E6E8EE",
    accent="#2F72F0",
    accent_text="#FFFFFF",
    accent_soft="#EAF1FE",
    green="#12A150",
    amber="#B4690E",
    red="#DC3D43",
    shadow_alpha=60,
    overlay="#FFFFFF",
)

DARK = Theme(
    dark=True,
    panel="#1B1D22",
    panel_alt="#202329",
    card="#24272E",
    card_hover="#2B2F37",
    text="#F2F4F8",
    sub="#A2AAB7",
    faint="#7C8492",
    line="#2E323A",
    track="#343941",
    accent="#4C8DFF",
    accent_text="#FFFFFF",
    accent_soft="#243349",
    green="#35C06F",
    amber="#F0A93B",
    red="#F2585E",
    shadow_alpha=110,
    overlay="#1B1D22",
)


def system_uses_light_theme() -> bool:
    return _personalize_flag("AppsUseLightTheme", True)


def system_taskbar_light() -> bool:
    """任务栏自己的深浅色，跟"应用模式"是分开的开关。"""
    return _personalize_flag("SystemUsesLightTheme", False)


def _personalize_flag(name: str, default: bool) -> bool:
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        )
        try:
            value, _ = winreg.QueryValueEx(key, name)
            return bool(value)
        finally:
            winreg.CloseKey(key)
    except OSError:
        return default


def resolve_theme(mode: str) -> Theme:
    """mode: auto / light / dark"""
    if mode == "light":
        return LIGHT
    if mode == "dark":
        return DARK
    return LIGHT if system_uses_light_theme() else DARK


# ------------------------------------------------------------------ 任务栏墨色
@dataclass(frozen=True)
class BarSkin:
    """任务栏上"原生状态项"的墨色：只有黑白 + 系统告警色，没有底色。"""

    dark: bool
    fg: tuple
    dim: tuple
    hover: tuple
    pressed: tuple
    critical: tuple

    def level_color(self, level: int | None, status: str, charging: bool = False):
        if status != "online" or level is None:
            return self.dim
        if not charging and level <= 10:      # 和 Windows 一样，低于 10% 才转红
            return self.critical
        return self.fg


DARK_BAR = BarSkin(
    dark=True,
    fg=(255, 255, 255, 255),
    dim=(255, 255, 255, 150),
    hover=(255, 255, 255, 18),
    pressed=(255, 255, 255, 30),
    critical=(255, 153, 164, 255),        # SystemFillColorCriticalLight
)

LIGHT_BAR = BarSkin(
    dark=False,
    fg=(26, 26, 26, 255),
    dim=(26, 26, 26, 138),
    hover=(0, 0, 0, 14),
    pressed=(0, 0, 0, 26),
    critical=(196, 43, 28, 255),          # SystemFillColorCriticalDark
)


def _sample_brightness(box) -> int | None:
    """取一块屏幕区域的平均亮度；任务栏可能是深色、浅色或强调色。"""
    try:
        from PIL import Image, ImageGrab

        im = ImageGrab.grab(bbox=tuple(int(round(v)) for v in box), all_screens=True)
        if im.width < 2 or im.height < 2:
            return None
        return int(im.convert("L").resize((1, 1), Image.BOX).getpixel((0, 0)))
    except Exception:
        return None


_skin_cache: tuple[float, BarSkin] | None = None


def bar_skin(box=None, force: bool = False) -> BarSkin:
    """黑底任务栏上写字用白，浅色或强调色浅底上写字用近黑。

    直接采样任务栏像素，比读注册表更准：任务栏可以是强调色、毛玻璃，
    甚至和"应用模式"不同色，只有实际亮度才能决定墨色。
    """
    global _skin_cache
    now = time.monotonic()
    if not force and _skin_cache is not None and now - _skin_cache[0] < 2.0:
        return _skin_cache[1]
    brightness = _sample_brightness(box) if box else None
    dark = (not system_taskbar_light()) if brightness is None else brightness < 150
    skin = DARK_BAR if dark else LIGHT_BAR
    _skin_cache = (now, skin)
    return skin


def forget_bar_skin() -> None:
    global _skin_cache
    _skin_cache = None


def card_skin(theme: Theme) -> BarSkin:
    """悬浮卡片上的墨色：跟卡片自己的深浅走，而不是任务栏。"""
    return DARK_BAR if theme.dark else LIGHT_BAR


# (文件, 字体集合索引, 可变字重实例, 合成字重增强)
# 中文没有 Semibold：雅黑只有 regular / bold，bold 在 12~17px 会把笔画糊成一团。
# 所以中文半粗改用"regular + 细描边"的合成字重，笔画均匀、不粘连。
# 西文与数字用 Win11 自己的 Segoe UI Variable，按光学尺寸选 Text 实例，小字号更清楚。
FONT_FILES = {
    ("regular", False): ("msyh.ttc", 1, None, 0.0),
    ("semibold", False): ("msyh.ttc", 1, None, 0.16),
    ("bold", False): ("msyhbd.ttc", 1, None, 0.0),
    ("light", False): ("msyhl.ttc", 1, None, 0.0),
    ("regular", True): ("SegUIVar.ttf", 0, "Regular", 0.0),
    ("semibold", True): ("SegUIVar.ttf", 0, "Semibold Text", 0.0),
    ("bold", True): ("SegUIVar.ttf", 0, "Bold Text", 0.0),
}

# SegUIVar 缺失时的退路：同样按字重选文件
_SEGOE_FALLBACK = {
    "regular": ("segoeui.ttf", 0, None, 0.0),
    "semibold": ("seguisb.ttf", 0, None, 0.0),
    "bold": ("segoeuib.ttf", 0, None, 0.0),
    "light": ("segoeuil.ttf", 0, None, 0.0),
}


# 西文与数字单独走 Segoe UI Variable：微软雅黑自带的拉丁字形偏宽偏矮，
# 和 Windows 原生界面（正文一直是 Segoe UI）放在一起会显得"不是这个系统的字"。
# 按字重给对应实例，中文那边缺 semibold 是合成描边，西文这里有真字重。
_LATIN_FACE = {
    "regular": ("SegUIVar.ttf", 0, "Regular"),
    "semibold": ("SegUIVar.ttf", 0, "Semibold Text"),
    "bold": ("SegUIVar.ttf", 0, "Bold Text"),
    "light": ("SegUIVar.ttf", 0, "Light Text"),
}


class Fonts:
    def __init__(self, scale: float) -> None:
        self.scale = scale
        self._cache: dict[tuple[int, str, bool], object] = {}
        self._paths: dict[tuple[str, bool], tuple[str, int, str | None, float]] = {}

    def _spec(self, weight: str, digit: bool) -> tuple[str, int, str | None, float]:
        key = (weight, digit)
        if key not in self._paths:
            fname, idx, var, boost = FONT_FILES.get(key, FONT_FILES[("regular", False)])
            path = os.path.join(FONT_DIR, fname)
            if not os.path.exists(path):
                if digit or weight in _SEGOE_FALLBACK:
                    fname, idx, var, boost = _SEGOE_FALLBACK.get(
                        weight, _SEGOE_FALLBACK["regular"])
                else:
                    fname, idx, var, boost = "segoeui.ttf", 0, None, 0.0
                path = os.path.join(FONT_DIR, fname)
            self._paths[key] = (path, idx, var, boost)
        return self._paths[key]

    def get(self, size: float, weight: str = "regular", digit: bool = False):
        # 字号取整到物理像素：15.625 这种半像素字号会被 FreeType 栅格化成
        # 一条粗一条细，宁可落在整数像素上。
        px = max(9, int(round(size * self.scale)))
        key = (px, weight, digit)
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        from PIL import ImageFont

        path, idx, var, boost = self._spec(weight, digit)
        try:
            font = ImageFont.truetype(path, px, index=idx)
            if var:
                try:
                    font.set_variation_by_name(var)
                except Exception:
                    pass
        except Exception:
            font = ImageFont.load_default()
        # 渲染层靠这份元数据在 3 倍尺寸上重建同款字体；
        # latin 是同一字号下的西文搭档，中英混排时按字符分流（见 draw.render_text）
        latin = None
        if not digit:
            lname, lidx, lvar = _LATIN_FACE.get(weight, _LATIN_FACE["regular"])
            lpath = os.path.join(FONT_DIR, lname)
            if not os.path.exists(lpath):
                lpath, lidx, lvar = os.path.join(FONT_DIR, "segoeui.ttf"), 0, None
            latin = (lpath, lidx, lvar)
        font._tb = (path, px, idx, var, boost, latin)
        self._cache[key] = font
        return font
