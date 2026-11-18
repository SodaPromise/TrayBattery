"""生成应用图标 assets/icon.ico（多尺寸）。

用法：python tools/make_icon.py
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from app.draw import app_mark  # noqa: E402
from app.theme import DARK  # noqa: E402

SIZES = [16, 24, 32, 48, 64, 128, 256]


def main() -> None:
    out_dir = os.path.join(ROOT, "assets")
    os.makedirs(out_dir, exist_ok=True)
    big = app_mark(256, DARK)
    ico = os.path.join(out_dir, "icon.ico")
    big.save(ico, format="ICO", sizes=[(s, s) for s in SIZES])
    png = os.path.join(out_dir, "icon.png")
    big.save(png, format="PNG")
    print(f"wrote {ico} ({os.path.getsize(ico)} bytes)")
    print(f"wrote {png}")


if __name__ == "__main__":
    main()
