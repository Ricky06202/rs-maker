"""Independent OCCT validation of RS Maker original Space/Beach boxes.

Runs with CadQuery OCP (no FreeCAD GUI). Real printed fit, hinge motion,
retention and child safety remain unverified.
"""
import unittest

from freecad.RSMaker.config import PuzzleConfig, FACES
import test_geometry_occ as occ

cq=occ.cq


@unittest.skipUnless(cq is not None,"CadQuery OCP no está instalado")
class ThemedPuzzleOCCChecks(unittest.TestCase):
    def setUp(self):
        self.builder=occ.TestGeometryOCC()

    def test_original_theme_parts_are_single_printable_solids(self):
        for collection,figure,scene,fig_key,scene_key in (
                ("Espacio","Astronauta","Cohete",
                 "Chibi_Astronauta","Escenario_Cohete"),
                ("Playa","Cangrejito","Palmeras",
                 "Chibi_Cangrejito","Escenario_Palmeras")):
            with self.subTest(collection=collection):
                cfg=PuzzleConfig(collection=collection,
                                 figure=figure,scene=scene,
                                 theme="Ninguno").validate()
                parts=self.builder.get_parts(cfg)
                self.assertEqual(len(parts),15)
                for name in ("Base","Tapa",fig_key,scene_key):
                    shape=parts[name]
                    self.assertTrue(shape.isValid(),name)
                    self.assertGreater(shape.Volume,1,name)
                    self.assertEqual(len(shape.s.Solids()),1,name)

                self.assertLess(
                    parts[fig_key].s.intersect(parts["Base"].s).Volume(),
                    1e-3,"El chibi no debe atravesar el fondo")
                self.assertLess(
                    parts[fig_key].s.intersect(parts["Tapa"].s).Volume(),
                    1e-3,"El chibi no debe atravesar la tapa")
                self.assertLess(
                    parts[scene_key].s.intersect(parts["Tapa"].s).Volume(),
                    1e-3,"Los pivotes deben caber en sus huecos")
                self.assertLess(
                    parts[scene_key].s.intersect(parts["Tapa_Dial"].s).Volume(),
                    1e-3,"La escena no puede tapar la quinta cara jugable")
                for i,face in enumerate(FACES[:4],1):
                    self.assertIn("C%d_Cerrojo"%i,parts)
                    self.assertIn("C%d_Rueda"%i,parts)
                    self.assertLess(
                        parts["Base"].s.intersect(
                            parts["C%d_Cerrojo"%i].s).Volume(),1e-3)
                    self.assertLess(
                        parts["Base"].s.intersect(
                            parts["C%d_Rueda"%i].s).Volume(),1e-3)

    def test_top_challenge_and_part_inventory_survive_theme_change(self):
        from dataclasses import replace
        old=PuzzleConfig(theme="Ninguno")
        for collection,figure,scene in (
                ("Espacio","Astronauta","Cohete"),
                ("Playa","Cangrejito","Palmeras")):
            with self.subTest(collection=collection):
                changed=replace(old,collection=collection,
                                figure=figure,scene=scene).validate()
                self.assertEqual(changed.difficulties,old.difficulties)
                parts=self.builder.get_parts(changed)
                self.assertIn("Tapa_Dial",parts)
                self.assertIn("Tapa_Leva",parts)
                self.assertIn("Tapa_Retenedor",parts)
                self.assertEqual(len(
                    [k for k in parts if k.endswith("_Cerrojo")]),4)


if __name__=="__main__":
    unittest.main()
