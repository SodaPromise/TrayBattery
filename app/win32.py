"""Win32 API 封装（纯 ctypes，无第三方依赖）。

只包含本项目用到的部分：窗口、分层绘制、托盘图标、菜单、DPI。
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes as w

user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
shell32 = ctypes.WinDLL("shell32", use_last_error=True)

LRESULT = ctypes.c_ssize_t
WPARAM = ctypes.c_size_t
LPARAM = ctypes.c_ssize_t
HCURSOR = ctypes.c_void_p
HICON = ctypes.c_void_p
HBRUSH = ctypes.c_void_p
HMONITOR = ctypes.c_void_p
HANDLE = ctypes.c_void_p
HGDIOBJ = ctypes.c_void_p
HBITMAP = ctypes.c_void_p
HDC = ctypes.c_void_p
HWND = ctypes.c_void_p
HINSTANCE = ctypes.c_void_p
HMENU = ctypes.c_void_p
ATOM = ctypes.c_ushort

WNDPROC = ctypes.WINFUNCTYPE(LRESULT, HWND, w.UINT, WPARAM, LPARAM)

# ---------------------------------------------------------------- 常量
WM_NULL = 0x0000
WM_DESTROY = 0x0002
WM_CLOSE = 0x0010
WM_QUIT = 0x0012
WM_ACTIVATE = 0x0006
WM_SETFOCUS = 0x0007
WM_KILLFOCUS = 0x0008
WM_PAINT = 0x000F
WM_ERASEBKGND = 0x0014
WM_SETCURSOR = 0x0020
WM_GETMINMAXINFO = 0x0024
WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_LBUTTONDBLCLK = 0x0203
WM_RBUTTONUP = 0x0205
WM_MOUSEWHEEL = 0x020A
WM_MOUSELEAVE = 0x02A3
WM_KEYDOWN = 0x0100
WM_TIMER = 0x0113
WM_CONTEXTMENU = 0x007B
WM_DEVICECHANGE = 0x0219
WM_DISPLAYCHANGE = 0x007E
WM_DPICHANGED = 0x02E0
WM_APP = 0x8000

NIN_SELECT = 0x0400
NIN_KEYSELECT = 0x0401
NIN_BALLOONUSERCLICK = 0x0405

WA_INACTIVE = 0
SW_HIDE = 0
SW_SHOW = 5
SW_SHOWNOACTIVATE = 4

HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
HWND_TOP = 0
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040
SWP_HIDEWINDOW = 0x0080

GWL_EXSTYLE = -20
GWLP_USERDATA = -21
WS_POPUP = 0x80000000
WS_CHILD = 0x40000000
WS_VISIBLE = 0x10000000
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_TOPMOST = 0x00000008
WS_EX_LAYERED = 0x00080000
WS_EX_NOACTIVATE = 0x08000000
WS_EX_APPWINDOW = 0x00040000

ULW_ALPHA = 0x00000002
AC_SRC_OVER = 0x00
AC_SRC_ALPHA = 0x01
BI_RGB = 0

SM_CXSMICON = 49
SM_CYSMICON = 50
SM_CXSCREEN = 0
SM_CYSCREEN = 1

IDC_ARROW = 32512
IDC_HAND = 32649
IDC_SIZENS = 32645

SPI_GETWORKAREA = 0x0030
SPI_SETWORKAREA = 0x002F
MONITOR_DEFAULTTONEAREST = 2

MF_STRING = 0x00000000
MF_SEPARATOR = 0x00000800
MF_CHECKED = 0x00000008
MF_UNCHECKED = 0x00000000
MF_GRAYED = 0x00000001
MF_DISABLED = 0x00000002
MF_DEFAULT = 0x00001000
TPM_LEFTALIGN = 0x0000
TPM_CENTERALIGN = 0x0004
TPM_RIGHTALIGN = 0x0008
TPM_RIGHTBUTTON = 0x0002
TPM_RETURNCMD = 0x0100
TPM_NONOTIFY = 0x0080
TPM_TOPALIGN = 0x0000
TPM_BOTTOMALIGN = 0x0020

NIM_ADD = 0x00000000
NIM_MODIFY = 0x00000001
NIM_DELETE = 0x00000002
NIM_SETVERSION = 0x00000004
NIF_MESSAGE = 0x00000001
NIF_ICON = 0x00000002
NIF_TIP = 0x00000004
NIF_STATE = 0x00000008
NIF_INFO = 0x00000010
NIF_SHOWTIP = 0x00000080
NIS_HIDDEN = 0x00000001
NOTIFYICON_VERSION_4 = 4
NIIF_INFO = 0x00000001
NIIF_USER = 0x00000004
NIIF_NOSOUND = 0x00000010

DBT_DEVNODES_CHANGED = 0x0007

TME_LEAVE = 0x00000002
HOVER_DEFAULT = 0xFFFFFFFF

MAPVK_VK_TO_CHAR = 2


# ---------------------------------------------------------------- 结构体
class POINT(ctypes.Structure):
    _fields_ = [("x", w.LONG), ("y", w.LONG)]


class SIZE(ctypes.Structure):
    _fields_ = [("cx", w.LONG), ("cy", w.LONG)]


class RECT(ctypes.Structure):
    _fields_ = [("left", w.LONG), ("top", w.LONG), ("right", w.LONG), ("bottom", w.LONG)]


class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize", w.UINT),
        ("style", w.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", HINSTANCE),
        ("hIcon", HICON),
        ("hCursor", HCURSOR),
        ("hbrBackground", HBRUSH),
        ("lpszMenuName", w.LPCWSTR),
        ("lpszClassName", w.LPCWSTR),
        ("hIconSm", HICON),
    ]


class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", HWND),
        ("message", w.UINT),
        ("wParam", WPARAM),
        ("lParam", LPARAM),
        ("time", w.DWORD),
        ("pt", POINT),
    ]


class BLENDFUNCTION(ctypes.Structure):
    _fields_ = [
        ("BlendOp", w.BYTE),
        ("BlendFlags", w.BYTE),
        ("SourceConstantAlpha", w.BYTE),
        ("AlphaFormat", w.BYTE),
    ]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", w.DWORD),
        ("biWidth", w.LONG),
        ("biHeight", w.LONG),
        ("biPlanes", w.WORD),
        ("biBitCount", w.WORD),
        ("biCompression", w.DWORD),
        ("biSizeImage", w.DWORD),
        ("biXPelsPerMeter", w.LONG),
        ("biYPelsPerMeter", w.LONG),
        ("biClrUsed", w.DWORD),
        ("biClrImportant", w.DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", w.DWORD * 3)]


class ICONINFO(ctypes.Structure):
    _fields_ = [
        ("fIcon", w.BOOL),
        ("xHotspot", w.DWORD),
        ("yHotspot", w.DWORD),
        ("hbmMask", HBITMAP),
        ("hbmColor", HBITMAP),
    ]


class TRACKMOUSEEVENT(ctypes.Structure):
    _fields_ = [
        ("cbSize", w.DWORD),
        ("dwFlags", w.DWORD),
        ("hwndTrack", HWND),
        ("dwHoverTime", w.DWORD),
    ]


class MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", w.DWORD),
        ("rcMonitor", RECT),
        ("rcWork", RECT),
        ("dwFlags", w.DWORD),
    ]


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ("cbSize", w.DWORD),
        ("hWnd", HWND),
        ("uID", w.UINT),
        ("uFlags", w.UINT),
        ("uCallbackMessage", w.UINT),
        ("hIcon", HICON),
        ("szTip", w.WCHAR * 128),
        ("dwState", w.DWORD),
        ("dwStateMask", w.DWORD),
        ("szInfo", w.WCHAR * 256),
        ("uVersion", w.UINT),
        ("szInfoTitle", w.WCHAR * 64),
        ("dwInfoFlags", w.DWORD),
        ("guidItem", ctypes.c_byte * 16),
        ("hBalloonIcon", HICON),
    ]


# ---------------------------------------------------------------- 原型
def _f(dll, name, restype, *argtypes):
    fn = getattr(dll, name)
    fn.restype = restype
    fn.argtypes = argtypes
    return fn


RegisterClassExW = _f(user32, "RegisterClassExW", w.ATOM, ctypes.POINTER(WNDCLASSEXW))
UnregisterClassW = _f(user32, "UnregisterClassW", w.BOOL, w.LPCWSTR, HINSTANCE)
CreateWindowExW = _f(
    user32, "CreateWindowExW", HWND,
    w.DWORD, w.LPCWSTR, w.LPCWSTR, w.DWORD,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    HWND, HMENU, HINSTANCE, ctypes.c_void_p,
)
DestroyWindow = _f(user32, "DestroyWindow", w.BOOL, HWND)
DefWindowProcW = _f(user32, "DefWindowProcW", LRESULT, HWND, w.UINT, WPARAM, LPARAM)
GetMessageW = _f(user32, "GetMessageW", w.BOOL, ctypes.POINTER(MSG), HWND, w.UINT, w.UINT)
PeekMessageW = _f(user32, "PeekMessageW", w.BOOL, ctypes.POINTER(MSG), HWND, w.UINT, w.UINT, w.UINT)
TranslateMessage = _f(user32, "TranslateMessage", w.BOOL, ctypes.POINTER(MSG))
DispatchMessageW = _f(user32, "DispatchMessageW", LRESULT, ctypes.POINTER(MSG))
PostMessageW = _f(user32, "PostMessageW", w.BOOL, HWND, w.UINT, WPARAM, LPARAM)
SendMessageW = _f(user32, "SendMessageW", LRESULT, HWND, w.UINT, WPARAM, LPARAM)
PostQuitMessage = _f(user32, "PostQuitMessage", None, ctypes.c_int)
ShowWindow = _f(user32, "ShowWindow", w.BOOL, HWND, ctypes.c_int)
IsWindowVisible = _f(user32, "IsWindowVisible", w.BOOL, HWND)
SetWindowPos = _f(user32, "SetWindowPos", w.BOOL, HWND, HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, w.UINT)
SetForegroundWindow = _f(user32, "SetForegroundWindow", w.BOOL, HWND)
GetForegroundWindow = _f(user32, "GetForegroundWindow", HWND)
GetAsyncKeyState = _f(user32, "GetAsyncKeyState", ctypes.c_short, ctypes.c_int)
GetCursorPos = _f(user32, "GetCursorPos", w.BOOL, ctypes.POINTER(POINT))
ScreenToClient = _f(user32, "ScreenToClient", w.BOOL, HWND, ctypes.POINTER(POINT))
ClientToScreen = _f(user32, "ClientToScreen", w.BOOL, HWND, ctypes.POINTER(POINT))
GetWindowRect = _f(user32, "GetWindowRect", w.BOOL, HWND, ctypes.POINTER(RECT))
GetClientRect = _f(user32, "GetClientRect", w.BOOL, HWND, ctypes.POINTER(RECT))
SetCapture = _f(user32, "SetCapture", HWND, HWND)
ReleaseCapture = _f(user32, "ReleaseCapture", w.BOOL)
GetDC = _f(user32, "GetDC", HDC, HWND)
ReleaseDC = _f(user32, "ReleaseDC", ctypes.c_int, HWND, HDC)
UpdateLayeredWindow = _f(
    user32, "UpdateLayeredWindow", w.BOOL,
    HWND, HDC, ctypes.POINTER(POINT), ctypes.POINTER(SIZE),
    HDC, ctypes.POINTER(POINT), w.COLORREF, ctypes.POINTER(BLENDFUNCTION), w.DWORD,
)
SetWindowLongPtrW = _f(user32, "SetWindowLongPtrW", ctypes.c_ssize_t, HWND, ctypes.c_int, ctypes.c_ssize_t)
GetWindowLongPtrW = _f(user32, "GetWindowLongPtrW", ctypes.c_ssize_t, HWND, ctypes.c_int)
SetTimer = _f(user32, "SetTimer", ctypes.c_size_t, HWND, ctypes.c_size_t, w.UINT, ctypes.c_void_p)
KillTimer = _f(user32, "KillTimer", w.BOOL, HWND, ctypes.c_size_t)
InvalidateRect = _f(user32, "InvalidateRect", w.BOOL, HWND, ctypes.POINTER(RECT), w.BOOL)
TrackMouseEvent = _f(user32, "TrackMouseEvent", w.BOOL, ctypes.POINTER(TRACKMOUSEEVENT))
LoadCursorW = _f(user32, "LoadCursorW", HCURSOR, HINSTANCE, ctypes.c_void_p)
SetCursor = _f(user32, "SetCursor", HCURSOR, HCURSOR)
GetSystemMetrics = _f(user32, "GetSystemMetrics", ctypes.c_int, ctypes.c_int)
GetSystemMetricsForDpi = _f(user32, "GetSystemMetricsForDpi", ctypes.c_int, ctypes.c_int, w.UINT)
GetDpiForWindow = _f(user32, "GetDpiForWindow", w.UINT, HWND)
GetDpiForSystem = _f(user32, "GetDpiForSystem", w.UINT)
SetProcessDpiAwarenessContext = _f(user32, "SetProcessDpiAwarenessContext", w.BOOL, ctypes.c_void_p)
SystemParametersInfoW = _f(user32, "SystemParametersInfoW", w.BOOL, w.UINT, w.UINT, ctypes.c_void_p, w.UINT)
MonitorFromPoint = _f(user32, "MonitorFromPoint", HMONITOR, POINT, w.DWORD)
GetMonitorInfoW = _f(user32, "GetMonitorInfoW", w.BOOL, HMONITOR, ctypes.POINTER(MONITORINFO))
FindWindowW = _f(user32, "FindWindowW", HWND, w.LPCWSTR, w.LPCWSTR)
FindWindowExW = _f(user32, "FindWindowExW", HWND, HWND, w.LPCWSTR, w.LPCWSTR)
RegisterWindowMessageW = _f(user32, "RegisterWindowMessageW", w.UINT, w.LPCWSTR)
CreatePopupMenu = _f(user32, "CreatePopupMenu", HMENU)
AppendMenuW = _f(user32, "AppendMenuW", w.BOOL, HMENU, w.UINT, ctypes.c_size_t, w.LPCWSTR)
SetMenuDefaultItem = _f(user32, "SetMenuDefaultItem", w.BOOL, HMENU, w.UINT, w.UINT)
DestroyMenu = _f(user32, "DestroyMenu", w.BOOL, HMENU)
TrackPopupMenu = _f(
    user32, "TrackPopupMenu", ctypes.c_int,
    HMENU, w.UINT, ctypes.c_int, ctypes.c_int, ctypes.c_int, HWND, ctypes.POINTER(RECT),
)
SetWindowTextW = _f(user32, "SetWindowTextW", w.BOOL, HWND, w.LPCWSTR)
MessageBoxW = _f(user32, "MessageBoxW", ctypes.c_int, HWND, w.LPCWSTR, w.LPCWSTR, w.UINT)
MapVirtualKeyW = _f(user32, "MapVirtualKeyW", w.UINT, w.UINT, w.UINT)
GetKeyState = _f(user32, "GetKeyState", ctypes.c_short, ctypes.c_int)
user32.CreateIconIndirect = _f(user32, "CreateIconIndirect", HICON, ctypes.POINTER(ICONINFO))

gdi32.CreateCompatibleDC = _f(gdi32, "CreateCompatibleDC", HDC, HDC)
gdi32.DeleteDC = _f(gdi32, "DeleteDC", w.BOOL, HDC)
gdi32.SelectObject = _f(gdi32, "SelectObject", HGDIOBJ, HDC, HGDIOBJ)
gdi32.DeleteObject = _f(gdi32, "DeleteObject", w.BOOL, HGDIOBJ)
gdi32.CreateDIBSection = _f(
    gdi32, "CreateDIBSection", HBITMAP,
    HDC, ctypes.POINTER(BITMAPINFO), w.UINT, ctypes.POINTER(ctypes.c_void_p), HANDLE, w.DWORD,
)
gdi32.CreateBitmap = _f(gdi32, "CreateBitmap", HBITMAP, ctypes.c_int, ctypes.c_int, w.UINT, w.UINT, ctypes.c_void_p)
gdi32.CreateSolidBrush = _f(gdi32, "CreateSolidBrush", HBRUSH, w.DWORD)

kernel32.GetModuleHandleW = _f(kernel32, "GetModuleHandleW", HINSTANCE, w.LPCWSTR)
kernel32.CreateMutexW = _f(kernel32, "CreateMutexW", HANDLE, ctypes.c_void_p, w.BOOL, w.LPCWSTR)
kernel32.GetLastError = _f(kernel32, "GetLastError", w.DWORD)
kernel32.SetLastError = _f(kernel32, "SetLastError", None, w.DWORD)
kernel32.CloseHandle = _f(kernel32, "CloseHandle", w.BOOL, HANDLE)

shell32.Shell_NotifyIconW = _f(shell32, "Shell_NotifyIconW", w.BOOL, w.DWORD, ctypes.POINTER(NOTIFYICONDATAW))
shell32.ShellExecuteW = _f(
    shell32, "ShellExecuteW", HINSTANCE, HWND, w.LPCWSTR, w.LPCWSTR, w.LPCWSTR, w.LPCWSTR, ctypes.c_int
)
shell32.ExtractIconExW = _f(shell32, "ExtractIconExW", w.UINT, w.LPCWSTR, ctypes.POINTER(HICON), ctypes.POINTER(HICON), w.UINT)


# ---------------------------------------------------------------- 工具
def enable_dpi_awareness() -> None:
    """Per-Monitor V2，失败时退回系统 DPI 感知。"""
    try:
        if SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
            return
    except Exception:
        pass
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            user32.SetProcessDPIAware()
        except Exception:
            pass


def system_dpi() -> int:
    try:
        return int(GetDpiForSystem())
    except Exception:
        return 96


def scale_for_dpi(dpi: int) -> float:
    return max(0.75, min(3.0, dpi / 96.0))


def cursor_pos() -> tuple[int, int]:
    p = POINT()
    GetCursorPos(ctypes.byref(p))
    return p.x, p.y


def work_area() -> RECT:
    r = RECT()
    SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(r), 0)
    return r


def monitor_work_area(x: int, y: int) -> RECT:
    mi = MONITORINFO()
    mi.cbSize = ctypes.sizeof(MONITORINFO)
    hm = MonitorFromPoint(POINT(x, y), MONITOR_DEFAULTTONEAREST)
    if hm and GetMonitorInfoW(hm, ctypes.byref(mi)):
        return mi.rcWork
    return work_area()


def register_window_message(name: str) -> int:
    """注册可接收系统广播的窗口消息（如 TaskbarCreated）。"""
    return int(RegisterWindowMessageW(name))


def _load_cursor(name_id: int) -> HCURSOR:
    return LoadCursorW(None, ctypes.c_void_p(name_id))


# ---------------------------------------------------------------- 图标 & 分层绘制
def hicon_from_image(image) -> HICON | None:
    """32bpp DIB + 掩码生成 HICON（比 PNG 资源兼容性更好）。"""
    from PIL import Image, ImageChops

    img = image.convert("RGBA")
    w_, h_ = img.size
    r, g, b, a = img.split()
    r = ImageChops.multiply(r, a)
    g = ImageChops.multiply(g, a)
    b = ImageChops.multiply(b, a)
    # DIB 需要 BGRA 顺序的自上而下像素
    pixels = Image.merge("RGBA", (b, g, r, a)).tobytes("raw", "BGRA")

    bmi = BITMAPINFO()
    bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.bmiHeader.biWidth = w_
    bmi.bmiHeader.biHeight = -h_
    bmi.bmiHeader.biPlanes = 1
    bmi.bmiHeader.biBitCount = 32
    bmi.bmiHeader.biCompression = BI_RGB

    hdc_screen = GetDC(None)
    hdc = gdi32.CreateCompatibleDC(hdc_screen)
    bits = ctypes.c_void_p()
    hbmp = gdi32.CreateDIBSection(hdc, ctypes.byref(bmi), 0, ctypes.byref(bits), None, 0)
    if not hbmp:
        gdi32.DeleteDC(hdc)
        ReleaseDC(None, hdc_screen)
        return None
    ctypes.memmove(bits, pixels, len(pixels))
    mask = gdi32.CreateBitmap(w_, h_, 1, 1, None)
    info = ICONINFO(1, 0, 0, mask, hbmp)
    hicon = user32.CreateIconIndirect(ctypes.byref(info))
    gdi32.DeleteObject(mask)
    gdi32.DeleteObject(hbmp)
    gdi32.DeleteDC(hdc)
    ReleaseDC(None, hdc_screen)
    return hicon


def destroy_icon(hicon: HICON | None) -> None:
    if hicon:
        user32.DestroyIcon(ctypes.c_void_p(hicon))


class LayeredCanvas:
    """管理一个分层窗口所需的 DIB 与 HDC，复用减少分配。"""

    def __init__(self) -> None:
        self.hdc_screen = GetDC(None)
        self.hdc_mem = gdi32.CreateCompatibleDC(self.hdc_screen)
        self.hbmp: HBITMAP | None = None
        self.old_obj: HGDIOBJ | None = None
        self.bits: ctypes.c_void_p | None = None
        self.size = (0, 0)

    def ensure(self, w_: int, h_: int) -> None:
        if self.size == (w_, h_) and self.hbmp:
            return
        self._release_bitmap()
        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = w_
        bmi.bmiHeader.biHeight = -h_  # top-down
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = BI_RGB
        bits = ctypes.c_void_p()
        self.hbmp = gdi32.CreateDIBSection(
            self.hdc_mem, ctypes.byref(bmi), 0, ctypes.byref(bits), None, 0
        )
        self.bits = bits
        self.old_obj = gdi32.SelectObject(self.hdc_mem, self.hbmp)
        self.size = (w_, h_)

    def _release_bitmap(self) -> None:
        if self.hbmp:
            if self.old_obj:
                gdi32.SelectObject(self.hdc_mem, self.old_obj)
            gdi32.DeleteObject(self.hbmp)
            self.hbmp = None
            self.old_obj = None
            self.bits = None
            self.size = (0, 0)

    def upload(self, image) -> None:
        """image: PIL RGBA，尺寸需与 ensure 的一致。"""
        w_, h_ = image.size
        self.ensure(w_, h_)
        raw = image.convert("RGBA").tobytes("raw", "BGRA")
        ctypes.memmove(self.bits, raw, len(raw))

    def present(self, hwnd: HWND, x: int | None = None, y: int | None = None, alpha: int = 255) -> bool:
        w_, h_ = self.size
        if not w_ or not h_:
            return False
        pt_dst = POINT(x, y) if x is not None and y is not None else None
        size = SIZE(w_, h_)
        src = POINT(0, 0)
        blend = BLENDFUNCTION(AC_SRC_OVER, 0, alpha, AC_SRC_ALPHA)
        return bool(
            UpdateLayeredWindow(
                hwnd,
                self.hdc_screen,
                ctypes.byref(pt_dst) if pt_dst else None,
                ctypes.byref(size),
                self.hdc_mem,
                ctypes.byref(src),
                0,
                ctypes.byref(blend),
                ULW_ALPHA,
            )
        )

    def close(self) -> None:
        self._release_bitmap()
        if self.hdc_mem:
            gdi32.DeleteDC(self.hdc_mem)
            self.hdc_mem = None
        if self.hdc_screen:
            ReleaseDC(None, self.hdc_screen)
            self.hdc_screen = None


# ---------------------------------------------------------------- 窗口类注册
_window_instances: dict[int, object] = {}
_wndproc_ref = None
_registered: set[str] = set()


def _global_wndproc(hwnd, msg, wparam, lparam):
    try:
        inst = _window_instances.get(int(hwnd or 0))
        if inst is not None:
            return inst.on_message(msg, wparam, lparam)
    except Exception:
        try:
            from .log import log_exc
            log_exc("WndProc error")
        except Exception:
            pass
    return DefWindowProcW(hwnd, msg, wparam, lparam)


def register_window_class(name: str) -> None:
    global _wndproc_ref
    if name in _registered:
        return
    if _wndproc_ref is None:
        _wndproc_ref = WNDPROC(_global_wndproc)
    hinst = kernel32.GetModuleHandleW(None)
    wc = WNDCLASSEXW()
    wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
    wc.style = 0
    wc.lpfnWndProc = _wndproc_ref
    wc.cbClsExtra = 0
    wc.cbWndExtra = 0
    wc.hInstance = hinst
    wc.hIcon = None
    wc.hCursor = _load_cursor(IDC_ARROW)
    wc.hbrBackground = None
    wc.lpszMenuName = None
    wc.lpszClassName = name
    wc.hIconSm = None
    atom = RegisterClassExW(ctypes.byref(wc))
    if not atom:
        err = ctypes.get_last_error()
        if err not in (1410,):  # class already exists
            raise OSError(f"RegisterClassExW failed: {err}")
    _registered.add(name)


def create_window(name: str, w_: int, h_: int, ex_style: int, style: int = WS_POPUP,
                  parent: HWND | None = None, x: int = -20000, y: int = -20000) -> HWND:
    register_window_class(name)
    hwnd = CreateWindowExW(
        ex_style, name, "TrayBattery", style, x, y, w_, h_, parent, None,
        kernel32.GetModuleHandleW(None), None,
    )
    if not hwnd:
        raise OSError(f"CreateWindowExW failed: {ctypes.get_last_error()}")
    return hwnd


def bind_window(hwnd: HWND, inst: object) -> None:
    _window_instances[int(hwnd)] = inst


def unbind_window(hwnd: HWND | None) -> None:
    if hwnd:
        _window_instances.pop(int(hwnd), None)


def run_message_loop() -> None:
    msg = MSG()
    while True:
        ret = GetMessageW(ctypes.byref(msg), None, 0, 0)
        if ret == -1:
            break
        if ret == 0:
            break
        TranslateMessage(ctypes.byref(msg))
        DispatchMessageW(ctypes.byref(msg))
