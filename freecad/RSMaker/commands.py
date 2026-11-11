"""RS Maker Workbench toolbar commands."""
import os
import FreeCADGui as Gui
from .init_gui import ROOT

ICON_DIR = os.path.join(ROOT, "Resources", "Icons")


class NewPuzzle:
    def GetResources(self):
        return dict(Pixmap=os.path.join(ICON_DIR,"new.svg"),
                    MenuText="Nueva caja puzzle",
                    ToolTip="Crea una caja puzzle sorpresa con mecanismo y decoración")

    def IsActive(self):
        return True

    def Activated(self):
        from .panel import show_dialog
        show_dialog()


class EditPuzzle:
    def GetResources(self):
        return dict(Pixmap=os.path.join(ICON_DIR,"edit.svg"),
                    MenuText="Editar caja puzzle",
                    ToolTip="Edita y regenera una caja puzzle seleccionada")

    def IsActive(self):
        from .project import get_project_from_selection
        return get_project_from_selection() is not None

    def Activated(self):
        from .project import get_project_from_selection
        from .panel import show_dialog
        root = get_project_from_selection()
        if root:
            show_dialog(root)


class ExportPuzzle:
    def GetResources(self):
        return dict(Pixmap=os.path.join(ICON_DIR,"print.svg"),
                    MenuText="Exportar piezas STL",
                    ToolTip="Exporta cada pieza sólida del proyecto seleccionado a un STL independiente")

    def IsActive(self):
        from .project import get_project_from_selection
        return get_project_from_selection() is not None

    def Activated(self):
        from .project import get_project_from_selection
        from .panel import export_parts
        root = get_project_from_selection()
        if root:
            export_parts(root)


Gui.addCommand("RSMaker_New", NewPuzzle())
Gui.addCommand("RSMaker_Edit", EditPuzzle())
Gui.addCommand("RSMaker_Export", ExportPuzzle())
