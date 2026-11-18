"""向厂商 HID 集合发送一帧并读取应答，用于验证华为/星闪接收器协议。

用法:
  python tools/probe_cmd.py list
  python tools/probe_cmd.py send FFB3 "05 20 00 1a 06" [--repeat 3]
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import devapi  # noqa: E402


def open_by_page(page: int):
    for itf in devapi.scan_hid_interfaces():
        if itf.vendor_id == 0x12D1 and itf.usage_page == page and itf.out_len > 1:
            dev = devapi.HidDevice(itf.path)
            if dev.valid:
                return itf, dev
            dev.close()
    return None, None


def drain(dev, out_len: int, seconds: float) -> list[bytes]:
    frames: list[bytes] = []
    end = time.time() + seconds
    while time.time() < end:
        data = dev.read(out_len, timeout_ms=120)
        if data:
            frames.append(data)
    return frames


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] == "list":
        for itf in devapi.scan_hid_interfaces():
            if itf.vendor_id == 0x12D1 and itf.usage_page >= 0xFF00:
                print(f"0x{itf.usage_page:04X} in={itf.in_len:<3} out={itf.out_len:<3} {itf.path[-26:]}")
        return

    page = int(sys.argv[2], 16)
    payload = bytes(int(x, 16) for x in sys.argv[3].split())
    repeat = int(sys.argv[sys.argv.index("--repeat") + 1]) if "--repeat" in sys.argv else 1

    itf, dev = open_by_page(page)
    if not dev:
        print(f"page 0x{page:04X} not openable")
        return
    print(f"page 0x{page:04X} in={itf.in_len} out={itf.out_len}")
    drain(dev, itf.in_len, 0.3)          # 清空待处理帧
    frame = payload + bytes(itf.out_len - len(payload))
    for i in range(repeat):
        ok = dev.write(frame, timeout_ms=600)
        print(f"tx#{i} ok={ok} {frame[:12].hex(' ')}")
        time.sleep(0.05)
        for data in drain(dev, itf.in_len, 1.2):
            print(f"   rx {data[:24].hex(' ')}")
        time.sleep(0.2)
    dev.close()


if __name__ == "__main__":
    main()
