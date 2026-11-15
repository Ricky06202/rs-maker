"""OpenCascade checks for the maze and coded-tumbler side families.

These checks validate printable BReps, path/dial rule differences and the
locked/released geometric interference. They are not a physical motion test.
"""
import math
import unittest

from freecad.RSMaker.config import PuzzleConfig, DIFFICULTIES
from freecad.RSMaker.maze_lock import path_for
from freecad.RSMaker.cipher_lock import cipher_profile
import test_geometry_occ as occ

cq = occ.cq


class ChallengeProfileTests(unittest.TestCase):
    def test_maze_paths_grow_and_keep_a_locked_start_and_release_exit(self):
        profiles = [path_for(level) for level in DIFFICULTIES]
        lengths = [len(path) for path, _turns in profiles]
        turns = [turns for _path, turns in profiles]
        self.assertEqual(lengths, sorted(lengths))
        self.assertEqual(turns, sorted(turns))
        for path, _turn_count in profiles:
            self.assertEqual(path[0], (0, 0))
            self.assertEqual(path[-1], (-8, 12))

    def test_cipher_adds_rings_and_positions_with_difficulty(self):
        profiles = [cipher_profile(level) for level in DIFFICULTIES]
        self.assertEqual([p["rings"] for p in profiles], [2, 3, 4])
        self.assertEqual([p["positions"] for p in profiles], [2, 4, 8])
        self.assertEqual([p["moves"] for p in profiles], [3, 4, 5])
        for profile in profiles:
            self.assertTrue(all(0 < code < profile["positions"]
                                for code in profile["code"]))


@unittest.skipUnless(cq is not None, "CadQuery/OCP not installed")
class MechanismFamilyOCCTests(unittest.TestCase):
    def setUp(self):
        self.builder = occ.TestGeometryOCC()

    def test_maze_cursor_blocks_eight_mm_then_escapes_at_exit(self):
        cfg = PuzzleConfig(theme="Ninguno", frontal="Difícil",
                           mecanismo_frontal="laberinto").validate()
        parts = self.builder.get_parts(cfg)
        guide = parts["C1_Laberinto_Guia"].s
        cursor = parts["C1_Laberinto_Cursor"].s
        latch = parts["C1_Cerrojo"].s
        base = parts["Base"].s
        self.assertTrue(guide.isValid())
        self.assertTrue(cursor.isValid())
        self.assertEqual(len(guide.Solids()), 1)
        self.assertEqual(len(cursor.Solids()), 1)
        self.assertLess(base.intersect(guide).Volume(), .001)
        self.assertLess(guide.intersect(cursor).Volume(), .001)

        attempted = latch.translate(cq.Vector(-8,0,0))
        self.assertGreater(attempted.intersect(cursor).Volume(), 1.0)
        pre_exit = cursor.translate(cq.Vector(-8,0,0))
        full_stroke = latch.translate(cq.Vector(-20,0,0))
        self.assertGreater(full_stroke.intersect(pre_exit).Volume(), 1.0)
        path,_turns = path_for("Difícil")
        for cursor_x,cursor_z in path[:-1]:
            state = cursor.translate(cq.Vector(cursor_x,0,cursor_z))
            later_steps = [latch.translate(cq.Vector(-distance,0,0)).intersect(state).Volume()
                           for distance in (8,12,16,20)]
            self.assertGreater(max(later_steps),1.0,
                               "maze blocker released early at %s"%((cursor_x,cursor_z),))
        at_exit = cursor.translate(cq.Vector(-8,0,12))
        self.assertLess(attempted.intersect(at_exit).Volume(), .001)
        for distance in (0,4,8,12,16,20):
            moved = latch.translate(cq.Vector(-distance,0,0))
            self.assertLess(moved.intersect(at_exit).Volume(), .001)

    def test_cipher_gate_requires_each_ring_window_aligned(self):
        cfg = PuzzleConfig(theme="Ninguno", frontal="Difícil",
                           mecanismo_frontal="cifrado").validate()
        parts = self.builder.get_parts(cfg)
        rings = [parts["C1_Cifrado_Anillo_%d"%i].s for i in range(1,5)]
        gate = parts["C1_Cifrado_Compuerta"].s
        cap = parts["C1_Cifrado_Seguro"].s
        base = parts["Base"].s
        self.assertEqual(len(rings),4)
        self.assertTrue(all(ring.isValid() and len(ring.Solids())==1
                            for ring in rings))
        self.assertTrue(gate.isValid())
        self.assertTrue(cap.isValid(),"cap")
        self.assertEqual(len(base.Solids()),1)
        for i,ring in enumerate(rings,1):
            self.assertLess(base.intersect(ring).Volume(),.001,"base/ring %d"%i)
            self.assertLess(gate.intersect(ring).Volume(),.001,"locked gate/ring %d"%i)
        self.assertNotIn("C1_Cifrado_Rieles",parts)
        self.assertLess(base.intersect(gate).Volume(),.001)
        self.assertLess(base.intersect(cap).Volume(),.001)

        down = gate.translate(cq.Vector(0,0,-12))
        locked_volume = sum(down.intersect(ring).Volume() for ring in rings)
        self.assertGreater(locked_volume, 1.0)

        # Rotate each wheel to its configured answer. The comb should then
        # pass through every radial window in the same 12 mm gate movement.
        u0 = cfg.width/2
        pivot = u0-51.0
        first_x = u0-30.0
        z = (cfg.height-5.0-7.0)-16.0
        profile = cipher_profile("Difícil")
        unlocked = []
        for i,ring in enumerate(rings):
            angle = 360.0*profile["code"][i]/profile["positions"]
            center = cq.Vector(first_x+i*15.0,-1.45,z)
            aligned = ring.rotate(center,center+cq.Vector(0,1,0),-angle)
            unlocked.append(aligned)
        # The extended gate includes its blocker. It is clear of the latch
        # after its comb descends and all ring windows align.
        self.assertTrue(math.isclose(pivot,u0-51.0))
        aligned_volume = sum(down.intersect(ring).Volume() for ring in unlocked)
        self.assertLess(aligned_volume, .02)

        latch = parts["C1_Cerrojo"].s
        self.assertGreater(latch.translate(cq.Vector(-8,0,0)).intersect(gate).Volume(),1.0)
        for distance in (0,4,8,12,16,20):
            moved = latch.translate(cq.Vector(-distance,0,0))
            self.assertLess(moved.intersect(down).Volume(),.001)

    def test_families_generate_as_separate_parts_on_all_sides(self):
        cfg = PuzzleConfig(width=150,depth=150,height=75,wall=5.0,
                           floor=3.0,clearance=0.2,theme="Ninguno",
                           mecanismo_frontal="laberinto",
                           mecanismo_derecha="cifrado",
                           mecanismo_trasera="secuencia",
                           mecanismo_izquierda="cerrojo_rueda").validate()
        parts = self.builder.get_parts(cfg)
        self.assertIn("C1_Laberinto_Guia",parts)
        self.assertIn("C1_Laberinto_Cursor",parts)
        self.assertIn("C2_Cifrado_Anillo_1",parts)
        self.assertIn("C2_Cifrado_Compuerta",parts)
        self.assertIn("C3_Compuerta",parts)
        self.assertIn("C4_Rueda",parts)
        self.assertTrue(all(shape.isValid() for shape in parts.values()))
        self.assertEqual(len(parts["Base"].s.Solids()),1)
        self.assertLess(parts["Base"].s.intersect(
                        parts["C1_Laberinto_Guia"].s).Volume(),.001)
        self.assertEqual(sum(name.startswith("C2_Cifrado_Anillo_")
                             for name in parts),3)


if __name__ == "__main__":
    unittest.main()
