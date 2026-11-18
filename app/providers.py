"""设备发现与电量读取。

来源：蓝牙 PnP 电量属性、标准 HID 电池字段、罗技 HID++ 2.0、
华为/荣耀私有通道、Compx（Nordic）公版方案、雷蛇 Feature Report。
"""
from __future__ import annotations

import ctypes
import re
import struct
import time
from collections import defaultdict
from ctypes import wintypes as w

from . import devapi
from .model import (
    Device, GAMEPAD, HEADSET, KEYBOARD, MOUSE, OTHER, OFFLINE, ONLINE, UNSUPPORTED,
)

LOGITECH = 0x046D
RECEIVER_PIDS = {
    0xC52B, 0xC532, 0xC534, 0xC537, 0xC539, 0xC53D, 0xC547, 0xC548, 0xC54D, 0xC54E,
}

# 华为 / 荣耀无线外设（星闪或 2.4G 接收器）：电量走厂商 HID 私有通道
HUAWEI_VID = 0x12D1
HUAWEI_STATUS_PAGE = 0xFFB3     # 接收器状态通道（会主动推送 05 00 00 AA 心跳）
HUAWEI_BATTERY_ITEM = 0x1A      # 电量数据项
_HW_GET = 0x1E                  # 读数据项
_HW_READ_ACK = 0x20              # 读应答
_HW_MODEL_ITEM = 0xF9           # 型号 + 固件版本（ASCII）

_MAC_RE = re.compile(r"DEV_([0-9A-F]{12})|&([0-9A-F]{12})(?:_|$)", re.I)
_MAC_ANY = re.compile(r"([0-9A-F]{12})", re.I)
_BT_SERVICE_SUFFIX = (
    " Hands-Free AG", " Hands-Free", " Avrcp 传输", " A2DP", " 服务",
    " Audio", " 音频", " Stereo", " HFP", " HSP",
)
_WIRELESS_HINT = re.compile(r"receiv|dongle|2\.4\s*g|wireless|无线|接收器", re.I)


def _looks_wireless(name: str, ifaces: list[devapi.HidInterface]) -> bool:
    """名称里带接收器/无线字样时，才把厂商私有通道的设备标成 2.4G。"""
    texts = [name] + [i.product or "" for i in ifaces]
    return any(_WIRELESS_HINT.search(t) for t in texts if t)


# ------------------------------------------------------------------ 名称与类型
def clean_bt_name(name: str) -> str:
    out = name.strip()
    for suffix in _BT_SERVICE_SUFFIX:
        if out.endswith(suffix):
            out = out[: -len(suffix)]
    return out.strip() or name.strip()


def infer_kind(name: str, classes: set[str] | None = None) -> str:
    low = (name or "").lower()
    if any(k in low for k in ("mouse", "鼠标", "trackball", "轨迹球",
                              "mx master", "mx anywhere")):
        return MOUSE
    if any(k in low for k in ("keyboard", "键盘", "keychron", "hhkb", "mx keys")):
        return KEYBOARD
    if any(k in low for k in ("buds", "airpods", "headset", "headphone", "耳机", "耳麦",
                              "wh-", "wf-", "freeclip", "soundcore", "momentum", "bose qc")):
        return HEADSET
    if any(k in low for k in ("音箱", "speaker", "sound joy", "soundlink")):
        return OTHER
    # 手柄：Windows 上常见的名字是 "Xbox Wireless Controller" /
    # "Wireless Controller"(PS4) / "Pro Controller"(Switch) / "DualSense ..."。
    # 不单独用 "controller" 兜底，免得把音频、MIDI 这类控制器也认成手柄。
    if any(k in low for k in ("gamepad", "game pad", "game controller", "手柄", "游戏手柄",
                              "xbox", "wireless controller", "pro controller",
                              "dualsense", "dualshock", "joy-con", "joycon",
                              "switch pro", "steam controller", "8bitdo",
                              "gamesir", "flydigi", "北通")):
        return GAMEPAD
    cls = classes or set()
    if "Mouse" in cls and "Keyboard" not in cls:
        return MOUSE
    if "Keyboard" in cls:
        return KEYBOARD
    if cls & {"MEDIA", "AudioEndpoint", "Audio"}:
        return HEADSET
    return OTHER


def group_container_classes(nodes: list[devapi.PnpNode]) -> dict[str, set[str]]:
    out: dict[str, set[str]] = defaultdict(set)
    for node in nodes:
        if node.container_id and node.class_name:
            out[node.container_id].add(node.class_name)
    return out


def _bt_mac(instance_id: str) -> str | None:
    m = _MAC_RE.search(instance_id)
    if m:
        return (m.group(1) or m.group(2)).upper()
    m = _MAC_ANY.search(instance_id)
    return m.group(1).upper() if m else None


# ------------------------------------------------------------------ 蓝牙连接状态
class _BLUETOOTH_ADDRESS(ctypes.Union):
    _fields_ = [("ullLong", ctypes.c_ulonglong), ("rgBytes", ctypes.c_ubyte * 6)]


class _SYSTEMTIME(ctypes.Structure):
    _fields_ = [
        ("wYear", w.WORD), ("wMonth", w.WORD), ("wDayOfWeek", w.WORD), ("wDay", w.WORD),
        ("wHour", w.WORD), ("wMinute", w.WORD), ("wSecond", w.WORD), ("wMilliseconds", w.WORD),
    ]


class _BLUETOOTH_DEVICE_INFO(ctypes.Structure):
    _fields_ = [
        ("dwSize", w.DWORD), ("Address", _BLUETOOTH_ADDRESS), ("ulClassofDevice", w.ULONG),
        ("fConnected", w.BOOL), ("fRemembered", w.BOOL), ("fAuthenticated", w.BOOL),
        ("stLastSeen", _SYSTEMTIME), ("stLastUsed", _SYSTEMTIME), ("szName", w.WCHAR * 248),
    ]


class _BLUETOOTH_DEVICE_SEARCH_PARAMS(ctypes.Structure):
    _fields_ = [
        ("dwSize", w.DWORD), ("fReturnAuthenticated", w.BOOL), ("fReturnRemembered", w.BOOL),
        ("fReturnUnknown", w.BOOL), ("fReturnConnected", w.BOOL), ("fIssueInquiry", w.BOOL),
        ("cTimeoutMultiplier", ctypes.c_ubyte), ("hRadio", ctypes.c_void_p),
    ]


def _load_bluetooth_api():
    try:
        bth = ctypes.WinDLL("bthprops.cpl")
        find_first = bth.BluetoothFindFirstDevice
        find_first.restype = ctypes.c_void_p
        find_first.argtypes = [ctypes.POINTER(_BLUETOOTH_DEVICE_SEARCH_PARAMS),
                               ctypes.POINTER(_BLUETOOTH_DEVICE_INFO)]
        find_next = bth.BluetoothFindNextDevice
        find_next.restype = w.BOOL
        find_next.argtypes = [ctypes.c_void_p, ctypes.POINTER(_BLUETOOTH_DEVICE_INFO)]
        find_close = bth.BluetoothFindDeviceClose
        find_close.restype = w.BOOL
        find_close.argtypes = [ctypes.c_void_p]
        return find_first, find_next, find_close
    except Exception:
        return None


_BT_API = _load_bluetooth_api()


def bluetooth_connection_map() -> dict[str, bool] | None:
    """返回 {MAC: 是否已连接}；蓝牙 API 不可用时返回 None。"""
    if not _BT_API:
        return None
    find_first, find_next, find_close = _BT_API

    sp = _BLUETOOTH_DEVICE_SEARCH_PARAMS()
    sp.dwSize = ctypes.sizeof(sp)
    sp.fReturnAuthenticated = True
    sp.fReturnRemembered = True
    sp.fReturnConnected = True
    sp.fIssueInquiry = False
    sp.cTimeoutMultiplier = 1
    info = _BLUETOOTH_DEVICE_INFO()
    info.dwSize = ctypes.sizeof(info)
    try:
        handle = find_first(ctypes.byref(sp), ctypes.byref(info))
    except Exception:
        return None
    if not handle:
        return {}
    result: dict[str, bool] = {}
    try:
        while True:
            addr = bytes(info.Address.rgBytes[::-1]).hex().upper()
            result[addr] = bool(info.fConnected)
            if not find_next(handle, ctypes.byref(info)):
                break
    finally:
        find_close(handle)
    return result


# ------------------------------------------------------------------ 私有协议缓存
class _Cache:
    """容器 ID → (时间戳, 电量, 充电中)：带 TTL，失败时沿用上次读数。"""

    def __init__(self) -> None:
        self._items: dict[str, tuple[float, int, bool]] = {}

    def fresh(self, key: str, ttl: float):
        item = self._items.get(key)
        if item and ttl > 0 and time.time() - item[0] < ttl:
            return item
        return None

    def last(self, key: str):
        return self._items.get(key)

    def put(self, key: str, level: int, charging: bool) -> None:
        self._items[key] = (time.time(), level, charging)

    def clear(self) -> None:
        self._items.clear()


_HW_CACHE = _Cache()
_CX_CACHE = _Cache()
_RZ_CACHE = _Cache()


def invalidate_vendor_caches() -> None:
    for cache in (_HW_CACHE, _CX_CACHE, _RZ_CACHE):
        cache.clear()


def _scan_vendor(ifaces, match, reader, cache: _Cache, ttl: float):
    """遍历接口，对匹配的容器查询一次电量；同一容器只查第一个接口。"""
    out: dict[str, tuple[int, bool]] = {}
    seen: set[str] = set()
    for itf in ifaces:
        cid = itf.container_id or ""
        if not cid or cid in seen or not match(itf):
            continue
        seen.add(cid)
        hit = cache.fresh(cid, ttl)
        if hit:
            out[cid] = hit[1:]
            continue
        got = reader(itf)
        if got:
            cache.put(cid, *got)
            out[cid] = got
        elif cache.last(cid):
            out[cid] = cache.last(cid)[1:]
    return out


# ------------------------------------------------------------------ HID++
class HidppLink:
    """HID++ 2.0 最小实现：短/长报文、功能发现、电量与名称。"""

    def __init__(self, dev: devapi.HidDevice) -> None:
        self.dev = dev
        self.out_len = int(dev.caps.OutputReportByteLength) if dev.caps else 0
        self.in_len = int(dev.caps.InputReportByteLength) if dev.caps else 0
        self.sw_id = 0x01
        self._features: dict[tuple[int, int], int] = {}

    def request(self, dev_idx: int, feat_idx: int, func: int,
                params: bytes = b"\x00\x00\x00", timeout: float = 0.22) -> bytes | None:
        if self.out_len >= 20:
            buf = bytearray(20)
            buf[0] = 0x11
        else:
            buf = bytearray(max(7, self.out_len or 7))
            buf[0] = 0x10
        buf[1] = dev_idx
        buf[2] = feat_idx
        buf[3] = ((func & 0x0F) << 4) | (self.sw_id & 0x0F)
        for i, b in enumerate(params[: max(0, len(buf) - 4)]):
            buf[4 + i] = b
        if not self.dev.write(bytes(buf), 300):
            return None
        deadline = time.monotonic() + timeout
        while True:
            remain = deadline - time.monotonic()
            if remain <= 0:
                return None
            data = self.dev.read(self.in_len or 7, int(remain * 1000) + 20)
            if not data or len(data) < 7:
                continue
            if data[0] not in (0x11, 0x12):
                continue
            if data[1] != dev_idx or data[2] != feat_idx:
                continue
            if (data[3] & 0x0F) != (self.sw_id & 0x0F):
                continue
            return bytes(data[4:])

    def feature(self, dev_idx: int, feature_id: int) -> int:
        key = (dev_idx, feature_id)
        if key not in self._features:
            resp = self.request(dev_idx, 0x00, 0x00, struct.pack(">H", feature_id))
            self._features[key] = resp[0] if resp else 0
        return self._features[key]

    def device_name(self, dev_idx: int) -> str | None:
        idx = self.feature(dev_idx, 0x0005)
        if not idx:
            return None
        resp = self.request(dev_idx, idx, 0x00)
        if not resp or not 0 < resp[0] < 8:
            return None
        raw = bytearray()
        for i in range(resp[0]):
            part = self.request(dev_idx, idx, 0x01, bytes([i]))
            if not part:
                break
            raw.extend(part[1:1 + min(part[0], len(part) - 1)])
        return raw.decode("utf-8", "ignore").replace("\x00", "").strip() or None

    def battery(self, dev_idx: int) -> tuple[int | None, bool, str]:
        """返回 (电量, 是否充电, 数据来源)。"""
        idx = self.feature(dev_idx, 0x1004)  # UNIFIED_BATTERY
        if idx:
            resp = self.request(dev_idx, idx, 0x00)
            if resp and 0 <= resp[0] <= 100:
                status, external = resp[1], resp[2]
                charging = bool(status & 0x03) or bool(external & 0x01) or resp[0] == 100 and bool(status)
                return resp[0], charging, "unified"
        idx = self.feature(dev_idx, 0x1000)  # BATTERY_LEVEL_STATUS
        if idx:
            resp = self.request(dev_idx, idx, 0x00)
            if resp and 0 <= resp[0] <= 100:
                status = resp[2] if len(resp) > 2 else 0
                return resp[0], status in (1, 2), "level"
        idx = self.feature(dev_idx, 0x1001)  # BATTERY_VOLTAGE
        if idx:
            resp = self.request(dev_idx, idx, 0x00)
            if resp and len(resp) >= 2:
                mv = resp[0] | (resp[1] << 8)
                if 2800 <= mv <= 4600:
                    pct = int(round((mv - 3300) / 900 * 100))
                    return max(0, min(100, pct)), False, "voltage"
        return None, False, ""


def _logi_device(product: str, index: int, name: str,
                 link: HidppLink, receiver: bool) -> Device:
    level, charging, source = link.battery(index)
    device = Device(
        key=f"hx:{product}:{index}",
        name=name,
        kind=infer_kind(name),
        transport="2.4G" if receiver else "USB",
        vendor="Logitech",
    )
    if level is None:
        device.status = UNSUPPORTED
        device.detail = "此设备未提供电量接口"
    else:
        device.level = level
        device.charging = charging
        device.detail = "电压估算" if source == "voltage" else ""
    return device


def scan_logitech(ifaces: list[devapi.HidInterface] | None = None):
    """扫描罗技 HID++ 设备，返回 (设备列表, 已被接管的容器 ID)。"""
    ifaces = devapi.scan_hid_interfaces() if ifaces is None else ifaces
    devices: list[Device] = []
    skip_containers: set[str] = set()
    seen_paths: set[str] = set()
    for itf in ifaces:
        if itf.vendor_id != LOGITECH or itf.usage_page != 0xFF00:
            continue
        if itf.path in seen_paths:
            continue
        seen_paths.add(itf.path)
        if itf.container_id:
            skip_containers.add(itf.container_id)
        dev = devapi.HidDevice(itf.path)
        if not dev.valid or not dev.caps:
            dev.close()
            continue
        try:
            link = HidppLink(dev)
            product = itf.product or "罗技设备"
            receiver = (
                itf.product_id in RECEIVER_PIDS
                or "receiver" in product.lower()
                or "接收器" in product
            )
            name_cache: dict[int, str] = {}

            def dev_name(index: int) -> str:
                if index not in name_cache:
                    name_cache[index] = link.device_name(index)
                return name_cache[index]

            if receiver:
                indexes = list(range(1, 7))
            else:
                # 有些接收器的 PID 不在已知列表、产品名里也没有 receiver，
                # 先按单设备位（0xFF）试一次，失败再扫 1–6 号位。
                if dev_name(0xFF):
                    indexes = [0xFF]
                else:
                    indexes = list(range(1, 7))
                    if any(dev_name(i) for i in indexes):
                        receiver = True
            found = False
            for index in indexes:
                name = dev_name(index)
                if not name:
                    continue
                found = True
                devices.append(_logi_device(product, index, name, link, receiver))
            if receiver and not found:
                skip_containers.add(itf.container_id or "")
        finally:
            dev.close()
    return devices, skip_containers


# ------------------------------------------------------------------ 统一发现
def _huawei_read(dev: devapi.HidDevice, item: int, timeout_ms: int = 1100) -> bytes | None:
    """在华为接收器的厂商通道上读一个数据项，返回其负载；无应答返回 None。"""
    if not dev.valid or not dev.caps:
        return None
    out_len = int(dev.caps.OutputReportByteLength or 0)
    in_len = int(dev.caps.InputReportByteLength or 0)
    if out_len < 4 or in_len < 6:
        return None
    frame = bytes([0x05, _HW_GET, 0x00, item]) + bytes(out_len - 4)
    if not dev.write(frame, timeout_ms=400):
        return None
    deadline = time.time() + timeout_ms / 1000.0
    while time.time() < deadline:
        data = dev.read(in_len, timeout_ms=150)
        if not data or len(data) < 6:
            continue
        if data[0] == 0x05 and data[1] == _HW_READ_ACK and data[3] == item:
            return data[5:5 + min(int(data[4]), len(data) - 5)]
    return None


def _huawei_battery(itf: devapi.HidInterface) -> tuple[int, bool] | None:
    """查询华为/荣耀无线鼠标电量，返回 (百分比, 是否充电)。"""
    for attempt in range(2):
        dev = devapi.HidDevice(itf.path)
        if not dev.valid or not dev.caps:
            dev.close()
            continue
        try:
            payload = _huawei_read(dev, HUAWEI_BATTERY_ITEM,
                                   timeout_ms=1100 if attempt == 0 else 700)
            if not payload or len(payload) < 5:
                continue
            level, state = int(payload[3]), int(payload[4])
            if 0 <= level <= 100:
                return level, state == 1
        finally:
            dev.close()
    return None


def scan_huawei(ttl: float = 60.0,
                ifaces: list[devapi.HidInterface] | None = None) -> dict[str, tuple[int, bool]]:
    """扫描华为/荣耀接收器，返回 {容器 ID: (电量, 充电中)}。

    查询会让接收器把无线链路叫醒，因此默认缓存 60 秒；手动刷新时传 ttl=0。
    """
    ifaces = devapi.scan_hid_interfaces() if ifaces is None else ifaces
    return _scan_vendor(
        ifaces,
        lambda i: (i.vendor_id == HUAWEI_VID and i.usage_page == HUAWEI_STATUS_PAGE
                   and i.out_len >= 4),
        _huawei_battery, _HW_CACHE, ttl,
    )


# ---------------------------------------------------------------- Razer
# 90 字节 Feature Report，命令类 0x02 / 命令 0x07，XOR 校验；电量 0–255 缩放到百分比。
# 协议来自 OpenRazer 与 Fan4Metal/mouse_tray 的公开实现（transaction id 0x1F 家族）。
RAZER_VID = 0x1532
RAZER_PIDS = {
    0x00A5, 0x00A6, 0x00B6, 0x00B7, 0x00BE, 0x00BF,   # Viper V2/V3 Pro、DeathAdder V3/V4 Pro
    0x00AA, 0x00AB, 0x00CC, 0x00CD,                   # Basilisk V3 Pro / 35K
    0x0086, 0x0088, 0x00AF, 0x00B0,                   # Basilisk Ultimate、Cobra Pro
    0x008F, 0x0090, 0x00A7, 0x00A8,                   # Naga Pro / V2 Pro
    0x006F, 0x0070, 0x00D0, 0x00D1,                   # Lancehead Wireless、Pro Click V2
}
_RAZER_TRANSACTION = 0x1F


def _razer_battery(itf: devapi.HidInterface) -> tuple[int, bool] | None:
    dev = devapi.HidDevice(itf.path)
    if not dev.valid or not dev.caps or not dev.writable:
        dev.close()
        return None
    try:
        size = int(dev.caps.FeatureReportByteLength or 0)
        if size < 16:
            return None
        header = [0x00, _RAZER_TRANSACTION, 0x00, 0x00, 0x00, 0x02, 0x07, 0x80]
        crc = 0
        for b in header[2:]:
            crc ^= b
        payload = bytes([0x00] + header + [0] * 80 + [crc, 0])
        if not dev.set_feature((payload + bytes(size))[:size]):
            return None
        time.sleep(0.3)
        report = dev.get_feature(0, size)
        if not report or len(report) <= 10:
            return None
        raw = int(report[10])
        return (round(raw / 255 * 100), False) if raw else None
    finally:
        dev.close()


def scan_razer(ttl: float = 60.0,
               ifaces: list[devapi.HidInterface] | None = None) -> dict[str, tuple[int, bool]]:
    """扫描 Razer 无线鼠标，返回 {容器 ID: (电量, 充电中)}。"""
    ifaces = devapi.scan_hid_interfaces() if ifaces is None else ifaces
    return _scan_vendor(
        ifaces,
        lambda i: (i.vendor_id == RAZER_VID and i.product_id in RAZER_PIDS
                   and i.feature_len >= 88),
        _razer_battery, _RZ_CACHE, ttl,
    )


# ---------------------------------------------------------------- Compx / Nordic 方案
# 这不是某一家品牌的私有格式，而是 Compx（Nordic 52840 / 54L15）公版方案的协议，
# 大量国产 2.4G 鼠标贴牌共用。协议字段来自公开开源实现：
#   Fan4Metal/mouse_tray（nordic52 / nordic54 驱动）
#   yszyszysz233/2.4G-battery-viewer（ATK/VXE 双协议）
COMPX_VIDS = {
    0x373B,  # ATK / VXE / VGN
    0x3554,  # VXE / VGN / Zaopin / Scyrox
    0x260D,  # Dareu 达尔优
    0x33E4,  # G-Wolves
}
COMPX_PAGE_52 = 0xFF02   # Nordic 52840：17 字节报文
COMPX_PAGE_54 = 0xFF05   # Nordic 54L15：64 字节报文

# 08 04 00×14 49 —— 末字节是校验（整帧 17 字节之和为 0x55）
COMPX_FRAME_52 = bytes([0x08, 0x04]) + bytes(14) + bytes([0x49])
# 08 7D 72 02 00 01 07 01，回复 [1]=0x72、[5]=0x07、电量在 [7]
COMPX_FRAME_54 = bytes([0x08, 0x7D, 0x72, 0x02, 0x00, 0x01, 0x07, 0x01])


def _exchange(dev: devapi.HidDevice, request: bytes, size: int,
              expect: tuple[tuple[int, int], ...] = (),
              wait_ms: int = 130, tries: int = 3) -> bytes | None:
    """发一帧 Output Report，等一条匹配的 Input Report（只读查询）。"""
    if not dev.valid or not dev.caps or not dev.writable:
        return None
    in_len = int(dev.caps.InputReportByteLength or 0)
    if in_len <= 0 or len(request) > size:
        return None
    body = request + bytes(size - len(request))
    last = None
    for _ in range(max(1, tries)):
        for _ in range(6):                      # 丢掉队列里陈旧的报文
            dev.read(in_len, timeout_ms=8)
        if not dev.write(body, timeout_ms=300):
            return last
        deadline = time.time() + wait_ms / 1000.0
        while time.time() < deadline:
            report = dev.read(in_len, timeout_ms=60)
            if not report:
                continue
            last = report
            if not expect or all(len(report) > off and report[off] == val
                                 for off, val in expect):
                return report
    return last


def _compx_battery(itf: devapi.HidInterface) -> tuple[int, bool] | None:
    """Compx 方案读电量，返回 (百分比, 是否充电)。"""
    dev = devapi.HidDevice(itf.path)
    if not dev.valid or not dev.caps:
        dev.close()
        return None
    try:
        if itf.usage_page == COMPX_PAGE_52:
            report = _exchange(dev, COMPX_FRAME_52, 17, ((0, 0x08), (1, 0x04)))
            if not report or len(report) < 8:
                return None
            if int(report[0]) != 0x08 or int(report[1]) != 0x04:
                return None          # 收到的是别的报告（如鼠标移动），不能当电量
            level, wired = int(report[6]), bool(report[7])
        else:
            report = _exchange(dev, COMPX_FRAME_54, 64, ((1, 0x72), (5, 0x07)))
            if not report or len(report) < 8:
                return None
            if int(report[1]) != 0x72 or int(report[5]) != 0x07:
                return None
            level, wired = int(report[7]), False
        if not 0 <= level <= 100:
            return None
        return level, wired and level < 100
    finally:
        dev.close()


def scan_compx(ttl: float = 60.0,
               ifaces: list[devapi.HidInterface] | None = None) -> dict[str, tuple[int, bool]]:
    """扫描 Compx 方案鼠标，返回 {容器 ID: (电量, 充电中)}。"""
    ifaces = devapi.scan_hid_interfaces() if ifaces is None else ifaces
    # 同 VID 下可能还有键盘（例如 373B 的磁轴键盘），只在确实是鼠标的容器上查询
    mice = {
        i.container_id for i in ifaces
        if i.container_id and i.usage_page == 0x01 and i.usage in (0x01, 0x02)
    }
    return _scan_vendor(
        ifaces,
        lambda i: (i.vendor_id in COMPX_VIDS
                   and i.usage_page in (COMPX_PAGE_52, COMPX_PAGE_54)
                   and i.out_len >= 17 and i.container_id in mice),
        _compx_battery, _CX_CACHE, ttl,
    )


def _is_known_vendor_channel(itf: devapi.HidInterface) -> bool:
    return bool(
        (itf.vendor_id == HUAWEI_VID and itf.usage_page == HUAWEI_STATUS_PAGE)
        or (itf.vendor_id in COMPX_VIDS
            and itf.usage_page in (COMPX_PAGE_52, COMPX_PAGE_54))
        or (itf.vendor_id == RAZER_VID and itf.product_id in RAZER_PIDS)
    )


def discover(demo: bool = False, force: bool = False) -> list[Device]:
    if demo:
        return _demo_devices()

    ifaces = devapi.scan_hid_interfaces()
    nodes = devapi.scan_pnp_nodes()
    classes = group_container_classes(nodes)
    connected_map = bluetooth_connection_map()
    devices: dict[str, Device] = {}

    # 1) 带电量属性的蓝牙/系统设备
    bt_containers: set[str] = set()
    bt_groups: dict[str, list[devapi.PnpNode]] = defaultdict(list)
    for node in nodes:
        if node.battery is not None:
            bt_groups[node.container_id or node.instance_id].append(node)

    for key, group in bt_groups.items():
        bt_containers.add(key)
        names = [clean_bt_name(n.name) for n in group]
        name = min((x for x in names if x), key=len, default="蓝牙设备")
        kind = infer_kind(name, classes.get(key))
        level = max(n.battery or 0 for n in group)
        mac = next((m for m in (_bt_mac(n.instance_id) for n in group) if m), None)
        is_bt = any(n.enumerator in ("BTHENUM", "BTHLE") for n in group)
        connected = True
        if is_bt and connected_map and mac and mac in connected_map:
            connected = bool(connected_map[mac])
        device = Device(
            key=f"bt:{mac or key}",
            name=name,
            kind=kind,
            transport="蓝牙" if is_bt else "USB",
            status=ONLINE if connected else OFFLINE,
            level=level if connected else None,
            last_level=level,
            detail="" if connected else "设备未连接，显示上次电量",
        )
        devices[device.key] = device

    # 2) 罗技 HID++（2.4G 接收器 / 有线）
    logi_devices, logi_containers = scan_logitech(ifaces)
    for device in logi_devices:
        devices[device.key] = device

    # 3) 其余 HID 外设（私有协议电量、标准电池接口或明确不支持）
    ttl = 0 if force else 60.0
    vendor_battery = {
        **scan_huawei(ttl, ifaces),
        **scan_compx(ttl, ifaces),
        **scan_razer(ttl, ifaces),
    }
    hid_groups: dict[str, list[devapi.HidInterface]] = defaultdict(list)
    for itf in ifaces:
        cid = itf.container_id or ""
        if not cid or cid.startswith("00000000-0000-0000-ffff"):
            continue
        if cid in logi_containers:
            continue
        hid_groups[cid].append(itf)

    for cid, group in hid_groups.items():
        if cid in bt_containers:
            continue
        cls = classes.get(cid, set())
        name = next((i.product for i in group if i.product), "")
        if not name:
            name = next((n.name for n in nodes if n.container_id == cid and n.name), "HID 设备")
        kind = infer_kind(name, cls)
        if kind == OTHER:
            continue
        is_bt = any(i.instance_id.upper().startswith(("BTHENUM", "BTHLE")) for i in group)
        known = vendor_battery.get(cid)
        if known is not None:
            level, charging = known
            devices[f"hid:{cid}"] = Device(
                key=f"hid:{cid}",
                name=name,
                kind=kind,
                transport="2.4G",
                level=level,
                charging=charging,
            )
            continue

        level, charging = None, False
        for itf in group:
            if itf.feature_len <= 0 and itf.in_len <= 0:
                continue
            got = devapi.read_hid_battery(itf)
            if got is not None:
                level, charging = got
                break

        # 已知厂商通道在、但这轮没应答：这是"设备休眠/离线"，不是"不支持"
        if level is None and any(_is_known_vendor_channel(i) for i in group):
            devices[f"hid:{cid}"] = Device(
                key=f"hid:{cid}",
                name=name,
                kind=kind,
                transport="2.4G",
                status=OFFLINE,
                detail="设备未应答，显示上次电量",
            )
            continue

        status = ONLINE if level is not None else UNSUPPORTED
        detail = ""
        transport = "蓝牙" if is_bt else "USB"
        if level is None:
            # 容器里存在厂商自定义用量页（0xFF00+）说明设备有私有通道，
            # 只是协议还没适配——和"硬件根本没有电量"要分开告诉用户。
            if any(i.usage_page >= 0xFF00 for i in group):
                detail = "厂商私有协议，暂未适配"
                if not is_bt and _looks_wireless(name, group):
                    transport = "2.4G"
            else:
                detail = "设备未提供电量接口"

        mac = _bt_mac(group[0].instance_id) if is_bt else None
        key = f"bt:{mac}" if mac else f"hid:{cid}"
        if key not in devices:
            devices[key] = Device(
                key=key,
                name=name,
                kind=kind,
                transport=transport,
                status=status,
                level=level,
                charging=charging,
                detail=detail,
            )

    return sorted(devices.values(), key=lambda d: d.sort_key())


# ------------------------------------------------------------------ 演示数据
_DEMO = [
    ("demo:mouse", "MX Master 3S", MOUSE, "2.4G", 87, False),
    ("demo:keyboard", "MX Keys Mini", KEYBOARD, "蓝牙", 64, False),
    ("demo:headset", "HUAWEI FreeBuds 6i", HEADSET, "蓝牙", 41, False),
]


def _demo_devices() -> list[Device]:
    drift = int(time.time() // 20) % 3
    return [
        Device(key=key, name=name, kind=kind, transport=transport, status=ONLINE,
               level=max(5, min(100, level + (drift if i == 0 else -drift))),
               charging=charging)
        for i, (key, name, kind, transport, level, charging) in enumerate(_DEMO)
    ]
