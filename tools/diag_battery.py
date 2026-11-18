"""电量通道诊断：把蓝牙鼠标相关的系统原始数据导出成文本。

在 TrayBattery 目录下运行：

    python tools/diag_battery.py

结果同时写入 tools/diag_battery_output.txt。如果蓝牙连接时仍然读不到电量，
把这个文件发回，就能看到设备到底在哪条通道上报（或没上报）电量。
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from app import devapi, providers  # noqa: E402

OUTPUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      "diag_battery_output.txt")
FOCUS = ("mouse", "gatt", "huawei", "honor", "cd26", "cd28", "cd20",
         "sound joy", "鼠标", "键盘")

_lines: list[str] = []


def out(text: str = "") -> None:
    print(text)
    _lines.append(str(text))


def focused(text: str) -> bool:
    low = (text or "").lower()
    return any(key in low for key in FOCUS)


def main() -> None:
    out("电量助手 · 设备电量通道诊断")
    out(f"Python {sys.version.split()[0]} / {sys.platform}")
    out(f"时间 {__import__('time').strftime('%Y-%m-%d %H:%M:%S')}")
    out()

    out("=== 1. BLE 设备接口（GATT Battery Service） ===")
    ble = devapi.scan_ble_devices()
    out(f"共 {len(ble)} 个 BLE 设备")
    for item in ble:
        out(f"  名称      : {item.name!r}")
        out(f"  MAC       : {item.mac}")
        out(f"  容器 ID   : {item.container_id}")
        out(f"  GATT 电量 : {item.battery}")
        services = devapi.gatt_service_uuids(item.path)
        rendered = " ".join(f"0x{u:04X}" for u in services) or "(读不到服务)"
        out(f"  GATT 服务 : {rendered}")
        out(f"  有 0x180F : {0x180F in services}")
        out(f"  接口路径  : {item.path}")
        out()

    out("=== 2. PnP 节点（含电量属性 / 相关名字） ===")
    nodes = devapi.scan_pnp_nodes()
    picked = [n for n in nodes if n.battery is not None or focused(n.name)]
    out(f"共 {len(nodes)} 个节点，筛出 {len(picked)} 个")
    for n in picked:
        out(f"  {n.name!r:<46} bat={str(n.battery):<5} en={n.enumerator:<8} "
            f"cls={n.class_name:<12} cid={n.container_id}")
        out(f"      iid={n.instance_id}")
    out()

    out("=== 3. HID 接口（相关名字 / 厂商通道） ===")
    ifaces = devapi.scan_hid_interfaces()
    picked_i = [i for i in ifaces if focused(i.product or "") or i.vendor_id == 0x12D1
                or i.usage_page >= 0xFF00]
    out(f"共 {len(ifaces)} 个接口，筛出 {len(picked_i)} 个")
    for i in picked_i:
        out(f"  {i.vid_pid:<14} up=0x{i.usage_page:04X} use=0x{i.usage:04X} "
            f"in={i.in_len:<4} out={i.out_len:<4} feat={i.feature_len:<4} "
            f"product={i.product!r}")
        out(f"      cid={i.container_id}  iid={i.instance_id}")
    out()

    out("=== 4. 各私有通道读数 ===")
    for name, fn in (("华为/荣耀", providers.scan_huawei),
                     ("Compx", providers.scan_compx),
                     ("雷蛇", providers.scan_razer),
                     ("罗技 HID++", providers.scan_logitech_battery)):
        try:
            out(f"  {name:<12}: {fn(0, ifaces)}")
        except Exception as exc:
            out(f"  {name:<12}: 读取异常 {type(exc).__name__}: {exc}")
    out()

    out("=== 5. 程序最终发现的设备 ===")
    providers.invalidate_vendor_caches()
    found = providers.discover(force=True)
    for d in found:
        out(f"  {d.name[:42]:<44} {d.kind_label:<4} {d.transport:<5} "
            f"{d.status:<11} level={str(d.level):<5} last={str(d.last_level):<5} "
            f"detail={d.detail!r} key={d.key}")
    out()

    out("=== 6. 当前配置 ===")
    try:
        from app.config import Config
        cfg = Config()
        out(f"  enabled     : {cfg['enabled']}")
        out(f"  initialized : {cfg['initialized']}")
        for key, info in (cfg.known or {}).items():
            out(f"  known {key:<38} {info.get('name')!r} "
                f"kind={info.get('kind')} transport={info.get('transport')} "
                f"last_level={info.get('last_level')}")
    except Exception as exc:
        out(f"  配置读取失败: {type(exc).__name__}: {exc}")
    out()

    out("=== 判断依据 ===")
    out("  · 蓝牙链路取电顺序：系统电量属性 → GATT 0x180F/0x2A19 → 厂商私有通道")
    out("  · USB / 2.4G 接收器链路：华为 0xFFB3、罗技 HID++、Compx、雷蛇、标准 HID 电池字段")
    out("  · 断开时不沿用任何旧读数；若上面 GATT 电量全部为 None 且设备确实连着，把本文件发回")
    out()

    with open(OUTPUT, "w", encoding="utf-8") as handle:
        handle.write("\n".join(_lines) + "\n")
    out(f"已保存：{OUTPUT}")


if __name__ == "__main__":
    main()
