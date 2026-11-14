"""Bed packing and safe FreeCAD STL export regression tests (no GUI needed)."""
import json
import math
import os
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

from freecad.RSMaker import print_plates as plates


class PackingTests(unittest.TestCase):
    def test_layout_is_deterministic_and_never_overlaps(self):
        sizes=[("Base",170,160),("Tapa",169.3,159.3)]
        sizes.extend(("Hardware_%d"%i,20+(i%5),12+(i%3))
                     for i in range(70))
        first=plates.plan_plates(sizes,430,430,8,6)
        second=plates.plan_plates(reversed(sizes),430,430,8,6)
        self.assertEqual(first,second)
        self.assertEqual(len(first),len(sizes))
        for p in first:
            self.assertGreaterEqual(p.x,8)
            self.assertGreaterEqual(p.y,8)
            self.assertLessEqual(p.x+p.width,422.00001)
            self.assertLessEqual(p.y+p.depth,422.00001)
        for i,a in enumerate(first):
            for b in first[i+1:]:
                if a.plate!=b.plate:
                    continue
                horizontal=(a.x+a.width+5.9999<=b.x or
                            b.x+b.width+5.9999<=a.x)
                vertical=(a.y+a.depth+5.9999<=b.y or
                          b.y+b.depth+5.9999<=a.y)
                self.assertTrue(horizontal or vertical,(a,b))

    def test_small_printer_automatically_uses_multiple_plates(self):
        result=plates.plan_plates(
            [("P%d"%i,100,100) for i in range(6)],220,220,5,5)
        self.assertEqual(max(p.plate for p in result),2)

    def test_rejects_oversized_and_invalid_items(self):
        with self.assertRaisesRegex(ValueError,"no cabe"):
            plates.plan_plates([("Base",420,160)],430,430,8,6)
        for items in ([("a",20,20),("a",30,30)],
                      [("../evil",10,10)],
                      [("broken",float("nan"),10)]):
            with self.subTest(items=items):
                with self.assertRaises(ValueError):
                    plates.plan_plates(items)
        with self.assertRaisesRegex(ValueError,"separación"):
            plates.plan_plates([("pieza",12,12)],430,430,8,1)

    def test_no_reorientation_or_unstated_rotation(self):
        result=plates.plan_plates([("LongPart",150,45)],160,80,5,3)
        self.assertEqual((result[0].width,result[0].depth),(150,45))


class FakeBBox:
    def __init__(self,x,y,z,w,d,h):
        self.XMin=x
        self.YMin=y
        self.ZMin=z
        self.XMax=x+w
        self.YMax=y+d
        self.ZMax=z+h


class FakeShape:
    def __init__(self,key,x,y,z,w,d,h,valid=True,solid_count=1):
        self.key=key
        self.BoundBox=FakeBBox(x,y,z,w,d,h)
        self.valid=valid
        self.Solids=[object() for _ in range(solid_count)]

    def isValid(self):
        return self.valid

    def isNull(self):
        return False


class FakeMesh:
    def __init__(self,source=None):
        self.components=[(source, (0,0,0))] if source else []

    def translate(self,v):
        self.components=[(k,(x+v[0],y+v[1],z+v[2]))
                         for k,(x,y,z) in self.components]

    def addMesh(self,other):
        self.components+=other.components

    def write(self,path):
        with open(path,"w",encoding="utf-8") as fp:
            json.dump(self.components,fp)


class FakeMeshPart:
    @staticmethod
    def meshFromShape(Shape,**kw):
        assert kw["LinearDeflection"]==.10
        assert kw["Relative"] is False
        return FakeMesh(Shape.key)


def root_of(*shapes):
    return types.SimpleNamespace(Group=[
        types.SimpleNamespace(RSMakerPartKey=shape.key,Shape=shape)
        for shape in shapes
    ])


class ExportTests(unittest.TestCase):
    def test_individual_stl_are_lowered_without_changing_cad_shapes(self):
        root=root_of(FakeShape("Base",100,70,22,170,160,95),
                     FakeShape("C1_Rueda",-6,-4,87,10,10,6))
        before=[obj.Shape.BoundBox.ZMin for obj in root.Group]
        fakeapp=types.ModuleType("FreeCAD")
        fakeapp.Vector=lambda x,y,z:(x,y,z)
        mesh=types.ModuleType("Mesh")
        mesh.Mesh=FakeMesh
        meshpart=types.ModuleType("MeshPart")
        meshpart.meshFromShape=FakeMeshPart.meshFromShape
        with tempfile.TemporaryDirectory() as temp,patch.dict(
                sys.modules,{"FreeCAD":fakeapp,"Mesh":mesh,
                             "MeshPart":meshpart}):
            created=plates.export_separate(root,temp)
            self.assertEqual(set(created),{"Base.stl","C1_Rueda.stl"})
            self.assertEqual(
                json.load(open(os.path.join(temp,"Base.stl"),encoding="utf-8")),
                [["Base",[-100,-70,-22]]])
            self.assertEqual(
                json.load(open(os.path.join(temp,"C1_Rueda.stl"),encoding="utf-8")),
                [["C1_Rueda",[6,4,-87]]])
            self.assertEqual(before,
                             [obj.Shape.BoundBox.ZMin for obj in root.Group])

    def test_plates_write_combined_mesh_and_readable_manifest(self):
        root=root_of(FakeShape("Base",40,35,20,170,160,95),
                     FakeShape("Tapa",30,45,110,170,160,5),
                     FakeShape("Chibi",95,90,120,18,16,25))
        fakeapp=types.ModuleType("FreeCAD")
        fakeapp.Vector=lambda x,y,z:(x,y,z)
        mesh=types.ModuleType("Mesh")
        mesh.Mesh=FakeMesh
        meshpart=types.ModuleType("MeshPart")
        meshpart.meshFromShape=FakeMeshPart.meshFromShape
        with tempfile.TemporaryDirectory() as temp,patch.dict(
                sys.modules,{"FreeCAD":fakeapp,"Mesh":mesh,
                             "MeshPart":meshpart}):
            report=plates.export_plates(root,temp,430,430,8,6)
            self.assertEqual(len(report["plates"]),1)
            name=report["plates"][0]["file"]
            self.assertEqual(name,"Plato_01.stl")
            combined=json.load(open(os.path.join(temp,name),encoding="utf-8"))
            self.assertEqual({row[0] for row in combined},
                             {"Base","Tapa","Chibi"})
            self.assertEqual(len(combined),3)
            self.assertEqual(
                json.load(open(os.path.join(temp,"Platos_RS_Maker.json"),
                               encoding="utf-8")),report)
            part_coordinates={item["key"]:(item["x_mm"],item["y_mm"])
                              for item in report["plates"][0]["parts"]}
            self.assertEqual(part_coordinates["Base"],(8.0,8.0))
            self.assertEqual(part_coordinates["Tapa"],(184.0,8.0))
            self.assertEqual(part_coordinates["Chibi"],(360.0,8.0))
            # Z of every individual mesh is brought to the bed; no changes
            # are made to the FreeCAD document or original shapes.
            translations=dict(combined)
            self.assertEqual(translations["Base"][2],-20)
            self.assertEqual(translations["Tapa"][2],-110)
            self.assertEqual(translations["Chibi"][2],-120)

    def test_failure_does_not_leave_partial_stls(self):
        root=root_of(FakeShape("Base",0,0,0,430,430,5))
        fakeapp=types.ModuleType("FreeCAD")
        fakeapp.Vector=lambda x,y,z:(x,y,z)
        mesh=types.ModuleType("Mesh")
        mesh.Mesh=FakeMesh
        meshpart=types.ModuleType("MeshPart")
        meshpart.meshFromShape=FakeMeshPart.meshFromShape
        with tempfile.TemporaryDirectory() as temp,patch.dict(
                sys.modules,{"FreeCAD":fakeapp,"Mesh":mesh,
                             "MeshPart":meshpart}):
            with self.assertRaisesRegex(ValueError,"no cabe"):
                plates.export_plates(root,temp,430,430,8,6)
            self.assertEqual(os.listdir(temp),[])

    def test_nameforge_colour_compounds_stay_exportable(self):
        group=root_of(FakeShape("Color_A",0,0,7,20,20,2,
                                solid_count=3))
        group.RSMakerReliefSchema=7
        self.assertEqual(len(plates._generated_objects(group)),1)
        # For multicolour layers, their original XY alignment is preserved.
        fakeapp=types.ModuleType("FreeCAD")
        fakeapp.Vector=lambda x,y,z:(x,y,z)
        fakepart=types.ModuleType("MeshPart")
        fakepart.meshFromShape=FakeMeshPart.meshFromShape
        with tempfile.TemporaryDirectory() as temp,patch.dict(
                sys.modules,{"FreeCAD":fakeapp,"MeshPart":fakepart}):
            self.assertEqual(plates.export_separate(
                group,temp,keep_xy=True),["Color_A.stl"])
            self.assertEqual(
                json.load(open(os.path.join(temp,"Color_A.stl"),
                               encoding="utf-8")),
                [["Color_A",[0,0,-7]]])

    def test_duplicate_printable_part_keys_fail_before_export(self):
        group=root_of(FakeShape("A",0,0,0,2,2,2),
                      FakeShape("A",1,1,1,3,3,3))
        with self.assertRaisesRegex(ValueError,"duplicada"):
            plates._generated_objects(group)

    def test_non_solid_or_invalid_shape_is_rejected(self):
        root=root_of(FakeShape("Bad",0,0,0,20,20,10,solid_count=2))
        with self.assertRaisesRegex(ValueError,"sólido único"):
            plates._generated_objects(root)
        root=root_of(FakeShape("Bad",0,0,0,20,20,10,valid=False))
        with self.assertRaisesRegex(ValueError,"CAD inválido"):
            plates._generated_objects(root)


if __name__=="__main__":
    unittest.main()
