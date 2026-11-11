"""Simple, extensible create catalog. One entry point for all RS Maker generators."""
try:
    from PySide import QtWidgets
except ImportError:
    from PySide2 import QtWidgets


class CreateCatalog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.choice = None
        self.setWindowTitle("RS Maker · Crear")
        self.setMinimumWidth(470)
        layout = QtWidgets.QVBoxLayout(self)
        heading = QtWidgets.QLabel("¿Qué quieres crear?")
        heading.setStyleSheet("font-size: 19px; font-weight: 600;")
        layout.addWidget(heading)
        hint = QtWidgets.QLabel("Selecciona un generador. Cada herramienta conserva sus propias opciones.")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self._option(layout, "Caja puzzle sorpresa",
                     "Cinco caras jugables · muñeco y decoración · prototipo experimental",
                     "puzzle")
        self._option(layout, "NameForge · Figura SVG + nombre",
                     "Caja maciza de base plana · ancho, alto y profundidad · relieve editable",
                     "nameforge")
        cancel = QtWidgets.QPushButton("Cancelar")
        cancel.clicked.connect(self.reject)
        layout.addWidget(cancel)

    def _option(self, layout, title, subtitle, key):
        button = QtWidgets.QPushButton(title + "\n" + subtitle)
        button.setMinimumHeight(72)
        button.setStyleSheet("QPushButton { text-align: left; padding: 12px; }")
        button.setToolTip(subtitle)
        button.clicked.connect(lambda checked=False: self._choose(key))
        layout.addWidget(button)

    def _choose(self, key):
        self.choice = key
        self.accept()


def show_catalog():
    import FreeCADGui as Gui
    catalog = CreateCatalog(Gui.getMainWindow())
    if catalog.exec() != QtWidgets.QDialog.Accepted:
        return
    if catalog.choice == "puzzle":
        from .panel import show_dialog
        show_dialog()
    elif catalog.choice == "nameforge":
        from .relief import show_dialog
        show_dialog()
