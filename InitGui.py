"""FreeCAD entry point for the RS Maker Python workbench."""
import os
import sys

_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
from freecad.RSMaker import init_gui  # noqa: F401,E402
