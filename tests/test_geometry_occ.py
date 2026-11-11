"""Optional independent OCC BRep tests with a tiny FreeCAD Part compatibility shim.

Running these tests is NOT equivalent to launching the FreeCAD 1.x GUI,
modeling a full-motion mechanism or verifying child safety.
"""
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
try:
    import cadquery as cq
except ImportError:
    cq=None

@unittest.skipUnless(cq is not None,"CadQuery not installed (FreeCAD still needs live tests)")
class TestGeometryOCC(unittest.TestCase):
    def shim(self):
        class Shape:
            def __init__(self,shape):self.s=shape
            @property
            def Volume(self):return self.s.Volume()
            def isValid(self):return self.s.isValid()
            def copy(self):return Shape(self.s)
            def cut(self,other):return Shape(self.s.cut(other.s))
            def common(self,other):return Shape(self.s.intersect(other.s))
            def fuse(self,other):return Shape(self.s.fuse(other.s))
            def removeSplitter(self):return Shape(self.s.clean())
            def rotate(self,center,axis,angle):
                self.s=self.s.rotate(cq.Vector(*center),cq.Vector(*center)+cq.Vector(*axis),angle)
            def translate(self,vector): self.s=self.s.translate(cq.Vector(*vector))
        class Face:
            def __init__(self,wire):self.f=cq.Face.makeFromWires(wire)
            def extrude(self,vector):return Shape(cq.Solid.extrudeLinear(self.f,cq.Vector(*vector)))
        app=types.ModuleType('FreeCAD')
        app.Vector=lambda *args:tuple(args)
        part=types.ModuleType('Part')
        part.makeBox=lambda x,y,z,p=(0,0,0):Shape(cq.Solid.makeBox(x,y,z,cq.Vector(*p)))
        part.makeCylinder=lambda r,h,p=(0,0,0),direction=(0,0,1):Shape(
            cq.Solid.makeCylinder(r,h,cq.Vector(*p),cq.Vector(*direction)))
        part.makeSphere=lambda r,p=(0,0,0):Shape(cq.Solid.makeSphere(r,cq.Vector(*p)))
        part.makePolygon=lambda points:cq.Wire.makePolygon([cq.Vector(*p) for p in points])
        part.Face=Face
        return app,part

    def get_parts(self,cfg):
        from freecad.RSMaker.geometry import build_shapes
        fakeapp,fakepart=self.shim()
        with patch.dict(sys.modules,{'FreeCAD':fakeapp,'Part':fakepart}):
            return {key:shape for key,shape,_ in build_shapes(cfg)}

    def test_five_lock_machinery_and_valid_brep(self):
        from freecad.RSMaker.config import PuzzleConfig
        parts=self.get_parts(PuzzleConfig(theme='Ninguno'))
        expected=['C%d_%s'%(i,typ) for i in range(1,5)
                        for typ in ('Cerrojo','Rueda')]
        self.assertEqual(len(parts),13)  # Base, Tapa, 8 sides, 3 top
        for item in expected+['Base','Tapa','Tapa_Dial','Tapa_Leva','Tapa_Retenedor']:
            self.assertIn(item,parts)
        for name,part in parts.items():
            with self.subTest(name=name):
                self.assertTrue(part.isValid(),name)
                self.assertGreater(part.Volume,.1,name)

    def test_disjoint_base_lid_and_hardware_in_closed_state(self):
        from freecad.RSMaker.config import PuzzleConfig
        p=self.get_parts(PuzzleConfig(theme='Ninguno'))
        self.assertLess(p['Base'].s.intersect(p['Tapa'].s).Volume(),1e-3)
        # The side rods pass within *oversized* holes of the lid lugs.
        for i in range(1,5):
            rod=p[f'C{i}_Cerrojo'].s
            self.assertLess(rod.intersect(p['Base'].s).Volume(),1e-3,f'base / rod {i}')
            self.assertLess(rod.intersect(p['Tapa'].s).Volume(),1e-3,f'lid / rod {i}')
            wheel=p[f'C{i}_Rueda'].s
            self.assertLess(wheel.intersect(p['Base'].s).Volume(),1e-3,f'base / wheel {i}')
            self.assertLess(wheel.intersect(rod).Volume(),1e-3,f'wheel / rod {i}')
        for name in ('Tapa_Dial','Tapa_Leva','Tapa_Retenedor'):
            self.assertLess(p[name].s.intersect(p['Base'].s).Volume(),1e-3,name)
            self.assertLess(p[name].s.intersect(p['Tapa'].s).Volume(),1e-3,name)

    def test_per_face_difficulty_does_not_remove_parts(self):
        from freecad.RSMaker.config import PuzzleConfig
        p=self.get_parts(PuzzleConfig(frontal='Difícil',derecha='Fácil',
                                      trasera='Medio',izquierda='Difícil',
                                      tapa='Difícil',theme='Estrellas'))
        self.assertEqual(len(p),14)
        self.assertIn('Decoracion_Estrellas',p)
        for name,solid in p.items():
            self.assertTrue(solid.isValid(),name)

if __name__=='__main__':unittest.main()
