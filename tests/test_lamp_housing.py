"""Regression test: the lamp back and frame must be ONE printable solid.

Fake BReps exercise the FreeCAD-facing assembly without requiring a desktop
FreeCAD install in Python CI. A real OCC and physical print remain necessary.
"""
import importlib
import sys
import types
import unittest
from unittest.mock import patch


class FakeSolid:
    def __init__(self, name, start=0, end=0, cuts=()):
        self.name = name
        self.zmin = start
        self.zmax = end
        self.cuts = tuple(cuts)
        self.Solids = [self]
        self.BoundBox = types.SimpleNamespace(
            XMin=0, XMax=150, YMin=0, YMax=220)

    def translate(self, vector):
        self.zmin += vector.z
        self.zmax += vector.z

    def cut(self, other):
        return FakeSolid(self.name, self.zmin, self.zmax,
                         cuts=self.cuts + ((other.name,other.zmin,other.zmax),))

    def fuse(self, other):
        raise AssertionError(
            "No se permite unir tapa y marco: debe vaciarse un único sólido.")

    def removeSplitter(self):
        return self

    def isValid(self):
        return True

class FakePlanar:
    def __init__(self,name):
        self.name=name

    def extrude(self,vector):
        return FakeSolid(self.name, 0, vector.z)


class FakeVector:
    def __init__(self,x,y,z):
        self.x,self.y,self.z=x,y,z


class LampAssemblyTests(unittest.TestCase):
    def test_housing_is_one_shell_cut_from_one_solid(self):
        # In a real FreeCAD build the outer shell and back share the same
        # extrusion, then a smaller interior is removed. No fuse is allowed.
        dummy = types.ModuleType("PySide2")
        dummy.QtCore = types.SimpleNamespace()
        dummy.QtGui = types.SimpleNamespace()
        dummy.QtSvg = types.SimpleNamespace()
        fake_freecad = types.ModuleType("FreeCAD")
        fake_freecad.Vector = FakeVector
        fake_part = types.ModuleType("Part")
        fake_part.makeCylinder = lambda *args: FakeSolid("cable")

        fake_meta = dict(pixels=(12, 12), scale=2,
                         front_mask=bytearray(144),
                         rear_mask=bytearray(144),
                         cavity_mask=bytearray([1])*144,
                         front_paths=[],rear_paths=[],cavity_paths=[])
        cfg = types.SimpleNamespace(width=150,height=220,depth=12)
        visited = []

        def face(mask,w,h,scale,label,paths,splines=None):
            visited.append(label)
            return FakePlanar(label)

        with patch.dict(sys.modules, {"PySide2":dummy,
                                      "FreeCAD":fake_freecad,
                                      "Part":fake_part}):
            lamp = importlib.import_module("freecad.RSMaker.lamp_stencil")
            with patch.object(lamp, "_to_part", side_effect=face):
                parts = lamp.make_lamp(cfg,b"",".jpg",mask_meta=fake_meta)

        self.assertEqual(len(parts),2)
        self.assertEqual([p[0] for p in parts],
                         ["nameforge_frente","nameforge_marco"])
        self.assertEqual(parts[0][2].zmin,10)
        self.assertEqual(parts[0][2].zmax,12)
        housing=parts[1][2]
        self.assertEqual(visited,
                         ["frente","perímetro de carcasa","cavidad interior"])
        self.assertEqual((housing.zmin,housing.zmax),(0,10))
        self.assertEqual([cut[0] for cut in housing.cuts],
                         ["cavidad interior","cable"])
        self.assertEqual(housing.cuts[0][1:],(2.0,11.0))
        self.assertEqual(len(housing.Solids),1)
        self.assertTrue(housing.isValid())

    def test_housing_requires_nonempty_led_cavity(self):
        fake_meta=dict(pixels=(8,8),scale=1,
                       rear_mask=bytearray([1])*64,
                       cavity_mask=bytearray(64))
        cfg=types.SimpleNamespace(width=50,height=50,depth=12)
        fake_freecad=types.ModuleType("FreeCAD")
        fake_freecad.Vector=FakeVector
        fake_part=types.ModuleType("Part")
        with patch.dict(sys.modules,{"FreeCAD":fake_freecad,"Part":fake_part}):
            from freecad.RSMaker import lamp_stencil as lamp
            with patch.object(lamp,"_to_part",
                              return_value=FakePlanar("perímetro")):
                with self.assertRaisesRegex(ValueError,"No se pudo crear"):
                    lamp._closed_back_housing(fake_meta,8,8,1,cfg)

if __name__=="__main__":
    unittest.main()
