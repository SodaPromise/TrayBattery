"""后台轮询：设备发现放到工作线程，结果回传 UI 线程。"""
from __future__ import annotations

import threading
import time

from . import providers
from . import win32 as k
from .tray import WM_DATA


class Monitor:
    def __init__(self, app) -> None:
        self.app = app
        self.interval = max(10, int(app.config["interval"]))
        self._wake = threading.Event()
        self._stop = False
        self._force = False
        self._thread = threading.Thread(target=self._run, name="TrayBatteryMonitor", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def set_interval(self, seconds: int) -> None:
        self.interval = max(10, int(seconds))
        self._wake.set()

    def trigger(self, delay: float = 0.0, force: bool = True) -> None:
        if force:
            self._force = True
        if delay > 0:
            threading.Timer(delay, self._wake.set).start()
        else:
            self._wake.set()

    def stop(self) -> None:
        self._stop = True
        self._wake.set()

    # ------------------------------------------------------------------
    def _run(self) -> None:
        while not self._stop:
            paused = bool(self.app.config["paused"])
            self._wake.clear()          # 先清事件，扫描期间的触发不会丢
            if not paused or self._force:
                forced = self._force
                self._force = False
                self._scan(forced)
            self._wake.wait(3600 if paused else self.interval)

    def _scan(self, force: bool = False) -> None:
        app = self.app
        app.mark_refreshing(True, notify=True)
        try:
            devices = providers.discover(app.demo, force=force)
        except Exception:
            devices = []
        app.pending = (devices, time.time())
        if app.host and app.host.hwnd:
            k.PostMessageW(app.host.hwnd, WM_DATA, 0, 0)
