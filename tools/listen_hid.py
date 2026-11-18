"""被动监听厂商自定义 HID 集合的输入报告（不发送任何数据）。

用法: python tools/listen_hid.py [秒数] [VID_HEX]
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import devapi  # noqa: E402


def main() -> None:
    secs = float(sys.argv[1]) if len(sys.argv) > 1 else 6.0
    vid = int(sys.argv[2], 16) if len(sys.argv) > 2 else 0x12D1
    items = [i for i in devapi.scan_hid_interfaces()
             if i.vendor_id == vid and i.usage_page >= 0xFF00 and i.in_len > 1]
    print(f"listening on {len(items)} vendor collection(s) for {secs:.0f}s ...")
    handles = []
    for itf in items:
        dev = devapi.HidDevice(itf.path)
        if dev.valid:
            print(f"  open page 0x{itf.usage_page:04X} in={itf.in_len} {itf.path[-30:]}")
            handles.append((itf, dev))
        else:
            dev.close()
    end = time.time() + secs
    seen: dict[int, int] = {}
    while time.time() < end:
        for itf, dev in handles:
            data = dev.read(max(itf.in_len, 2), timeout_ms=120)
            if data:
                key = (itf.usage_page, data.hex())
                seen[key] = seen.get(key, 0) + 1
                if seen[key] <= 6:
                    print(f"[{time.strftime('%H:%M:%S')}] page 0x{itf.usage_page:04X} "
                          f"len={len(data)} {data.hex(' ')}")
    for _, dev in handles:
        dev.close()
    print("--- unique frames:", len(seen))
    for (page, hx), n in sorted(seen.items(), key=lambda kv: -kv[1])[:30]:
        print(f"  page 0x{page:04X} x{n:<3} {hx}")


if __name__ == "__main__":
    main()
