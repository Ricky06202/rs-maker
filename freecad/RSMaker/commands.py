"""RS Maker Workbench toolbar commands; old command IDs remain available."""
import os
import FreeCADGui as Gui
from .init_gui import ROOT

ICON_DIR = os.path.join(ROOT, "Resources", "Icons")


def _selection():
    from .project import get_project_from_selection
    from .relief import project_from_selection
    puzzle = get_project_from_selection()
    return ("puzzle", puzzle) if puzzle else ("nameforge", project_from_selection())


class Create:
    def GetResources(self):
        return dict(Pixmap=os.path.join(ICON_DIR, "new.svg"),
                    MenuText="Crear…",
                    ToolTip="Elegir qué crear: caja puzzle o NameForge")

    def IsActive(self):
        return True

    def Activated(self):
        from .catalog import show_catalog
        show_catalog()


class NewPuzzle:
    """Backward compatible command ID from RS Maker 0.3."""
    def GetResources(self):
        return dict(Pixmap=os.path.join(ICON_DIR, "new.svg"),
                    MenuText="Nueva caja puzzle",
                    ToolTip="Crear caja puzzle sorpresa")

    def IsActive(self):
        return True

    def Activated(self):
        from .panel import show_dialog
        show_dialog()


class EditProject:
    def GetResources(self):
        return dict(Pixmap=os.path.join(ICON_DIR, "edit.svg"),
                    MenuText="Editar creación",
                    ToolTip="Selecciona una creación o una pieza y cambia sus parámetros")

    def IsActive(self):
        return _selection()[1] is not None

    def Activated(self):
        kind, root = _selection()
        if root is None:
            return
        if kind == "puzzle":
            from .panel import show_dialog
        else:
            from .relief import show_dialog
        show_dialog(root)


class ExportProject:
    def GetResources(self):
        return dict(Pixmap=os.path.join(ICON_DIR, "print.svg"),
                    MenuText="Exportar STL",
                    ToolTip="Exporta el sólido NameForge o las piezas puzzle")

    def IsActive(self):
        return _selection()[1] is not None

    def Activated(self):
        _, root = _selection()
        if root:
            from .panel import export_parts
            export_parts(root)


class ExportPlates:
    def GetResources(self):
        return dict(Pixmap=os.path.join(ICON_DIR, "print.svg"),
                    MenuText="Exportar platos STL",
                    ToolTip="Distribuir piezas puzzle en platos de impresión automáticamente")

    def IsActive(self):
        kind,root=_selection()
        return kind=="puzzle" and root is not None

    def Activated(self):
        kind,root=_selection()
        if kind=="puzzle" and root is not None:
            from .panel import export_print_plates
            export_print_plates(root)


Gui.addCommand("RSMaker_Create", Create())
Gui.addCommand("RSMaker_New", NewPuzzle())
Gui.addCommand("RSMaker_Edit", EditProject())
Gui.addCommand("RSMaker_Export", ExportProject())
Gui.addCommand("RSMaker_ExportPlates", ExportPlates())
