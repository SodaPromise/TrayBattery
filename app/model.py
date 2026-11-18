"""设备与状态的数据模型。"""
from __future__ import annotations

from dataclasses import dataclass, field

MOUSE = "mouse"
KEYBOARD = "keyboard"
HEADSET = "headset"
GAMEPAD = "gamepad"
OTHER = "other"

ONLINE = "online"
OFFLINE = "offline"
UNSUPPORTED = "unsupported"
ERROR = "error"

KIND_LABEL = {MOUSE: "鼠标", KEYBOARD: "键盘", HEADSET: "耳机",
              GAMEPAD: "手柄", OTHER: "设备"}
STATUS_LABEL = {ONLINE: "已连接", OFFLINE: "离线", UNSUPPORTED: "不支持", ERROR: "读取失败"}


@dataclass
class Device:
    key: str
    name: str
    kind: str = OTHER
    transport: str = "蓝牙"
    status: str = ONLINE
    level: int | None = None
    charging: bool = False
    detail: str = ""
    last_level: int | None = None
    vendor: str = ""

    @property
    def kind_label(self) -> str:
        return KIND_LABEL.get(self.kind, "设备")

    def status_text(self) -> str:
        if self.status == ONLINE:
            return f"{self.transport} · 充电中" if self.charging else f"{self.transport} · 已连接"
        if self.status == OFFLINE:
            return f"{self.transport} · 未连接"
        if self.status == UNSUPPORTED:
            return f"{self.transport} · {self.detail or '不支持电量读取'}"
        return self.detail or "读取失败，稍后重试"

    def sort_key(self) -> tuple:
        order = {MOUSE: 0, KEYBOARD: 1, HEADSET: 2, GAMEPAD: 3, OTHER: 4}
        return (0 if self.status == ONLINE else 1, order.get(self.kind, 9), self.name.lower())


@dataclass
class AppState:
    """后台线程与 UI 线程共享的只读快照。"""

    devices: list[Device] = field(default_factory=list)
    last_update: float = 0.0
    refreshing: bool = False
    cycle: int = 0
