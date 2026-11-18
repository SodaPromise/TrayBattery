"""诊断：把本机所有 HID 接口和已知电量读取方式跑一遍。

用法：
    python tools/probe_battery.py            # 全量诊断
    python tools/probe_battery.py 373b       # 只看某个 VID（十六进制）

输出分三段：接口清单、标准 HID 电池字段、私有协议（Compx / 雷蛇 / 华为）。
只做只读查询，不修改设备设置。
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import devapi, providers  # noqa: E402


def _filter(argv: list[str]) -> int | None:
    if len(argv) < 2:
        return None
    try:
        return int(argv[1], 16)
    except ValueError:
        print(f"VID 需要十六进制，例如 373b（收到 {argv[1]}）")
        sys.exit(2)


def main() -> None:
    vid = _filter(sys.argv)
    ifaces = [i for i in devapi.scan_hid_interfaces() if vid is None or i.vendor_id == vid]
    if not ifaces:
        print("没有匹配的 HID 接口。")
        return

    print(f"== HID 接口（{len(ifaces)} 个）==")
    print(f"{'VID:PID':<12} {'UsagePage':<11} {'in':>3} {'out':>4} {'feat':>5}  {'权限':<6} 名称")
    for itf in ifaces:
        dev = devapi.HidDevice(itf.path)
        perm = "读写" if dev.writable else ("只读" if dev.valid else "打不开")
        dev.close()
        print(f"{itf.vid_pid:<12} 0x{itf.usage_page:04X}/0x{itf.usage:04X}"
              f" {itf.in_len:>3} {itf.out_len:>4} {itf.feature_len:>5}  {perm:<6} {itf.product or '-'}")

    print("\n== 标准 HID 电池字段 ==")
    hits = 0
    for itf in ifaces:
        if itf.feature_len <= 0 and itf.in_len <= 0:
            continue
        got = devapi.read_hid_battery(itf)
        if got:
            hits += 1
            print(f"  {itf.vid_pid} 0x{itf.usage_page:04X} -> {got[0]}%"
                  f"{'（充电中）' if got[1] else ''}")
    if not hits:
        print("  没有设备声明标准电池 usage（可能在私有通道里）")

    print("\n== 私有协议 ==")
    for name, table in (
        ("华为 / 荣耀", providers.scan_huawei(ttl=0, ifaces=ifaces)),
        ("Compx（ATK/VXE/VGN/达尔优等）", providers.scan_compx(ttl=0, ifaces=ifaces)),
        ("雷蛇", providers.scan_razer(ttl=0, ifaces=ifaces)),
    ):
        if table:
            for cid, (level, charging) in table.items():
                print(f"  {name}: {level}%{'（充电中）' if charging else ''}  容器 {cid[:8]}…")
        else:
            print(f"  {name}: 未命中")

    print("\n提示：标准字段没命中、私有协议也没命中时，用 tools/probe_hid.py 看厂商通道，"
          "或从官方软件的通信日志里找报文。")


if __name__ == "__main__":
    main()
