"""轻量日志：写入 %APPDATA%\\TrayBattery\\app.log（最多 200KB）。"""
from __future__ import annotations

import os
import time
import traceback

from .config import data_dir

MAX_BYTES = 200 * 1024


def log(message: str) -> None:
    try:
        path = os.path.join(data_dir(), "app.log")
        if os.path.exists(path) and os.path.getsize(path) > MAX_BYTES:
            os.replace(path, path + ".1")
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}  {message}\n")
    except OSError:
        pass


def log_exc(context: str) -> None:
    log(context + "\n" + traceback.format_exc())
