"""配置持久化（%APPDATA%\\TrayBattery\\config.json）。"""
from __future__ import annotations

import json
import os
import time

APP_NAME = "TrayBattery"
APP_TITLE = "电量助手"


def data_dir() -> str:
    base = os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), "AppData", "Roaming")
    path = os.path.join(base, APP_NAME)
    os.makedirs(path, exist_ok=True)
    return path


DEFAULTS = {
    "version": 1,
    "enabled": [],
    "initialized": False,
    "interval": 60,
    "show_bar": True,
    "bar_pos": None,
    "tray_mode": "cycle",
    "theme": "auto",
    "autostart": False,
    "paused": False,
    "alert": True,
    "alert_threshold": 15,
    "known": {},
}


class Config:
    def __init__(self, path: str | None = None) -> None:
        self.path = path or os.path.join(data_dir(), "config.json")
        self.data = dict(DEFAULTS)
        self.data["known"] = {}
        self.load()

    # ------------------------------------------------------------------
    def load(self) -> None:
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            if isinstance(raw, dict):
                for k, v in raw.items():
                    if k in DEFAULTS:
                        self.data[k] = v
                if not isinstance(self.data.get("known"), dict):
                    self.data["known"] = {}
        except (OSError, ValueError):
            pass

    def save(self) -> None:
        tmp = self.path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)
        except OSError:
            try:
                os.remove(tmp)
            except OSError:
                pass

    # ------------------------------------------------------------------
    def __getitem__(self, key):
        return self.data.get(key, DEFAULTS.get(key))

    def __setitem__(self, key, value) -> None:
        self.data[key] = value

    def update(self, **kwargs) -> None:
        self.data.update(kwargs)

    # ------------------------------------------------------------------
    @property
    def known(self) -> dict:
        return self.data.setdefault("known", {})

    def remember(self, device) -> None:
        entry = self.known.get(device.key) or {}
        entry.update(
            {
                "name": device.name,
                "kind": device.kind,
                "transport": device.transport,
                "last_seen": int(time.time()),
            }
        )
        if device.level is not None and device.status == "online":
            entry["last_level"] = device.level
        self.known[device.key] = entry

    def is_enabled(self, key: str) -> bool:
        return key in (self.data.get("enabled") or [])

    def set_enabled(self, key: str, value: bool) -> None:
        enabled = list(self.data.get("enabled") or [])
        if value and key not in enabled:
            enabled.append(key)
        elif not value and key in enabled:
            enabled.remove(key)
        self.data["enabled"] = enabled
        self.data["initialized"] = True

    def toggle_enabled(self, key: str) -> bool:
        new = not self.is_enabled(key)
        self.set_enabled(key, new)
        return new
