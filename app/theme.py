"""配色与字体。"""
from __future__ import annotations

import os
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
    faint="#9AA1AC",
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
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        )
        try:
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return bool(value)
        finally:
            winreg.CloseKey(key)
    except OSError:
        return True


def resolve_theme(mode: str) -> Theme:
    """mode: auto / light / dark"""
    if mode == "light":
        return LIGHT
    if mode == "dark":
        return DARK
    return LIGHT if system_uses_light_theme() else DARK


FONT_FILES = {
    ("regular", False): ("msyh.ttc", 1),
    ("semibold", False): ("msyhbd.ttc", 1),
    ("bold", False): ("msyhbd.ttc", 1),
    ("light", False): ("msyhl.ttc", 1),
    ("regular", True): ("segoeui.ttf", 0),
    ("semibold", True): ("seguisb.ttf", 0),
    ("bold", True): ("segoeuib.ttf", 0),
}


class Fonts:
    def __init__(self, scale: float) -> None:
        self.scale = scale
        self._cache: dict[tuple[int, str, bool], object] = {}
        self._paths: dict[str, tuple[str, int]] = {}

    def _path(self, weight: str, digit: bool) -> tuple[str, int]:
        key = f"{weight}{digit}"
        if key not in self._paths:
            fname, idx = FONT_FILES.get((weight, digit), FONT_FILES[("regular", False)])
            self._paths[key] = (os.path.join(FONT_DIR, fname), idx)
        return self._paths[key]

    def get(self, size: float, weight: str = "regular", digit: bool = False):
        px = max(8, int(round(size * self.scale)))
        key = (px, weight, digit)
        if key not in self._cache:
            from PIL import ImageFont

            path, idx = self._path(weight, digit)
            try:
                self._cache[key] = ImageFont.truetype(path, px, index=idx)
            except Exception:
                self._cache[key] = ImageFont.load_default()
        return self._cache[key]
