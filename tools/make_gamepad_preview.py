"""生成设备图标展示图 assets/gamepad-preview.png。

和 make_icon.py 一样是纯绘制脚本，改了 device_glyph() 里的造型后重跑即可。
用法：python tools/make_gamepad_preview.py
"""
import sys, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from PIL import Image, ImageDraw
from app.draw import device_glyph, render_text, battery_glyph
from app.theme import Fonts

f = Fonts(1.0)
WHITE = (238, 241, 246, 255)
SUB = (150, 158, 172, 255)
INK = (52, 104, 200, 255)
PLATE = (214, 226, 246, 255)
out = Image.new("RGBA", (900, 400), (22, 24, 28, 255))
d = ImageDraw.Draw(out)


def txt(x, y, s, font, color, anchor="lm"):
    bmp = render_text(s, font, color)
    if anchor == "lm":
        out.alpha_composite(bmp, (int(x), int(y - bmp.height / 2)))
    else:
        out.alpha_composite(bmp, (int(x), int(y)))
    return bmp


def label(x, y, s, size=10):
    return txt(x, y, s, f.get(size), SUB)


txt(40, 34, "设备图标 · 手柄与音箱", f.get(16, "semibold"), WHITE)
label(40, 58, "任务栏 16 px / 设置页 18 px / 96 px 放大细节", 10)

# --- 左侧：两枚放大展示
for i, (kind, caption) in enumerate((("gamepad", "96 px · 手柄"),
                                     ("speaker", "96 px · 音箱"))):
    x = 46 + i * 112
    out.alpha_composite(device_glyph(kind, 96, WHITE, weight=0.115), (x, 96))
    label(x, 210, caption, 10)

# --- 左下：五枚 16 px 并排（真实尺寸）
label(40, 244, "与现有图标并排 · 16 px", 10)
for i, kind in enumerate(("mouse", "keyboard", "headset", "speaker", "gamepad")):
    out.alpha_composite(device_glyph(kind, 16, WHITE, weight=0.115), (40 + i * 42, 264))

# --- 右上：任务栏语境
bar = Image.new("RGBA", (580, 56), (30, 32, 37, 255))
out.alpha_composite(bar, (280, 92))
out.alpha_composite(device_glyph("gamepad", 16, WHITE, weight=0.115), (300, 112))
txt(326, 120, "87%", f.get(12, "semibold", True), WHITE)
out.alpha_composite(battery_glyph(16, 87, WHITE), (382, 112))
out.alpha_composite(device_glyph("speaker", 16, WHITE, weight=0.115), (430, 112))
txt(456, 120, "72%", f.get(12, "semibold", True), WHITE)
out.alpha_composite(battery_glyph(16, 72, WHITE), (512, 112))
d.line([(562, 120), (568, 114), (574, 120)], fill=(*SUB[:3], 255), width=2)
label(280, 166, "任务栏：与原生素色图标同一套墨色", 10)

# --- 右下：设置页圆盘语境
rows = (("mouse", "MX Master 3S"),
        ("keyboard", "MX Keys Mini"),
        ("headset", "HUAWEI FreeBuds 6i"),
        ("speaker", "HUAWEI Sound Joy"),
        ("gamepad", "Xbox Wireless Controller"))
for i, (kind, name) in enumerate(rows):
    y = 190 + i * 38
    d.ellipse((280, y, 310, y + 30), fill=PLATE)
    out.alpha_composite(device_glyph(kind, 18, INK, weight=0.115), (286, y + 6))
    txt(322, y + 15, name, f.get(11, "semibold"), WHITE)

out.convert("RGB").save(os.path.join(ROOT, "assets", "gamepad-preview.png"))
print("saved", out.size)
