"""Pure-Python validation of NameForge settings (no FreeCAD installation needed)."""
import importlib
import os
import sys
import tempfile
import types
import unittest


def load_relief():
    try:
        return importlib.import_module("freecad.RSMaker.relief")
    except ImportError as exc:
        if "PySide" not in str(exc):
            raise
        # Only QDialog is needed while defining the GUI class.
        side = types.ModuleType("PySide2")
        side.QtWidgets = types.SimpleNamespace(QDialog=type("QDialog", (object,), {}))
        sys.modules["PySide2"] = side
        try:
            return importlib.import_module("freecad.RSMaker.relief")
        finally:
            sys.modules.pop("PySide2", None)


relief = load_relief()


class ReliefConfigTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.svg = os.path.join(self.temp.name, "art.svg")
        self.font = os.path.join(self.temp.name, "font.ttf")
        with open(self.svg, "w", encoding="utf-8") as handle:
            handle.write('<svg xmlns="http://www.w3.org/2000/svg"><rect width="10" height="10"/></svg>')
        with open(self.font, "wb") as handle:
            handle.write(b"test-font")
        self.cfg = relief.ReliefConfig(svg_path=self.svg, font_path=self.font, text="Rodrigo")

    def test_valid_full_solid_parameters(self):
        self.assertEqual(self.cfg.validate().depth, 12.0)
        self.assertGreaterEqual(self.cfg.width, 30)

    def test_rejects_too_thin_base(self):
        from dataclasses import replace
        with self.assertRaisesRegex(ValueError, "profundidad"):
            replace(self.cfg, depth=0.4).validate()

    def test_rejects_empty_caption(self):
        from dataclasses import replace
        with self.assertRaises(ValueError):
            replace(self.cfg, text="  ").validate()

    def test_region_count_not_arbitrarily_limited(self):
        # More than 350 disjoint areas should pass the painter-order resolver.
        class Box:
            def __init__(self, i):
                self.BoundBox = type("Bounds", (), {"XMin":float(i), "XMax":float(i)+0.5,
                    "YMin":0.0,"YMax":0.5})()
                self.Volume = 0.5
            def isNull(self):
                return False
            def isValid(self):
                return True
        layers=[(Box(i), (0.1,0.2,0.3)) for i in range(351)]
        self.assertEqual(len(relief._visible_layers(layers)),351)

    def test_image_input_and_lamp_bridge_dimensions(self):
        from dataclasses import replace
        for extension in (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".svg"):
            cfg = replace(self.cfg, svg_path=os.path.join(self.temp.name, "art"+extension))
            self.assertEqual(cfg.validate().bridge_width, 1.6)
        with self.assertRaisesRegex(ValueError, "puente"):
            replace(self.cfg, bridge_width=0.4).validate()
        with self.assertRaisesRegex(ValueError, "colores"):
            replace(self.cfg, palette_colors=32).validate()

    def test_one_checkbox_switches_modes(self):
        from dataclasses import replace
        self.assertFalse(self.cfg.lamp_mode)  # existing saved designs are still solid
        lamp = replace(self.cfg, lamp_mode=True)
        self.assertTrue(lamp.validate().lamp_mode)
        self.assertEqual(relief.LAMP_FRONT, 2.0)
        self.assertEqual(relief.LAMP_WALL, 3.0)

    def test_lamp_needs_led_cavity_depth(self):
        from dataclasses import replace
        with self.assertRaisesRegex(ValueError, "lámpara"):
            replace(self.cfg, lamp_mode=True, depth=8.0).validate()
        self.assertEqual(replace(self.cfg, lamp_mode=True, depth=9.0).validate().depth, 9.0)
        # The solid box can remain thin.
        self.assertEqual(replace(self.cfg, lamp_mode=False, depth=2.0).validate().depth, 2.0)

    def test_svg_embedding_and_reload(self):
        content = relief._svg_xml(self.cfg)
        self.assertIn("<rect", content)
        os.remove(self.svg)
        self.assertEqual(relief._svg_xml(self.cfg, content, self.svg), content)

    def test_does_not_accept_external_xml_entities(self):
        with open(self.svg, "w", encoding="utf-8") as handle:
            handle.write('<!DOCTYPE svg [<!ENTITY evil SYSTEM "file:///etc/passwd">]><svg/>')
        with self.assertRaisesRegex(ValueError, "DOCTYPE"):
            relief._svg_xml(self.cfg)


if __name__ == "__main__":
    unittest.main()
