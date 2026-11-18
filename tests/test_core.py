"""纯逻辑单元测试（不启动窗口，不访问真实设备）。"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from app.model import (  # noqa: E402
    AppState, Device, HEADSET, KEYBOARD, MOUSE, OFFLINE, ONLINE, UNSUPPORTED,
)
from app.config import Config  # noqa: E402

IS_WINDOWS = sys.platform == "win32"


class ModelTests(unittest.TestCase):
    def test_status_text(self):
        dev = Device("k", "鼠标", MOUSE, "2.4G")
        self.assertEqual(dev.status_text(), "2.4G · 已连接")
        dev.charging = True
        self.assertEqual(dev.status_text(), "2.4G · 充电中")

        dev.status = OFFLINE
        self.assertEqual(dev.status_text(), "2.4G · 未连接")

        dev.status = UNSUPPORTED
        self.assertEqual(dev.status_text(), "2.4G · 不支持电量读取")
        dev.detail = "厂商私有协议，暂未适配"
        self.assertEqual(dev.status_text(), "2.4G · 厂商私有协议，暂未适配")

        dev.detail = ""
        self.assertEqual(dev.kind_label, "鼠标")
        self.assertEqual(Device("k", "x", HEADSET).kind_label, "耳机")
        self.assertEqual(Device("k", "x", KEYBOARD).kind_label, "键盘")

    def test_sort_key_prefers_online_then_mouse(self):
        online_mouse = Device("a", "B", MOUSE, status=ONLINE)
        online_keys = Device("b", "A", KEYBOARD, status=ONLINE)
        offline_mouse = Device("c", "A", MOUSE, status=OFFLINE)
        ordered = sorted([offline_mouse, online_keys, online_mouse], key=lambda d: d.sort_key())
        self.assertEqual([d.key for d in ordered], ["a", "b", "c"])

    def test_app_state_defaults(self):
        state = AppState()
        self.assertEqual(state.devices, [])
        self.assertFalse(state.refreshing)
        state.devices.append(Device("a", "b"))
        self.assertEqual(len(AppState().devices), 0)


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "config.json")

    def tearDown(self):
        self.tmp.cleanup()

    def test_defaults_and_enable(self):
        cfg = Config(self.path)
        self.assertEqual(cfg["interval"], 60)
        self.assertEqual(cfg["enabled"], [])
        self.assertFalse(cfg["initialized"])
        self.assertIsNone(cfg["missing_key"])

        cfg.toggle_enabled("bt:aa")
        self.assertTrue(cfg.is_enabled("bt:aa"))
        self.assertTrue(cfg["initialized"])
        cfg.toggle_enabled("bt:aa")
        self.assertFalse(cfg.is_enabled("bt:aa"))

    def test_save_load_roundtrip(self):
        cfg = Config(self.path)
        cfg["interval"] = 120
        cfg["theme"] = "dark"
        cfg.set_enabled("hid:x", True)
        cfg.remember(Device("hid:x", "鼠标", MOUSE, "2.4G", level=88))
        cfg.save()

        again = Config(self.path)
        self.assertEqual(again["interval"], 120)
        self.assertEqual(again["theme"], "dark")
        self.assertEqual(again["enabled"], ["hid:x"])
        self.assertEqual(again.known["hid:x"]["last_level"], 88)
        self.assertEqual(again.known["hid:x"]["name"], "鼠标")

    def test_remember_ignores_unknown_level_for_offline(self):
        cfg = Config(self.path)
        cfg.remember(Device("k", "鼠标", MOUSE, status=OFFLINE, level=None, last_level=70))
        self.assertNotIn("last_level", cfg.known["k"])

    def test_corrupted_file_falls_back(self):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write("{ not json")
        cfg = Config(self.path)
        self.assertEqual(cfg["interval"], 60)

    def test_unknown_keys_ignored(self):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump({"interval": 300, "bogus": 1, "known": []}, f)
        cfg = Config(self.path)
        self.assertEqual(cfg["interval"], 300)
        self.assertEqual(cfg.known, {})
        self.assertNotIn("bogus", cfg.data)


@unittest.skipUnless(IS_WINDOWS, "HID / SetupAPI 仅 Windows")
class ProviderTests(unittest.TestCase):
    def setUp(self):
        from app import providers
        self.p = providers

    def test_clean_bt_name(self):
        self.assertEqual(self.p.clean_bt_name("MX Keys Mini Hands-Free AG"), "MX Keys Mini")
        self.assertEqual(self.p.clean_bt_name("FreeBuds 6i Avrcp 传输"), "FreeBuds 6i")
        self.assertEqual(self.p.clean_bt_name("  Mouse  "), "Mouse")

    def test_infer_kind(self):
        self.assertEqual(self.p.infer_kind("MX Master 3S"), MOUSE)
        self.assertEqual(self.p.infer_kind("Keychron K3"), KEYBOARD)
        self.assertEqual(self.p.infer_kind("HUAWEI FreeBuds 6i"), HEADSET)
        self.assertEqual(self.p.infer_kind("未知设备", {"Mouse"}), MOUSE)
        self.assertEqual(self.p.infer_kind("未知设备", {"AudioEndpoint"}), HEADSET)
        self.assertEqual(self.p.infer_kind("未知设备"), "other")

    def test_bt_mac(self):
        iid = r"BTHENUM\DEV_001122AABBCC\7&1F2E3D4C&0&BLUETOOTHDEVICE_001122AABBCC"
        self.assertEqual(self.p._bt_mac(iid), "001122AABBCC")
        self.assertIsNone(self.p._bt_mac(r"USB\VID_046D&PID_C52B\5&1A2B3C4D&0&2"))

    def test_group_container_classes(self):
        nodes = [
            SimpleNamespace(container_id="c1", class_name="Mouse"),
            SimpleNamespace(container_id="c1", class_name="HIDClass"),
            SimpleNamespace(container_id=None, class_name="Mouse"),
        ]
        self.assertEqual(self.p.group_container_classes(nodes), {"c1": {"Mouse", "HIDClass"}})

    def test_compx_frames(self):
        frame = self.p.COMPX_FRAME_52
        self.assertEqual(len(frame), 17)
        self.assertEqual(sum(frame) & 0xFF, 0x55)
        self.assertEqual(self.p.COMPX_FRAME_54.hex(), "087d720200010701")

    def test_known_vendor_channel(self):
        huawei = SimpleNamespace(vendor_id=0x12D1, usage_page=0xFFB3, product_id=0)
        compx = SimpleNamespace(vendor_id=0x373B, usage_page=0xFF05, product_id=0)
        razer = SimpleNamespace(vendor_id=0x1532, usage_page=0x0001, product_id=0x00A5)
        other = SimpleNamespace(vendor_id=0x1234, usage_page=0xFF00, product_id=1)
        self.assertTrue(self.p._is_known_vendor_channel(huawei))
        self.assertTrue(self.p._is_known_vendor_channel(compx))
        self.assertTrue(self.p._is_known_vendor_channel(razer))
        self.assertFalse(self.p._is_known_vendor_channel(other))

    def test_scan_vendor_cache_dedupe_and_stale(self):
        calls = []

        def reader(itf):
            calls.append(itf.container_id)
            return (77, False)

        cache = self.p._Cache()
        a = SimpleNamespace(container_id="c1")
        b = SimpleNamespace(container_id="c1")
        out = self.p._scan_vendor([a, b], lambda i: True, reader, cache, 60)
        self.assertEqual(out, {"c1": (77, False)})
        self.assertEqual(calls, ["c1"])

        # TTL 内不再读设备
        self.p._scan_vendor([a], lambda i: True, reader, cache, 60)
        self.assertEqual(calls, ["c1"])

        # 强制刷新时设备无应答，沿用上次读数
        out = self.p._scan_vendor([a], lambda i: True, lambda i: None, cache, 0)
        self.assertEqual(out, {"c1": (77, False)})

    def test_scan_vendor_skips_without_container(self):
        cache = self.p._Cache()
        called = []
        out = self.p._scan_vendor(
            [SimpleNamespace(container_id=None)], lambda i: True,
            lambda i: called.append(1), cache, 0,
        )
        self.assertEqual(out, {})
        self.assertEqual(called, [])

    def test_invalidate_vendor_caches(self):
        self.p._HW_CACHE.put("a", 50, False)
        self.p._CX_CACHE.put("b", 60, True)
        self.p._RZ_CACHE.put("c", 70, False)
        self.p.invalidate_vendor_caches()
        self.assertIsNone(self.p._HW_CACHE.last("a"))
        self.assertIsNone(self.p._CX_CACHE.last("b"))
        self.assertIsNone(self.p._RZ_CACHE.last("c"))


@unittest.skipUnless(IS_WINDOWS, "HID 结构体仅 Windows")
class DevapiTests(unittest.TestCase):
    def setUp(self):
        from app import devapi
        self.d = devapi

    def _caps(self, lo, hi):
        vc = self.d.HIDP_VALUE_CAPS()
        vc.LogicalMin = lo
        vc.LogicalMax = hi
        return vc

    def test_normalize_battery(self):
        self.assertEqual(self.d._normalize_battery(100, self._caps(0, 100)), 100)
        self.assertEqual(self.d._normalize_battery(128, self._caps(0, 255)), 50)
        self.assertIsNone(self.d._normalize_battery(101, self._caps(0, 100)))
        # 逻辑值域不合法时只接受 0–100
        self.assertEqual(self.d._normalize_battery(80, self._caps(0, 0)), 80)
        self.assertIsNone(self.d._normalize_battery(200, self._caps(0, 0)))

    def test_battery_usage(self):
        vc = self.d.HIDP_VALUE_CAPS()
        vc.UsagePage = 0x06
        vc.IsRange = 0
        vc.u.NotRange.Usage = 0x20
        self.assertEqual(self.d._battery_usage(vc), 0x20)

        vc.UsagePage = 0x0D
        vc.u.NotRange.Usage = 0x30
        self.assertIsNone(self.d._battery_usage(vc))

        vc.UsagePage = 0x06
        vc.IsRange = 1
        vc.u.Range.UsageMin = 0x20
        vc.u.Range.UsageMax = 0x2F
        self.assertEqual(self.d._battery_usage(vc), 0x20)


class ThemeTests(unittest.TestCase):
    def test_mix_is_opaque_and_between(self):
        from app.theme import LIGHT, DARK
        c = LIGHT.mix("accent", "panel", 0.5)
        self.assertEqual(len(c), 4)
        self.assertEqual(c[3], 255)
        self.assertTrue(0 < c[0] < 255)
        self.assertEqual(DARK.c("panel")[3], 255)

    def test_resolve_theme(self):
        from app.theme import resolve_theme
        self.assertTrue(resolve_theme("dark").dark)
        self.assertFalse(resolve_theme("light").dark)
        self.assertIn(resolve_theme("auto").dark, (True, False))


class DrawTests(unittest.TestCase):
    def test_canvas_render_and_text(self):
        from app.draw import Canvas
        from app.theme import Fonts, LIGHT
        c = Canvas((120, 40), 1.0, 2)
        c.rrect((4, 4, 116, 36), 8, fill=LIGHT.c("panel"), outline=LIGHT.c("line"))
        c.text((12, 20), "电量 88%", Fonts(1.0).get(12), LIGHT.c("text"))
        img = c.finish()
        self.assertEqual(img.size, (120, 40))
        self.assertEqual(img.mode, "RGBA")
        self.assertIsNotNone(img.getbbox())
        self.assertEqual(img.getpixel((60, 20))[3], 255)

    def test_ellipsize(self):
        from PIL import ImageFont
        from app.draw import ellipsize
        font = ImageFont.load_default()
        out = ellipsize("abcdefghij" * 4, font, 40)
        self.assertTrue(out.endswith("…"))
        self.assertLess(len(out), 40)
        self.assertEqual(ellipsize("短", font, 200), "短")

    def test_mixed_script_fonts(self):
        """中英按字符分流：西文走 Segoe，比整段用雅黑的拉丁字形窄。"""
        from PIL import Image, ImageDraw, ImageFont
        from app.draw import render_text, text_width
        from app.theme import Fonts
        fonts = Fonts(1.0)
        font = fonts.get(13, "regular")
        latin = "HUAWEI FreeBuds 6i"
        mono = ImageDraw.Draw(Image.new("RGBA", (2, 2))).textlength(latin, font=font)
        self.assertLess(text_width(latin, font), mono)
        self.assertIsNotNone(render_text(latin + " 耳机", font,
                                         (240, 240, 240, 255)).getbbox())
        # 边界：空串、数字专用字体、没有重建信息的默认字体都不能炸
        self.assertEqual(text_width("", font), 0.0)
        self.assertEqual(text_width("", fonts.get(13, "semibold", True)), 0.0)
        plain = ImageFont.load_default()
        self.assertIsNotNone(render_text("Ab 中文", plain,
                                         (255, 255, 255, 255)).getbbox())

    def test_battery_glyph(self):
        from app.draw import battery_glyph
        img = battery_glyph(16, 80, (18, 161, 80, 255))
        self.assertEqual(img.size, (16, 16))
        self.assertIsNotNone(img.getbbox())
        charging = battery_glyph(16, 50, (47, 114, 240, 255), charging=True)
        self.assertIsNotNone(charging.getbbox())


if __name__ == "__main__":
    unittest.main(verbosity=2)
