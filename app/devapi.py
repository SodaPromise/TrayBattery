"""设备层 Win32 封装：SetupAPI 设备枚举、设备属性、HID 访问。"""
from __future__ import annotations

import ctypes
import uuid
from ctypes import wintypes as w
from dataclasses import dataclass

from . import win32 as k

setupapi = ctypes.WinDLL("setupapi", use_last_error=True)
hid = ctypes.WinDLL("hid", use_last_error=True)

HDEVINFO = ctypes.c_void_p
SP_DEVINFO_DATA = ctypes.c_void_p
HANDLE = ctypes.c_void_p
BOOL = w.BOOL
DWORD = w.DWORD
ULONG = w.ULONG
UCHAR = ctypes.c_ubyte
BOOLEAN = ctypes.c_ubyte
NTSTATUS = ctypes.c_long
GUID = ctypes.c_void_p

DIGCF_PRESENT = 0x00000002
DIGCF_ALLCLASSES = 0x00000004
DIGCF_DEVICEINTERFACE = 0x00000010

SPDRP_DEVICEDESC = 0x00000000
SPDRP_CLASS = 0x00000007
SPDRP_FRIENDLYNAME = 0x0000000C

DEVPROP_TYPE_STRING = 0x00000012
DEVPROP_TYPE_UINT32 = 0x00000007
DEVPROP_TYPE_BYTE = 0x00000003
DEVPROP_TYPE_GUID = 0x0000000D

ERROR_NO_MORE_ITEMS = 259
ERROR_INSUFFICIENT_BUFFER = 122

GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
OPEN_EXISTING = 3
FILE_FLAG_OVERLAPPED = 0x40000000
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

HidP_Input = 0
HidP_Feature = 2

IOCTL_HID_GET_REPORT_DESCRIPTOR = 0x000B0003  # HID_CTL_CODE(0), METHOD_NEITHER


class GUIDStruct(ctypes.Structure):
    _fields_ = [
        ("Data1", w.DWORD),
        ("Data2", w.WORD),
        ("Data3", w.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]


def guid(text: str) -> GUIDStruct:
    g = GUIDStruct()
    ctypes.memmove(ctypes.byref(g), uuid.UUID(text).bytes_le, 16)
    return g


class DEVPROPKEY(ctypes.Structure):
    _fields_ = [("fmtid", GUIDStruct), ("pid", w.ULONG)]


def propkey(text: str, pid: int) -> DEVPROPKEY:
    return DEVPROPKEY(guid(text), pid)


KEY_FRIENDLY_NAME = propkey("{A45C254E-DF1C-4EFD-8020-67D146A850E0}", 14)
KEY_CONTAINER_ID = propkey("{8C7ED206-3F8A-4827-B3AB-AE9E1FAEFC6C}", 2)
KEY_BLUETOOTH_BATTERY = propkey("{104EA319-6EE2-4701-BD47-8DDBF425BBE5}", 2)


class SP_DEVINFO_DATA(ctypes.Structure):
    _fields_ = [
        ("cbSize", w.DWORD),
        ("ClassGuid", GUIDStruct),
        ("DevInst", w.DWORD),
        ("Reserved", ctypes.c_size_t),
    ]


class SP_DEVICE_INTERFACE_DATA(ctypes.Structure):
    _fields_ = [
        ("cbSize", w.DWORD),
        ("InterfaceClassGuid", GUIDStruct),
        ("Flags", w.DWORD),
        ("Reserved", ctypes.c_size_t),
    ]


class HIDD_ATTRIBUTES(ctypes.Structure):
    _fields_ = [
        ("Size", w.ULONG),
        ("VendorID", w.USHORT),
        ("ProductID", w.USHORT),
        ("VersionNumber", w.USHORT),
    ]


class HIDP_CAPS(ctypes.Structure):
    _fields_ = [
        ("Usage", w.USHORT),
        ("UsagePage", w.USHORT),
        ("InputReportByteLength", w.USHORT),
        ("OutputReportByteLength", w.USHORT),
        ("FeatureReportByteLength", w.USHORT),
        ("Reserved", w.USHORT * 17),
        ("NumberLinkCollectionNodes", w.ULONG),
        ("NumberInputButtonCaps", w.ULONG),
        ("NumberInputValueCaps", w.ULONG),
        ("NumberInputDataIndices", w.ULONG),
        ("NumberOutputButtonCaps", w.ULONG),
        ("NumberOutputValueCaps", w.ULONG),
        ("NumberOutputDataIndices", w.ULONG),
        ("NumberFeatureButtonCaps", w.ULONG),
        ("NumberFeatureValueCaps", w.ULONG),
        ("NumberFeatureDataIndices", w.ULONG),
    ]


class _ValueUnion(ctypes.Union):
    class _Range(ctypes.Structure):
        _fields_ = [
            ("UsageMin", w.USHORT), ("UsageMax", w.USHORT),
            ("StringMin", w.USHORT), ("StringMax", w.USHORT),
            ("DesignatorMin", w.USHORT), ("DesignatorMax", w.USHORT),
            ("DataIndexMin", w.USHORT), ("DataIndexMax", w.USHORT),
        ]

    class _NotRange(ctypes.Structure):
        _fields_ = [
            ("Usage", w.USHORT), ("Reserved1", w.USHORT),
            ("StringIndex", w.USHORT), ("Reserved2", w.USHORT),
            ("DesignatorIndex", w.USHORT), ("Reserved3", w.USHORT),
            ("DataIndex", w.USHORT), ("Reserved4", w.USHORT),
        ]

    _fields_ = [("Range", _Range), ("NotRange", _NotRange)]


class HIDP_VALUE_CAPS(ctypes.Structure):
    _fields_ = [
        ("UsagePage", w.USHORT),
        ("ReportID", UCHAR),
        ("IsAlias", BOOLEAN),
        ("BitField", w.USHORT),
        ("LinkCollection", w.USHORT),
        ("LinkUsage", w.USHORT),
        ("LinkUsagePage", w.USHORT),
        ("IsRange", BOOLEAN),
        ("IsStringRange", BOOLEAN),
        ("IsDesignatorRange", BOOLEAN),
        ("IsAbsolute", BOOLEAN),
        ("HasNull", BOOLEAN),
        ("Reserved", UCHAR),
        ("BitSize", w.USHORT),
        ("ReportCount", w.USHORT),
        ("Reserved2", w.USHORT * 5),
        ("UnitsExp", w.ULONG),
        ("Units", w.ULONG),
        ("LogicalMin", w.LONG),
        ("LogicalMax", w.LONG),
        ("PhysicalMin", w.LONG),
        ("PhysicalMax", w.LONG),
        ("u", _ValueUnion),
    ]


class OVERLAPPED(ctypes.Structure):
    _fields_ = [
        ("Internal", ctypes.c_size_t),
        ("InternalHigh", ctypes.c_size_t),
        ("Offset", w.DWORD),
        ("OffsetHigh", w.DWORD),
        ("hEvent", HANDLE),
    ]


def _f(dll, name, restype, *argtypes):
    fn = getattr(dll, name)
    fn.restype = restype
    fn.argtypes = argtypes
    return fn


SetupDiGetClassDevsW = _f(setupapi, "SetupDiGetClassDevsW", HDEVINFO, ctypes.POINTER(GUIDStruct), w.LPCWSTR, w.HWND, w.DWORD)
SetupDiDestroyDeviceInfoList = _f(setupapi, "SetupDiDestroyDeviceInfoList", BOOL, HDEVINFO)
SetupDiEnumDeviceInfo = _f(setupapi, "SetupDiEnumDeviceInfo", BOOL, HDEVINFO, w.DWORD, ctypes.POINTER(SP_DEVINFO_DATA))
SetupDiGetDeviceInstanceIdW = _f(setupapi, "SetupDiGetDeviceInstanceIdW", BOOL, HDEVINFO, ctypes.POINTER(SP_DEVINFO_DATA), w.LPWSTR, w.DWORD, ctypes.POINTER(w.DWORD))
SetupDiGetDevicePropertyW = _f(setupapi, "SetupDiGetDevicePropertyW", BOOL, HDEVINFO, ctypes.POINTER(SP_DEVINFO_DATA), ctypes.POINTER(DEVPROPKEY), ctypes.POINTER(w.DWORD), ctypes.POINTER(w.BYTE), w.DWORD, ctypes.POINTER(w.DWORD), w.DWORD)
SetupDiGetDeviceRegistryPropertyW = _f(setupapi, "SetupDiGetDeviceRegistryPropertyW", BOOL, HDEVINFO, ctypes.POINTER(SP_DEVINFO_DATA), w.DWORD, ctypes.POINTER(w.DWORD), ctypes.POINTER(w.BYTE), w.DWORD, ctypes.POINTER(w.DWORD))
SetupDiEnumDeviceInterfaces = _f(setupapi, "SetupDiEnumDeviceInterfaces", BOOL, HDEVINFO, ctypes.POINTER(SP_DEVINFO_DATA), ctypes.POINTER(GUIDStruct), w.DWORD, ctypes.POINTER(SP_DEVICE_INTERFACE_DATA))
SetupDiGetDeviceInterfaceDetailW = _f(setupapi, "SetupDiGetDeviceInterfaceDetailW", BOOL, HDEVINFO, ctypes.POINTER(SP_DEVICE_INTERFACE_DATA), ctypes.c_void_p, w.DWORD, ctypes.POINTER(w.DWORD), ctypes.POINTER(SP_DEVINFO_DATA))

HidD_GetHidGuid = _f(hid, "HidD_GetHidGuid", None, ctypes.POINTER(GUIDStruct))
HidD_GetAttributes = _f(hid, "HidD_GetAttributes", BOOL, HANDLE, ctypes.POINTER(HIDD_ATTRIBUTES))
HidD_GetPreparsedData = _f(hid, "HidD_GetPreparsedData", BOOL, HANDLE, ctypes.POINTER(ctypes.c_void_p))
HidD_FreePreparsedData = _f(hid, "HidD_FreePreparsedData", BOOL, ctypes.c_void_p)
HidP_GetCaps = _f(hid, "HidP_GetCaps", NTSTATUS, ctypes.c_void_p, ctypes.POINTER(HIDP_CAPS))
HidP_GetValueCaps = _f(hid, "HidP_GetValueCaps", NTSTATUS, ctypes.c_int, ctypes.POINTER(HIDP_VALUE_CAPS), ctypes.POINTER(w.USHORT), ctypes.c_void_p)
HidP_GetUsageValue = _f(hid, "HidP_GetUsageValue", NTSTATUS, ctypes.c_int, w.USHORT, w.USHORT, w.USHORT, ctypes.POINTER(w.ULONG), ctypes.c_void_p, ctypes.c_char_p, w.ULONG)
HidD_GetFeature = _f(hid, "HidD_GetFeature", BOOL, HANDLE, ctypes.c_void_p, w.ULONG)
HidD_GetInputReport = _f(hid, "HidD_GetInputReport", BOOL, HANDLE, ctypes.c_void_p, w.ULONG)
HidD_SetFeature = _f(hid, "HidD_SetFeature", BOOL, HANDLE, ctypes.c_void_p, w.ULONG)
HidD_GetProductString = _f(hid, "HidD_GetProductString", BOOL, HANDLE, ctypes.c_void_p, w.ULONG)
HidD_GetManufacturerString = _f(hid, "HidD_GetManufacturerString", BOOL, HANDLE, ctypes.c_void_p, w.ULONG)
HidD_GetSerialNumberString = _f(hid, "HidD_GetSerialNumberString", BOOL, HANDLE, ctypes.c_void_p, w.ULONG)

CreateFileW = _f(k.kernel32, "CreateFileW", HANDLE, w.LPCWSTR, w.DWORD, w.DWORD, ctypes.c_void_p, w.DWORD, w.DWORD, HANDLE)
CreateEventW = _f(k.kernel32, "CreateEventW", HANDLE, ctypes.c_void_p, BOOL, BOOL, w.LPCWSTR)
WaitForSingleObject = _f(k.kernel32, "WaitForSingleObject", w.DWORD, HANDLE, w.DWORD)
GetOverlappedResult = _f(k.kernel32, "GetOverlappedResult", BOOL, HANDLE, ctypes.POINTER(OVERLAPPED), ctypes.POINTER(w.DWORD), BOOL)
CancelIoEx = _f(k.kernel32, "CancelIoEx", BOOL, HANDLE, ctypes.POINTER(OVERLAPPED))
ResetEvent = _f(k.kernel32, "ResetEvent", BOOL, HANDLE)
WriteFile = _f(k.kernel32, "WriteFile", BOOL, HANDLE, ctypes.c_char_p, w.DWORD, ctypes.POINTER(w.DWORD), ctypes.POINTER(OVERLAPPED))
ReadFile = _f(k.kernel32, "ReadFile", BOOL, HANDLE, ctypes.c_void_p, w.DWORD, ctypes.POINTER(w.DWORD), ctypes.POINTER(OVERLAPPED))
DeviceIoControl = _f(k.kernel32, "DeviceIoControl", BOOL, HANDLE, w.DWORD, ctypes.c_void_p, w.DWORD,
                     ctypes.c_void_p, w.DWORD, ctypes.POINTER(w.DWORD), ctypes.c_void_p)


# ------------------------------------------------------------------ 设备属性
def _read_prop(hdev, did: SP_DEVINFO_DATA, key: DEVPROPKEY):
    ptype = w.DWORD(0)
    needed = w.DWORD(0)
    buf = ctypes.create_string_buffer(2048)
    ok = SetupDiGetDevicePropertyW(
        hdev, ctypes.byref(did), ctypes.byref(key), ctypes.byref(ptype),
        ctypes.cast(buf, ctypes.POINTER(w.BYTE)), len(buf), ctypes.byref(needed), 0,
    )
    if not ok:
        return None, None
    t = ptype.value
    if t == DEVPROP_TYPE_UINT32:
        return ctypes.cast(buf, ctypes.POINTER(w.DWORD)).contents.value, t
    if t == DEVPROP_TYPE_BYTE:
        return ctypes.cast(buf, ctypes.POINTER(w.BYTE)).contents.value, t
    if t == DEVPROP_TYPE_STRING:
        return buf.raw[: needed.value or len(buf)].decode("utf-16-le", "ignore").split("\x00")[0], t
    if t == DEVPROP_TYPE_GUID:
        g = ctypes.cast(buf, ctypes.POINTER(GUIDStruct)).contents
        raw = ctypes.string_at(ctypes.byref(g), 16)
        return uuid.UUID(bytes_le=raw), t
    return None, t


def _read_reg_prop(hdev, did: SP_DEVINFO_DATA, prop: int):
    reg_type = w.DWORD(0)
    needed = w.DWORD(0)
    buf = ctypes.create_string_buffer(2048)
    ok = SetupDiGetDeviceRegistryPropertyW(
        hdev, ctypes.byref(did), prop, ctypes.byref(reg_type),
        ctypes.cast(buf, ctypes.POINTER(w.BYTE)), len(buf), ctypes.byref(needed),
    )
    if not ok:
        return None
    if reg_type.value in (1, 2):  # REG_SZ / REG_EXPAND_SZ
        return buf.raw[: needed.value or len(buf)].decode("utf-16-le", "ignore").split("\x00")[0]
    return None


@dataclass
class PnpNode:
    instance_id: str
    name: str
    class_name: str
    container_id: str | None
    enumerator: str
    battery: int | None = None


def scan_pnp_nodes() -> list[PnpNode]:
    """枚举所有在线设备节点（含类名、容器 ID、可用电量）。"""
    out: list[PnpNode] = []
    hdev = SetupDiGetClassDevsW(None, None, None, DIGCF_PRESENT | DIGCF_ALLCLASSES)
    if not hdev or hdev == INVALID_HANDLE_VALUE:
        return out
    try:
        idx = 0
        did = SP_DEVINFO_DATA()
        did.cbSize = ctypes.sizeof(SP_DEVINFO_DATA)
        while True:
            if not SetupDiEnumDeviceInfo(hdev, idx, ctypes.byref(did)):
                break
            idx += 1
            iid_buf = ctypes.create_unicode_buffer(512)
            if not SetupDiGetDeviceInstanceIdW(hdev, ctypes.byref(did), iid_buf, 512, None):
                continue
            iid = iid_buf.value
            enumerator = iid.split("\\", 1)[0].upper()
            if enumerator in ("ROOT", "SWD", "ACPI", "DISPLAY", "PCI", "SCSI", "STORAGE"):
                continue
            name = (_read_prop(hdev, did, KEY_FRIENDLY_NAME)[0] or ""
                    or _read_reg_prop(hdev, did, SPDRP_FRIENDLYNAME) or ""
                    or _read_reg_prop(hdev, did, SPDRP_DEVICEDESC) or "")
            cls = _read_reg_prop(hdev, did, SPDRP_CLASS) or ""
            cid = _read_prop(hdev, did, KEY_CONTAINER_ID)[0]
            level, ptype = _read_prop(hdev, did, KEY_BLUETOOTH_BATTERY)
            battery = None
            if isinstance(level, int) and ptype in (DEVPROP_TYPE_BYTE, DEVPROP_TYPE_UINT32) and 0 <= level <= 100:
                battery = int(level)
            out.append(PnpNode(
                instance_id=iid,
                name=str(name).strip(),
                class_name=str(cls).strip(),
                container_id=str(cid) if cid else None,
                enumerator=enumerator,
                battery=battery,
            ))
    finally:
        SetupDiDestroyDeviceInfoList(hdev)
    return out


# ------------------------------------------------------------------ HID
@dataclass
class HidInterface:
    path: str
    vendor_id: int
    product_id: int
    version: int
    product: str
    manufacturer: str
    usage_page: int
    usage: int
    in_len: int
    out_len: int
    feature_len: int
    instance_id: str = ""
    class_name: str = ""
    container_id: str | None = None

    @property
    def vid_pid(self) -> str:
        return f"{self.vendor_id:04x}:{self.product_id:04x}"


def _hid_guid() -> GUIDStruct:
    g = GUIDStruct()
    HidD_GetHidGuid(ctypes.byref(g))
    return g


def _device_interface_paths() -> list[tuple[str, dict]]:
    """枚举 HID 设备接口，附带所属设备节点的类名与容器 ID。"""
    out: list[tuple[str, dict]] = []
    g = _hid_guid()
    hdev = SetupDiGetClassDevsW(ctypes.byref(g), None, None, DIGCF_PRESENT | DIGCF_DEVICEINTERFACE)
    if not hdev or hdev == INVALID_HANDLE_VALUE:
        return out
    try:
        idx = 0
        did = SP_DEVINFO_DATA()
        did.cbSize = ctypes.sizeof(SP_DEVINFO_DATA)
        while True:
            if not SetupDiEnumDeviceInfo(hdev, idx, ctypes.byref(did)):
                break
            idx += 1
            inst = ctypes.create_unicode_buffer(512)
            SetupDiGetDeviceInstanceIdW(hdev, ctypes.byref(did), inst, 512, None)
            klass = _read_reg_prop(hdev, did, SPDRP_CLASS) or ""
            cid = _read_prop(hdev, did, KEY_CONTAINER_ID)[0]
            meta = {
                "instance_id": inst.value,
                "class_name": str(klass),
                "container_id": str(cid) if cid else None,
            }
            iface = SP_DEVICE_INTERFACE_DATA()
            iface.cbSize = ctypes.sizeof(SP_DEVICE_INTERFACE_DATA)
            i = 0
            while SetupDiEnumDeviceInterfaces(hdev, ctypes.byref(did), ctypes.byref(g), i, ctypes.byref(iface)):
                i += 1
                needed = w.DWORD(0)
                SetupDiGetDeviceInterfaceDetailW(hdev, ctypes.byref(iface), None, 0, ctypes.byref(needed), None)
                if needed.value <= 0:
                    continue
                buf = ctypes.create_string_buffer(needed.value)
                core = SP_DEVINFO_DATA()
                core.cbSize = ctypes.sizeof(SP_DEVINFO_DATA)
                ctypes.cast(buf, ctypes.POINTER(w.DWORD))[0] = 8 if ctypes.sizeof(ctypes.c_void_p) == 8 else 6
                if SetupDiGetDeviceInterfaceDetailW(
                    hdev, ctypes.byref(iface), buf, needed.value, None, ctypes.byref(core)
                ):
                    path = ctypes.wstring_at(ctypes.addressof(buf) + ctypes.sizeof(w.DWORD))
                    if path:
                        out.append((path, meta))
    finally:
        SetupDiDestroyDeviceInfoList(hdev)
    return out


class HidDevice:
    """阻塞式封装的 Overlapped HID 句柄。"""

    def __init__(self, path: str) -> None:
        self.path = path
        self.writable = False
        handle = CreateFileW(
            path, GENERIC_READ | GENERIC_WRITE,
            FILE_SHARE_READ | FILE_SHARE_WRITE, None, OPEN_EXISTING, FILE_FLAG_OVERLAPPED, None,
        )
        if handle and handle != INVALID_HANDLE_VALUE:
            self.writable = True
        else:
            # 鼠标 / 键盘 / 触控板这类顶层集合被系统独占，读写权限会拿到
            # ERROR_ACCESS_DENIED；用 0 权限打开仍可读属性与 Feature Report。
            handle = CreateFileW(
                path, 0,
                FILE_SHARE_READ | FILE_SHARE_WRITE, None, OPEN_EXISTING,
                FILE_FLAG_OVERLAPPED, None,
            )
        self.handle = handle
        self.attrs = HIDD_ATTRIBUTES()
        self.attrs.Size = ctypes.sizeof(HIDD_ATTRIBUTES)
        self.caps: HIDP_CAPS | None = None
        self.product = ""
        self.manufacturer = ""
        if self.valid:
            HidD_GetAttributes(self.handle, ctypes.byref(self.attrs))
            self.product = self._string(HidD_GetProductString)
            self.manufacturer = self._string(HidD_GetManufacturerString)
            self.caps = self._caps()

    @property
    def valid(self) -> bool:
        return bool(self.handle) and self.handle != INVALID_HANDLE_VALUE

    def _string(self, fn) -> str:
        buf = ctypes.create_unicode_buffer(256)
        if fn(self.handle, buf, ctypes.sizeof(buf)):
            return buf.value.strip()
        return ""

    def _caps(self) -> HIDP_CAPS | None:
        pp = ctypes.c_void_p()
        if not HidD_GetPreparsedData(self.handle, ctypes.byref(pp)) or not pp:
            return None
        try:
            caps = HIDP_CAPS()
            if HidP_GetCaps(pp, ctypes.byref(caps)) < 0:
                return None
            return caps
        finally:
            HidD_FreePreparsedData(pp)

    def interface(self) -> HidInterface | None:
        if not self.valid or not self.caps:
            return None
        return HidInterface(
            path=self.path,
            vendor_id=self.attrs.VendorID,
            product_id=self.attrs.ProductID,
            version=self.attrs.VersionNumber,
            product=self.product,
            manufacturer=self.manufacturer,
            usage_page=self.caps.UsagePage,
            usage=self.caps.Usage,
            in_len=self.caps.InputReportByteLength,
            out_len=self.caps.OutputReportByteLength,
            feature_len=self.caps.FeatureReportByteLength,
        )
    # --- IO ---
    def _overlapped(self):
        ev = CreateEventW(None, True, False, None)
        ov = OVERLAPPED()
        ov.hEvent = ev
        return ev, ov

    def write(self, data: bytes, timeout_ms: int = 500) -> bool:
        if not self.valid or not self.writable:
            return False
        ev, ov = self._overlapped()
        try:
            written = w.DWORD(0)
            buf = ctypes.create_string_buffer(data, len(data))
            if WriteFile(self.handle, buf, len(data), ctypes.byref(written), ctypes.byref(ov)):
                return True
            if k.kernel32.GetLastError() != 997:  # ERROR_IO_PENDING
                return False
            if WaitForSingleObject(ev, timeout_ms) != 0:
                CancelIoEx(self.handle, ctypes.byref(ov))
                return False
            r = w.DWORD(0)
            return bool(GetOverlappedResult(self.handle, ctypes.byref(ov), ctypes.byref(r), False))
        finally:
            if ev:
                k.kernel32.CloseHandle(ev)

    def read(self, size: int, timeout_ms: int = 500) -> bytes | None:
        if not self.valid or size <= 0:
            return None
        ev, ov = self._overlapped()
        try:
            buf = ctypes.create_string_buffer(size)
            n = w.DWORD(0)
            if ReadFile(self.handle, buf, size, ctypes.byref(n), ctypes.byref(ov)):
                return buf.raw[: n.value]
            if k.kernel32.GetLastError() != 997:
                return None
            if WaitForSingleObject(ev, timeout_ms) != 0:
                CancelIoEx(self.handle, ctypes.byref(ov))
                return None
            if not GetOverlappedResult(self.handle, ctypes.byref(ov), ctypes.byref(n), False):
                return None
            return buf.raw[: n.value]
        finally:
            if ev:
                k.kernel32.CloseHandle(ev)

    def get_feature(self, report_id: int, size: int) -> bytes | None:
        if not self.valid:
            return None
        buf = ctypes.create_string_buffer(max(size, 2))
        if report_id:
            buf[0] = bytes([report_id])
        if HidD_GetFeature(self.handle, buf, len(buf)):
            return buf.raw[: len(buf)]
        return None

    def get_input_report(self, report_id: int, size: int) -> bytes | None:
        if not self.valid:
            return None
        buf = ctypes.create_string_buffer(max(size, 2))
        if report_id:
            buf[0] = bytes([report_id])
        if HidD_GetInputReport(self.handle, buf, len(buf)):
            return buf.raw[: len(buf)]
        return None

    def set_feature(self, data: bytes) -> bool:
        """写一条 Feature Report（data 首字节为 report ID）。"""
        if not self.valid or not self.writable or not data:
            return False
        buf = ctypes.create_string_buffer(bytes(data), len(data))
        return bool(HidD_SetFeature(self.handle, buf, len(data)))

    def close(self) -> None:
        if self.valid:
            k.kernel32.CloseHandle(self.handle)
        self.handle = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def scan_hid_interfaces() -> list[HidInterface]:
    out: list[HidInterface] = []
    for path, meta in _device_interface_paths():
        dev = HidDevice(path)
        try:
            itf = dev.interface()
            if itf:
                itf.instance_id = meta.get("instance_id", "")
                itf.class_name = meta.get("class_name", "")
                itf.container_id = meta.get("container_id")
                out.append(itf)
        finally:
            dev.close()
    return out


def report_descriptor(path: str, size: int = 4096) -> bytes:
    """读取 HID 报告描述符（诊断工具用）。"""
    handle = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE,
                         None, OPEN_EXISTING, 0, None)
    if not handle or handle == INVALID_HANDLE_VALUE:
        return b""
    try:
        buf = ctypes.create_string_buffer(size)
        got = w.DWORD(0)
        ok = DeviceIoControl(handle, IOCTL_HID_GET_REPORT_DESCRIPTOR, None, 0,
                             buf, size, ctypes.byref(got), None)
        return buf.raw[: got.value] if ok else b""
    finally:
        k.kernel32.CloseHandle(handle)


# 报告描述符里表示电量的标准 usage：(UsagePage, Usage, 说明)
BATTERY_USAGES: tuple[tuple[int, int, str], ...] = (
    (0x0006, 0x0020, "Battery Strength"),          # 通用设备控制页，最常见
    (0x000D, 0x003B, "Battery Strength（数字化仪）"),
    (0x0085, 0x0001, "Absolute State of Charge"),   # 电池系统页
    (0x0085, 0x0066, "Relative State of Charge"),
    (0x0085, 0x0065, "Battery Level"),
)


def _usage_span(vc: HIDP_VALUE_CAPS) -> tuple[int, int]:
    if vc.IsRange:
        return int(vc.u.Range.UsageMin), int(vc.u.Range.UsageMax)
    usage = int(vc.u.NotRange.Usage)
    return usage, usage


def _battery_usage(vc: HIDP_VALUE_CAPS) -> int | None:
    lo, hi = _usage_span(vc)
    for page, usage, _ in BATTERY_USAGES:
        if int(vc.UsagePage) == page and lo <= usage <= hi:
            return usage
    return None


def _normalize_battery(value: int, vc: HIDP_VALUE_CAPS) -> int | None:
    """按逻辑值域把原始读数换算成 0–100。"""
    lo, hi = int(vc.LogicalMin), int(vc.LogicalMax)
    if hi <= lo:
        return value if 0 <= value <= 100 else None
    if not lo <= value <= hi:
        return None
    if lo == 0 and hi == 100:
        return value
    return max(0, min(100, round((value - lo) * 100 / (hi - lo))))


def _value_caps(pp, report_type: int) -> list[HIDP_VALUE_CAPS]:
    count = w.USHORT(0)
    HidP_GetValueCaps(report_type, None, ctypes.byref(count), pp)
    if count.value <= 0:
        return []
    arr = (HIDP_VALUE_CAPS * count.value)()
    got = w.USHORT(count.value)
    if HidP_GetValueCaps(report_type, arr, ctypes.byref(got), pp) < 0:
        return []
    return [arr[i] for i in range(got.value)]


def read_hid_battery(itf: HidInterface) -> tuple[int, bool] | None:
    """按标准 HID 电量字段读一次，返回 (百分比, 是否充电)。

    先查 Feature Report（多数设备走这条），再退到 Input Report（少数设备
    把电量放在周期上报里）。字段按 usage 匹配，数值按 LogicalMin/Max 归一化，
    因此 0–100 与 0–255 两种量纲都能正确换算。
    """
    dev = HidDevice(itf.path)
    if not dev.valid or not dev.caps:
        dev.close()
        return None
    pp = ctypes.c_void_p()
    if not HidD_GetPreparsedData(dev.handle, ctypes.byref(pp)) or not pp:
        dev.close()
        return None
    try:
        sizes = (
            (HidP_Feature, int(dev.caps.FeatureReportByteLength)),
            (HidP_Input, int(dev.caps.InputReportByteLength)),
        )
        for report_type, size in sizes:
            if size <= 0:
                continue
            for vc in _value_caps(pp, report_type):
                usage = _battery_usage(vc)
                if usage is None:
                    continue
                rid = int(vc.ReportID)
                if report_type == HidP_Feature:
                    report = dev.get_feature(rid, size)
                else:
                    report = dev.read(size, timeout_ms=160)
                if not report:
                    continue
                value = w.ULONG(0)
                status = HidP_GetUsageValue(
                    report_type, int(vc.UsagePage), int(vc.LinkCollection), usage,
                    ctypes.byref(value), pp, report, len(report),
                )
                if status < 0:
                    continue
                level = _normalize_battery(int(value.value), vc)
                if level is not None:
                    return level, False
    finally:
        HidD_FreePreparsedData(pp)
        dev.close()
    return None


# ------------------------------------------------------------------ BLE GATT
# BLE 外设（HID over GATT）通常把电量放在标准 Battery Service 0x180F 的
# Battery Level 特征 0x2A19 上。Windows 有时会把它映射成
# DEVPKEY_Bluetooth_Battery，但 HOGP 的通用 HID 节点上常常没有这个属性，
# 此时直接读 GATT 是唯一可靠的取电路。全部用 Win32，不引入 WinRT 依赖。
GUID_BLE_DEVICE_INTERFACE = "781aee18-7733-4ce4-add0-91f41c67b592"
BLE_BATTERY_SERVICE = 0x180F
BLE_BATTERY_LEVEL = 0x2A19
_HRESULT_MORE_DATA = 0x800700EA


class _BthLeUuidValue(ctypes.Union):
    _fields_ = [("ShortUuid", w.USHORT), ("LongUuid", GUIDStruct)]


class _BthLeUuid(ctypes.Structure):
    _fields_ = [("IsShortUuid", ctypes.c_ubyte), ("Value", _BthLeUuidValue)]


class _GattService(ctypes.Structure):
    _fields_ = [("ServiceUuid", _BthLeUuid), ("AttributeHandle", w.USHORT)]


class _GattCharacteristic(ctypes.Structure):
    _fields_ = [
        ("ServiceHandle", w.USHORT),
        ("CharacteristicUuid", _BthLeUuid),
        ("AttributeHandle", w.USHORT),
        ("CharacteristicValueHandle", w.USHORT),
        ("IsBroadcastable", ctypes.c_ubyte),
        ("IsReadable", ctypes.c_ubyte),
        ("IsWritable", ctypes.c_ubyte),
        ("IsWritableWithoutResponse", ctypes.c_ubyte),
        ("IsSignedWritable", ctypes.c_ubyte),
        ("IsNotifiable", ctypes.c_ubyte),
        ("IsIndicatable", ctypes.c_ubyte),
        ("HasExtendedProperties", ctypes.c_ubyte),
    ]


class _GattValue(ctypes.Structure):
    _fields_ = [("DataSize", w.ULONG), ("Data", ctypes.c_ubyte * 512)]


_bluetooth_apis = None


def _gatt_api():
    """惰性绑定 BluetoothAPIs.dll；系统不支持时返回 None。"""
    global _bluetooth_apis
    if _bluetooth_apis is None:
        try:
            dll = ctypes.WinDLL("BluetoothAPIs")
        except OSError:
            _bluetooth_apis = False
            return None
        _bluetooth_apis = (
            _f(dll, "BluetoothGATTGetServices", ctypes.c_long, HANDLE, w.USHORT,
               ctypes.POINTER(_GattService), ctypes.POINTER(w.USHORT), w.ULONG),
            _f(dll, "BluetoothGATTGetCharacteristics", ctypes.c_long, HANDLE,
               ctypes.POINTER(_GattService), w.USHORT,
               ctypes.POINTER(_GattCharacteristic), ctypes.POINTER(w.USHORT), w.ULONG),
            _f(dll, "BluetoothGATTGetCharacteristicValue", ctypes.c_long, HANDLE,
               ctypes.POINTER(_GattCharacteristic), w.ULONG,
               ctypes.POINTER(_GattValue), ctypes.POINTER(w.USHORT), w.ULONG),
        )
    return _bluetooth_apis or None


def _gatt_uuid16(u: _BthLeUuid) -> int | None:
    """把 16 位或 Bluetooth base 128 位 UUID 归一成 16 位短码。"""
    if u.IsShortUuid:
        return int(u.Value.ShortUuid)
    g = u.Value.LongUuid
    if (int(g.Data2) == 0 and int(g.Data3) == 0x1000
            and bytes(g.Data4) == b"\x80\x00\x00\x80\x5f\x9b\x34\xfb"):
        return int(g.Data1) & 0xFFFF
    return None


@dataclass
class BleDevice:
    path: str
    mac: str | None
    container_id: str | None
    name: str
    battery: int | None = None


def _gatt_services(handle, get_services) -> list[_GattService]:
    count = w.USHORT(0)
    r = get_services(handle, 0, None, ctypes.byref(count), 0) & 0xFFFFFFFF
    if r not in (0, _HRESULT_MORE_DATA) or not count.value:
        return []
    services = (_GattService * count.value)()
    got = w.USHORT(count.value)
    if (get_services(handle, count.value, services, ctypes.byref(got), 0)
            & 0xFFFFFFFF) != 0:
        return []
    return [services[i] for i in range(min(got.value, count.value))]


def gatt_service_uuids(path: str) -> list[int]:
    """列出 BLE 设备提供的 GATT 服务短 UUID（诊断用）。"""
    api = _gatt_api()
    if not api:
        return []
    handle = CreateFileW(path, GENERIC_READ | GENERIC_WRITE,
                         FILE_SHARE_READ | FILE_SHARE_WRITE, None, OPEN_EXISTING, 0, None)
    if not handle or handle == INVALID_HANDLE_VALUE:
        return []
    try:
        out = []
        for svc in _gatt_services(handle, api[0]):
            code = _gatt_uuid16(svc.ServiceUuid)
            if code is not None:
                out.append(code)
        return out
    finally:
        k.kernel32.CloseHandle(handle)


def read_gatt_battery(path: str) -> int | None:
    """读 BLE Battery Level 特征；设备断开或不支持时返回 None。

    刻意不加 FORCE_READ_FROM_CACHE：断开时 Windows 仍会给出服务列表，
    但实时读取会失败，正好避免「没连却显示旧电量」的幽灵读数。
    """
    api = _gatt_api()
    if not api:
        return None
    get_services, get_chars, get_value = api
    handle = CreateFileW(path, GENERIC_READ | GENERIC_WRITE,
                         FILE_SHARE_READ | FILE_SHARE_WRITE, None, OPEN_EXISTING, 0, None)
    if not handle or handle == INVALID_HANDLE_VALUE:
        return None
    try:
        for svc in _gatt_services(handle, get_services):
            if _gatt_uuid16(svc.ServiceUuid) != BLE_BATTERY_SERVICE:
                continue
            ccount = w.USHORT(0)
            r = get_chars(handle, ctypes.byref(svc), 0, None,
                          ctypes.byref(ccount), 0) & 0xFFFFFFFF
            if r not in (0, _HRESULT_MORE_DATA) or not ccount.value:
                return None
            chars = (_GattCharacteristic * ccount.value)()
            cgot = w.USHORT(ccount.value)
            if (get_chars(handle, ctypes.byref(svc), ccount.value, chars,
                          ctypes.byref(cgot), 0) & 0xFFFFFFFF) != 0:
                return None
            for j in range(min(cgot.value, ccount.value)):
                ch = chars[j]
                if (_gatt_uuid16(ch.CharacteristicUuid) != BLE_BATTERY_LEVEL
                        or not ch.IsReadable):
                    continue
                value = _GattValue()
                value.DataSize = ctypes.sizeof(value.Data)
                actual = w.USHORT(0)
                r = get_value(handle, ctypes.byref(ch), ctypes.sizeof(value),
                              ctypes.byref(value), ctypes.byref(actual), 0) & 0xFFFFFFFF
                if r != 0 or value.DataSize < 1:
                    return None
                level = int(value.Data[0])
                return level if 0 <= level <= 100 else None
        return None
    finally:
        k.kernel32.CloseHandle(handle)


def scan_ble_devices(read_battery: bool = True) -> list[BleDevice]:
    """枚举 BLE 设备接口，附带真实产品名、容器 ID、MAC 与 GATT 电量。"""
    out: list[BleDevice] = []
    g = guid(GUID_BLE_DEVICE_INTERFACE)
    hdev = SetupDiGetClassDevsW(ctypes.byref(g), None, None,
                                DIGCF_PRESENT | DIGCF_DEVICEINTERFACE)
    if not hdev or hdev == INVALID_HANDLE_VALUE:
        return out
    try:
        idx = 0
        did = SP_DEVINFO_DATA()
        did.cbSize = ctypes.sizeof(SP_DEVINFO_DATA)
        while SetupDiEnumDeviceInfo(hdev, idx, ctypes.byref(did)):
            idx += 1
            inst = ctypes.create_unicode_buffer(512)
            SetupDiGetDeviceInstanceIdW(hdev, ctypes.byref(did), inst, 512, None)
            iid = inst.value.upper()
            mac = None
            if "DEV_" in iid:
                tail = iid.split("DEV_", 1)[1][:12]
                if len(tail) == 12 and all(c in "0123456789ABCDEF" for c in tail):
                    mac = tail
            cid = _read_prop(hdev, did, KEY_CONTAINER_ID)[0]
            name = (str(_read_prop(hdev, did, KEY_FRIENDLY_NAME)[0] or "")
                    or _read_reg_prop(hdev, did, SPDRP_FRIENDLYNAME) or ""
                    or _read_reg_prop(hdev, did, SPDRP_DEVICEDESC) or "")
            iface = SP_DEVICE_INTERFACE_DATA()
            iface.cbSize = ctypes.sizeof(SP_DEVICE_INTERFACE_DATA)
            i = 0
            while SetupDiEnumDeviceInterfaces(hdev, ctypes.byref(did),
                                              ctypes.byref(g), i, ctypes.byref(iface)):
                i += 1
                needed = w.DWORD(0)
                SetupDiGetDeviceInterfaceDetailW(hdev, ctypes.byref(iface), None, 0,
                                                 ctypes.byref(needed), None)
                if needed.value <= 0:
                    continue
                buf = ctypes.create_string_buffer(needed.value)
                ctypes.cast(buf, ctypes.POINTER(w.DWORD))[0] = (
                    8 if ctypes.sizeof(ctypes.c_void_p) == 8 else 6)
                if SetupDiGetDeviceInterfaceDetailW(hdev, ctypes.byref(iface), buf,
                                                    needed.value, None, None):
                    path = ctypes.wstring_at(ctypes.addressof(buf) + ctypes.sizeof(w.DWORD))
                    if path:
                        out.append(BleDevice(
                            path=path, mac=mac,
                            container_id=str(cid) if cid else None,
                            name=str(name).strip(),
                            battery=read_gatt_battery(path) if read_battery else None,
                        ))
    finally:
        SetupDiDestroyDeviceInfoList(hdev)
    return out
