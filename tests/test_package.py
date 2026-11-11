"""Packaging smoke tests, without requiring FreeCAD to be installed."""
import runpy
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]


class PackageTests(unittest.TestCase):
    def test_freecad_workbench_entry_point_and_icons(self):
        registered = []
        fake_gui = types.ModuleType('FreeCADGui')
        fake_gui.Workbench = type('Workbench', (), {})
        fake_gui.addWorkbench = registered.append
        with patch.dict(sys.modules, {'FreeCADGui':fake_gui}):
            runpy.run_path(str(ROOT / 'InitGui.py'))
        self.assertEqual(len(registered), 1)
        workbench = registered[0]
        self.assertEqual(workbench.MenuText, 'RS Maker')
        self.assertTrue(Path(workbench.Icon).is_file(), workbench.Icon)

    def test_sample_meshes_are_watertight_when_trimesh_available(self):
        try:
            import trimesh
        except ImportError:
            self.skipTest('trimesh unavailable')
        if not all((ROOT / 'examples' / name).is_file() for name in ('Hamburguesita-v0.3.stl','Restaurante-v0.3.stl')):
            self.skipTest('Generated binary STL examples are distributed separately from source')
        for name in ('Hamburguesita-v0.3.stl','Restaurante-v0.3.stl'):
            with self.subTest(name=name):
                m=trimesh.load(ROOT / 'examples' / name,force='mesh')
                self.assertTrue(m.is_watertight)
                self.assertEqual(len(m.split(only_watertight=False)),1)

if __name__ == '__main__': unittest.main()
