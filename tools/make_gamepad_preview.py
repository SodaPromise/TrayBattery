"""生成手柄图标展示图 assets/gamepad-preview.png。

和 make_icon.py 一样是纯绘制脚本，改了 device_glyph() 里的手柄造型后重跑即可。
用法：python tools/make_gamepad_preview.py
"""
import sys, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from PIL import Image, ImageDraw
from app.draw import device_glyph, render_text, battery_glyph
from app.theme import Fonts, FONT_DIR

f = Fonts(1.0)
WHITE = (238, 241, 246, 255)
SUB = (150, 158, 172, 255)
INK = (52, 104, 200, 255)
PLATE = (214, 226, 246, 255)
out = Image.new("RGBA", (760, 330), (22, 24, 28, 255))


def txt(x, y, s, font, color, anchor="lm"):
    bmp = render_text(s, font, color)
    if anchor == "lm":
        out.alpha_composite(bmp, (int(x), int(y - bmp.height / 2)))
    else:
        out.alpha_composite(bmp, (int(x), int(y)))
    return bmp


def label(x, y, s, size=10):
    return txt(x, y, s, f.get(size), SUB)


txt(40, 34, "手柄设备图标", f.get(16, "semibold"), WHITE)
label(40, 58, "任务栏 16 px / 设置页 18 px / 96 px 放大细节", 10)

# --- 左侧：放大展示
big = device_glyph("gamepad", 96, WHITE, weight=0.115)
out.alpha_composite(big, (46, 96))
label(46, 210, "96 px", 10)

# --- 左下：四枚 16 px 并排（真实尺寸）
label(40, 244, "与现有三种图标并排 · 16 px", 10)
for i, kind in enumerate(("mouse", "keyboard", "headset", "gamepad")):
    out.alpha_composite(device_glyph(kind, 16, WHITE, weight=0.115), (40 + i * 42, 264))

# --- 右上：任务栏语境
bar = Image.new("RGBA", (490, 56), (30, 32, 37, 255))
out.alpha_composite(bar, (210, 92))
out.alpha_composite(device_glyph("gamepad", 16, WHITE, weight=0.115), (232, 112))
txt(258, 120, "87%", f.get(12, "semibold", True), WHITE)
out.alpha_composite(battery_glyph(16, 87, WHITE), (316, 112))
d = ImageDraw.Draw(out)
d.line([(366, 120), (372, 114), (378, 120)], fill=(*SUB[:3], 255), width=2)
label(210, 166, "任务栏：与原生素色图标同一套墨色", 10)

# --- 右中：设置页圆盘语境
for i, (kind, name) in enumerate((("mouse", "MX Master 3S"),
                                  ("keyboard", "MX Keys Mini"),
                                  ("gamepad", "Xbox Wireless Controller"))):
    y = 190 + i * 40
    d.ellipse((210, y, 240, y + 30), fill=PLATE)
    out.alpha_composite(device_glyph(kind, 18, INK, weight=0.115), (216, y + 6))
    txt(252, y + 15, name, f.get(11, "semibold"), WHITE)

# --- 底部：四枚 16px 并排（已移到左下，避免和圆盘行重叠）
out.convert("RGB").save(os.path.join(ROOT, "assets", "gamepad-preview.png"))
print("saved", out.size)
