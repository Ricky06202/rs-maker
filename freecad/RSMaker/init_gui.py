"""Register RS Maker as a native FreeCAD workbench."""
import os
import FreeCADGui as Gui

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
ICON = os.path.join(ROOT, "Resources", "Icons", "logo.svg")


class RSMakerWorkbench(Gui.Workbench):
    MenuText = "RS Maker"
    ToolTip = "Diseña cajas puzzle sorpresa para impresión 3D"
    Icon = ICON

    def Initialize(self):
        from . import commands  # noqa: F401 - command registration
        names = ["RSMaker_New", "RSMaker_Edit", "RSMaker_Export"]
        self.appendToolbar("RS Maker", names)
        self.appendMenu("RS Maker", names)

    def GetClassName(self):
        return "Gui::PythonWorkbench"


Gui.addWorkbench(RSMakerWorkbench())
