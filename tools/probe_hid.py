"""探测指定 VID 的 HID 接口与报告描述符，用于判断电量上报通道。

用法: python tools/probe_hid.py [VID_HEX]    默认 12d1 (Huawei)
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import devapi  # noqa: E402

USAGE_PAGES = {0x01: "Generic Desktop", 0x02: "Simulation", 0x06: "Generic Device Controls",
               0x07: "Keyboard", 0x08: "LED", 0x09: "Button", 0x0C: "Consumer",
               0x0D: "Digitizer", 0x0F: "PID", 0x84: "Power Device", 0x85: "Battery System",
               0xFF00: "Vendor 0xFF00", 0xFF01: "Vendor 0xFF01", 0xFF02: "Vendor 0xFF02",
               0xFFA0: "Vendor 0xFFA0"}


def parse_usages(data: bytes) -> list[tuple[str, str]]:
    """极简描述符解析：收集 Usage Page / Usage 组合与 Report ID。"""
    found: list[tuple[str, str]] = []
    usage_page = 0
    pending: list[int] = []
    i = 0
    while i < len(data):
        b = data[i]
        size = (0, 1, 2, 4)[b & 0x03] if (b & 0x03) != 3 else 4
        tag = b & 0xFC
        val = int.from_bytes(data[i + 1: i + 1 + size], "little") if size else 0
        if tag == 0x04:      # Usage Page
            usage_page = val
        elif tag == 0x08:    # Usage
            pending.append(val)
        elif tag == 0x0C:    # Usage Min
            found.append((f"page 0x{usage_page:04X} {USAGE_PAGES.get(usage_page, '')}",
                          f"usage 0x{val:04X}-"))
        elif tag == 0x84:    # Report ID
            for u in pending:
                found.append((f"page 0x{usage_page:04X} {USAGE_PAGES.get(usage_page, '')}",
                              f"usage 0x{u:04X} (report {val})"))
            pending.clear()
        i += 1 + size
    for u in pending:
        found.append((f"page 0x{usage_page:04X} {USAGE_PAGES.get(usage_page, '')}",
                      f"usage 0x{u:04X}"))
    return found


def main() -> None:
    vid = int(sys.argv[1], 16) if len(sys.argv) > 1 else 0x12D1
    items = [i for i in devapi.scan_hid_interfaces() if i.vendor_id == vid]
    print(f"VID 0x{vid:04X}: {len(items)} HID interface(s)\n")
    for itf in items:
        print("=" * 78)
        print(f"path      {itf.path}")
        print(f"vid:pid   {itf.vid_pid}   ver 0x{itf.version:04X}")
        print(f"product   {itf.product!r}   mfr {itf.manufacturer!r}")
        print(f"usage     page 0x{itf.usage_page:04X} {USAGE_PAGES.get(itf.usage_page, '')} / usage 0x{itf.usage:04X}")
        print(f"reports   in={itf.in_len} out={itf.out_len} feature={itf.feature_len}")
        print(f"node      {itf.instance_id}  class={itf.class_name}")
        print(f"container {itf.container_id}")
        desc = devapi.report_descriptor(itf.path)
        print(f"descriptor {len(desc)} bytes")
        if desc:
            print("  " + desc.hex(" "))
            for page, usage in parse_usages(desc):
                print(f"    - {page}  {usage}")
        if itf.feature_len > 1:
            dev = devapi.HidDevice(itf.path)
            try:
                for rid in range(0, 8):
                    buf = dev.get_feature(rid, max(itf.feature_len, 2))
                    if buf:
                        print(f"  feature[{rid}] -> {buf.hex(' ')}")
            finally:
                dev.close()
        print()


if __name__ == "__main__":
    main()
