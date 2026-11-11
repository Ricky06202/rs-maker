"""Independent checks for the original food collection, geometry and settings.

No live FreeCAD GUI or physical tolerances are tested here.
"""
import sys
import unittest
from dataclasses import replace
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from freecad.RSMaker.config import PuzzleConfig
from freecad.RSMaker.collection import restaurant_socket_centers
import test_geometry_occ as geometry_tests
cq = geometry_tests.cq


class CollectionConfigTests(unittest.TestCase):
    def test_collection_requires_valid_combination(self):
        c = PuzzleConfig(collection="Comida", figure="Hamburguesita",
                         scene="Restaurante", theme="Ninguno").validate()
        self.assertEqual(c.figure_height, 30)
        self.assertEqual(c.collection, "Comida")
        for bad in (dict(collection="Comida", figure="Hamburguesita", theme="Huellas"),
                    dict(figure="Hamburguesita"), dict(scene="Restaurante"),
                    dict(collection="Espacio"), dict(figure_height=42)):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                PuzzleConfig(**bad).validate()

    def test_collection_does_not_change_five_challenges(self):
        a = PuzzleConfig()
        b = replace(a, collection="Comida", scene="Restaurante", theme="Ninguno",
                    figure="Hamburguesita")
        self.assertEqual(a.difficulties, b.difficulties)
        self.assertEqual(len(b.difficulties), 5)
        self.assertEqual(len(restaurant_socket_centers(b)), 2)


@unittest.skipUnless(cq is not None, "CadQuery unavailable")
class FoodGeometryTests(unittest.TestCase):
    def setUp(self):
        self.builder=geometry_tests.TestGeometryOCC()
        self.food=PuzzleConfig(collection="Comida",scene="Restaurante",
                               figure="Hamburguesita",theme="Ninguno").validate()

    def test_original_figure_and_restaurant_are_valid_solids(self):
        p=self.builder.get_parts(self.food)
        self.assertEqual(len(p),15)
        for name in ("Chibi_Hamburguesita","Escenario_Restaurante","Base","Tapa"):
            with self.subTest(name=name):
                self.assertTrue(p[name].isValid(),name)
                self.assertGreater(p[name].Volume,1,name)
                self.assertEqual(len(p[name].s.Solids()),1,name)
        # Figure is not glued to the box and scene pins are inside clearance holes.
        self.assertLess(p['Chibi_Hamburguesita'].s.intersect(p['Base'].s).Volume(),1e-3)
        self.assertLess(p['Chibi_Hamburguesita'].s.intersect(p['Tapa'].s).Volume(),1e-3)
        self.assertLess(p['Escenario_Restaurante'].s.intersect(p['Tapa'].s).Volume(),1e-3)
        self.assertLess(p['Escenario_Restaurante'].s.intersect(p['Tapa_Dial'].s).Volume(),1e-3)

    def test_side_reliefs_really_change_base_not_five_locks(self):
        a=self.builder.get_parts(PuzzleConfig(theme='Ninguno'))
        b=self.builder.get_parts(replace(self.food,figure="Ninguna",scene="Ninguno"))
        self.assertGreater(b['Base'].Volume,a['Base'].Volume+300)
        self.assertEqual(set(a),set(b))
        for index in range(1,5):
            self.assertLess(b['Base'].s.intersect(b[f'C{index}_Cerrojo'].s).Volume(),1e-3)
            self.assertLess(b['Base'].s.intersect(b[f'C{index}_Rueda'].s).Volume(),1e-3)

    def test_independent_chibi_size_and_expression(self):
        small=self.builder.get_parts(replace(self.food,figure_height=25.0,expression="Feliz"))
        big=self.builder.get_parts(replace(self.food,figure_height=40.0,expression="Sorprendida"))
        self.assertGreater(big['Chibi_Hamburguesita'].Volume,
                           small['Chibi_Hamburguesita'].Volume*2.5)
        self.assertTrue(big['Chibi_Hamburguesita'].isValid())

    def test_original_unmodified_mechanism_still_present(self):
        p=self.builder.get_parts(self.food)
        for index in range(1,5):
            self.assertIn(f'C{index}_Cerrojo',p)
            self.assertIn(f'C{index}_Rueda',p)
        self.assertIn('Tapa_Dial',p)
        self.assertIn('Tapa_Leva',p)

if __name__ == '__main__':
    unittest.main()
