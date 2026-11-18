"""只读探测：对厂商集合尝试 GetInputReport / GetFeature（不写入任何数据）。

用法: python tools/probe_read.py [VID_HEX]
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import devapi  # noqa: E402


def main() -> None:
    vid = int(sys.argv[1], 16) if len(sys.argv) > 1 else 0x12D1
    items = [i for i in devapi.scan_hid_interfaces()
             if i.vendor_id == vid and i.usage_page >= 0xFF00]
    print(f"{len(items)} vendor interface(s)\n")
    for itf in items:
        dev = devapi.HidDevice(itf.path)
        if not dev.valid:
            print(f"page 0x{itf.usage_page:04X}: open failed")
            continue
        print(f"page 0x{itf.usage_page:04X}  in={itf.in_len} out={itf.out_len} feature={itf.feature_len}")
        size = max(itf.in_len, itf.feature_len, 16)
        for rid in range(0, 17):
            raw = dev.get_input_report(rid, size)
            if raw:
                print(f"  GetInputReport rid={rid:<2} -> {raw.hex(' ')}")
        if itf.feature_len:
            for rid in range(0, 5):
                raw = dev.get_feature(rid, max(itf.feature_len, 2))
                if raw:
                    print(f"  GetFeature rid={rid} -> {raw.hex(' ')}")
        dev.close()
        print()


if __name__ == "__main__":
    main()
