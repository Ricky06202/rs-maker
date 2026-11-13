"""Independent OpenCascade regression for two-step linear gate puzzles.

The vertical gate must block the 8-mm intermediate horizontal bolt motion
until moved down 12 mm. Tests check BRep solids and swept interference,
not human playability, friction, retention forces or printed tolerances.
"""
from dataclasses import replace
from types import SimpleNamespace
import unittest

from freecad.RSMaker.config import PuzzleConfig
from freecad.RSMaker import project as project_model
import test_geometry_occ as occ

cq=occ.cq


class SchemaMigrationTests(unittest.TestCase):
    def test_v3_projects_default_to_four_original_rotary_wheels(self):
        old=PuzzleConfig()
        properties=dict(RSMakerSchema=3,Theme=old.theme,
                        FigureHeight=old.figure_height,
                        Collection=old.collection,Figure=old.figure,
                        Scene=old.scene,Expression=old.expression)
        for name in project_model.DIMENSION_FIELDS:
            properties[name]=getattr(old,name)
        for name in project_model.DIFFICULTY_FIELDS:
            properties[name.capitalize()]=getattr(old,name)
        cfg=project_model.config_from_project(SimpleNamespace(**properties))
        for face in ("Frontal","Derecha","Trasera","Izquierda"):
            self.assertEqual(cfg.face_mechanism(face),"cerrojo_rueda")

    def test_v4_projects_retain_per_face_selected_mechanisms(self):
        old=PuzzleConfig()
        data=dict(RSMakerSchema=4,Theme=old.theme,
                  FigureHeight=old.figure_height,Collection=old.collection,
                  Figure=old.figure,Scene=old.scene,Expression=old.expression,
                  MecanismoFrontal="secuencia")
        for name in project_model.DIMENSION_FIELDS:
            data[name]=getattr(old,name)
        for name in project_model.DIFFICULTY_FIELDS:
            data[name.capitalize()]=getattr(old,name)
        cfg=project_model.config_from_project(SimpleNamespace(**data))
        self.assertEqual(cfg.face_mechanism("Frontal"),"secuencia")
        self.assertEqual(cfg.face_mechanism("Derecha"),"cerrojo_rueda")


@unittest.skipUnless(cq is not None,"CadQuery/OCP no instalado")
class SequentialLockOCCTests(unittest.TestCase):
    def setUp(self):
        self.builder=occ.TestGeometryOCC()
        self.config=PuzzleConfig(theme="Ninguno",
                                 mecanismo_frontal="secuencia").validate()

    def test_side_gate_and_cap_are_separate_valid_printable_solids(self):
        parts=self.builder.get_parts(self.config)
        self.assertEqual(len(parts),14)  # One wheel -> gate + top cap
        self.assertNotIn("C1_Rueda",parts)
        for key in ("Base","Tapa","C1_Cerrojo","C1_Compuerta",
                    "C1_SeguroCompuerta"):
            self.assertIn(key,parts)
            self.assertTrue(parts[key].isValid(),key)
            self.assertEqual(len(parts[key].s.Solids()),1,key)
        for i in (2,3,4):
            self.assertIn("C%d_Rueda"%i,parts)
        base=parts["Base"].s
        gate=parts["C1_Compuerta"].s
        cap=parts["C1_SeguroCompuerta"].s
        latch=parts["C1_Cerrojo"].s
        self.assertLess(base.intersect(gate).Volume(),.001)
        self.assertLess(base.intersect(cap).Volume(),.001)
        self.assertLess(gate.intersect(cap).Volume(),.001)
        self.assertLess(gate.intersect(latch).Volume(),.001)
        self.assertLess(cap.intersect(parts["Tapa"].s).Volume(),.001)

    def test_locked_gate_obstructs_bolt_then_drops_to_release(self):
        p=self.builder.get_parts(self.config)
        gate=p["C1_Compuerta"].s
        base=p["Base"].s
        latch=p["C1_Cerrojo"].s
        # First try sliding the latch alone, with the gate still upright.
        probe=latch.translate(cq.Vector(-8,0,0))
        self.assertGreater(probe.intersect(gate).Volume(),20.0)
        # After lowering the gate, the bolt can travel unobstructed.
        released=gate.translate(cq.Vector(0,0,-12))
        self.assertLess(probe.intersect(released).Volume(),.001)
        self.assertLess(base.intersect(released).Volume(),.001)
        for distance in (0,4,8,12,16,20):
            moved=latch.translate(cq.Vector(-distance,0,0))
            self.assertLess(moved.intersect(released).Volume(),.001)

    def test_all_four_sides_support_independent_linear_gates(self):
        cfg=replace(self.config,
                    mecanismo_derecha="secuencia",
                    mecanismo_trasera="secuencia",
                    mecanismo_izquierda="secuencia").validate()
        parts=self.builder.get_parts(cfg)
        self.assertEqual(len(parts),17)
        self.assertEqual(len(parts["Base"].s.Solids()),1)
        for i in range(1,5):
            with self.subTest(face=i):
                self.assertIn("C%d_Compuerta"%i,parts)
                self.assertIn("C%d_SeguroCompuerta"%i,parts)
                self.assertNotIn("C%d_Rueda"%i,parts)
                for suffix in ("Compuerta","SeguroCompuerta"):
                    shape=parts["C%d_%s"%(i,suffix)].s
                    self.assertTrue(shape.isValid())
                    self.assertEqual(len(shape.Solids()),1)
                    self.assertLess(
                        parts["Base"].s.intersect(shape).Volume(),.001)
        for name in ("Tapa_Dial","Tapa_Leva","Tapa_Retenedor"):
            self.assertIn(name,parts)


if __name__=="__main__":
    unittest.main()
