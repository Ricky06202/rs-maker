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
    def __init__(self, name, start=0, end=0, fused=()):
        self.name = name
        self.zmin = start
        self.zmax = end
        self.fused = fused
        self.Solids = [self]
        self.BoundBox = types.SimpleNamespace(
            XMin=0, XMax=150, YMin=0, YMax=220)

    def translate(self, vector):
        self.zmin += vector.z
        self.zmax += vector.z

    def cut(self, other):
        return self

    def fuse(self, other):
        if abs(self.zmax - other.zmin) > 1e-6:
            raise ValueError("Carcasa sin contacto entre tapa y marco")
        return FakeSolid("carcasa", self.zmin, other.zmax,
                         fused=(self.name,other.name))

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
    def test_frame_and_rear_are_fused_into_one_output(self):
        # Module import is guarded: no Qt or FreeCAD in CI.
        dummy = types.ModuleType("PySide2")
        dummy.QtCore = types.SimpleNamespace()
        dummy.QtGui = types.SimpleNamespace()
        dummy.QtSvg = types.SimpleNamespace()
        fake_freecad = types.ModuleType("FreeCAD")
        fake_freecad.Vector = FakeVector
        fake_part = types.ModuleType("Part")
        fake_part.makeCylinder=lambda *args: FakeSolid("hole")
        fake_meta = dict(pixels=(12,12),scale=2,
                         front_mask=bytearray(144),
                         frame_mask=bytearray(144),
                         rear_mask=bytearray(144),
                         front_paths=[],frame_paths=[],rear_paths=[])
        cfg=types.SimpleNamespace(width=150,height=220,depth=12)
        with patch.dict(sys.modules, {"PySide2":dummy,
                                      "FreeCAD":fake_freecad,
                                      "Part":fake_part}):
            lamp=importlib.import_module("freecad.RSMaker.lamp_stencil")
            with patch.object(lamp,"_to_part",
                              side_effect=lambda mask,w,h,scale,label,paths:
                                  FakePlanar(label)):
                parts=lamp.make_lamp(cfg,b"",".jpg",mask_meta=fake_meta)
        self.assertEqual(len(parts),2)
        self.assertEqual([p[0] for p in parts],
                         ["nameforge_frente","nameforge_marco"])
        self.assertEqual(parts[0][2].zmin,10)
        self.assertEqual(parts[0][2].zmax,12)
        housing=parts[1][2]
        self.assertEqual(housing.fused,("tapa trasera","marco"))
        self.assertEqual((housing.zmin,housing.zmax),(0,10))
        self.assertEqual(len(housing.Solids),1)


if __name__=="__main__":
    unittest.main()
