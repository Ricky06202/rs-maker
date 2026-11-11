"""Independent OpenCascade geometry check for the flat-printable LED frame.

Requires optional CadQuery. CI without OCC skips these checks. This does not
replace a real FreeCAD GUI or physical print test.
"""
import sys
import types
import unittest
from unittest.mock import patch

from test_relief_config import relief

try:
    import cadquery as cq
except ImportError:
    cq = None


@unittest.skipUnless(cq is not None, "CadQuery/OpenCascade not installed")
class LampFrameTests(unittest.TestCase):
    def test_frame_is_single_valid_open_solid_with_wire_exit(self):
        class Shape:
            def __init__(self, shape):
                self.s = shape
            def cut(self, other):
                return Shape(self.s.cut(other.s))
            def removeSplitter(self):
                return Shape(self.s.clean())
            def isValid(self):
                return self.s.isValid()
            @property
            def Solids(self):
                return self.s.Solids()

        app = types.ModuleType("FreeCAD")
        app.Vector = lambda *args: tuple(args)
        part = types.ModuleType("Part")
        part.makeBox = lambda x, y, z, p=(0, 0, 0): Shape(
            cq.Solid.makeBox(x, y, z, cq.Vector(*p)))
        with patch.dict(sys.modules, {"FreeCAD": app, "Part": part}):
            frame_cfg = relief.ReliefConfig(lamp_mode=True)
            frame = relief._lamp_frame(frame_cfg)
        self.assertTrue(frame.isValid())
        self.assertEqual(len(frame.Solids), 1)
        self.assertAlmostEqual(frame.s.BoundingBox().zmin, 0, places=5)
        self.assertAlmostEqual(frame.s.BoundingBox().zmax,
                               frame_cfg.depth - relief.LAMP_FRONT, places=5)
        cavity = cq.Solid.makeBox(frame_cfg.width - 2 * relief.LAMP_WALL,
                                  frame_cfg.height - 2 * relief.LAMP_WALL,
                                  frame_cfg.depth - relief.LAMP_FRONT,
                                  cq.Vector(relief.LAMP_WALL,
                                            relief.LAMP_WALL, 0))
        self.assertLess(frame.s.intersect(cavity).Volume(), 1e-5)
        exit_channel = cq.Solid.makeBox(5.5, relief.LAMP_WALL, 3,
                                        cq.Vector(frame_cfg.width / 2 - 2.75, 0, 0))
        self.assertLess(frame.s.intersect(exit_channel).Volume(), 1e-5)


if __name__ == "__main__":
    unittest.main()
