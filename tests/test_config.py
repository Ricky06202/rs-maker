"""Pure Python tests: 5 mandatory stations and independent difficulty settings."""
import itertools
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from freecad.RSMaker.config import (PuzzleConfig,FACES,DIFFICULTIES,DIAL_MARKS,
                                    PUZZLES,can_open)

class TestConfig(unittest.TestCase):
    def test_five_mandatory_faces(self):
        cfg=PuzzleConfig().validate()
        self.assertEqual(FACES,("Frontal","Derecha","Trasera","Izquierda","Tapa"))
        self.assertEqual(len(cfg.difficulties),5)
        self.assertEqual(cfg.face_difficulty("Frontal"),"Fácil")
        self.assertEqual(cfg.face_difficulty("Tapa"),"Medio")

    def test_one_face_changes_only_itself(self):
        old=PuzzleConfig()
        new=PuzzleConfig(derecha="Difícil").validate()
        self.assertEqual(old.difficulties[:1],new.difficulties[:1])
        self.assertEqual(old.difficulties[2:],new.difficulties[2:])
        self.assertEqual(new.face_difficulty("Derecha"),"Difícil")
        self.assertEqual(DIAL_MARKS[new.derecha],8)

    def test_and_logic_for_every_state(self):
        for state in itertools.product((False,True), repeat=5):
            with self.subTest(state=state):
                self.assertEqual(can_open(state[:4],state[4]),all(state))
        with self.assertRaises(ValueError): can_open([True,True],True)

    def test_unimplemented_families_not_claimed(self):
        self.assertTrue(PUZZLES['cerrojo_rueda']['implemented'])
        self.assertFalse(PUZZLES['laberinto']['implemented'])
        self.assertTrue(PUZZLES['secuencia']['implemented'])

    def test_mixed_mechanisms_keep_five_independent_challenges(self):
        cfg=PuzzleConfig(mecanismo_frontal="secuencia",
                         mecanismo_derecha="cerrojo_rueda").validate()
        self.assertEqual(cfg.face_mechanism("Frontal"),"secuencia")
        self.assertEqual(cfg.face_mechanism("Derecha"),"cerrojo_rueda")
        self.assertEqual(len(cfg.difficulties),5)
        for bad in ("laberinto","cifrado","inexistente"):
            with self.subTest(bad=bad),self.assertRaisesRegex(
                    ValueError,"Mecanismo lateral"):
                PuzzleConfig(mecanismo_frontal=bad).validate()
        with self.assertRaisesRegex(ValueError,"quinto"):
            cfg.face_mechanism("Tapa")

    def test_invalid_dimension_and_all_five_difficulties(self):
        for arg in ({"width":149},{"depth":149},{"clearance":.1},
                    {"tapa":"Ultra"},{"frontal":None},{"floor":7}):
            with self.subTest(arg=arg), self.assertRaises(ValueError):
                PuzzleConfig(**arg).validate()

    def test_useful_prize_interior(self):
        w,d,h=PuzzleConfig().prize_interior
        self.assertGreater(w,100)
        self.assertGreater(d,100)
        self.assertGreater(h,50)

if __name__ == '__main__':unittest.main()
