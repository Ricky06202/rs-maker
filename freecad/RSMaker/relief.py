"""RS Maker / NameForge: configurable solid plaque or hollow LED lightbox.

Requires FreeCAD 1.x and its bundled Draft and importSVG modules.
Lamp mode generates separate flat-printable front and open-back frame.
"""
import os
import tempfile
from dataclasses import dataclass

try:
    from PySide import QtWidgets
except ImportError:
    from PySide2 import QtWidgets


@dataclass(frozen=True)
class ReliefConfig:
    svg_path: str = ""
    font_path: str = ""
    text: str = "NOMBRE"
    width: float = 160.0
    height: float = 170.0
    depth: float = 12.0
    artwork_relief: float = 2.4
    text_relief: float = 1.6
    text_size: float = 19.0
    margin: float = 6.0
    lamp_mode: bool = False

    def validate(self):
        if not 30 <= self.width <= 430 or not 40 <= self.height <= 430:
            raise ValueError("Ancho: 30–430 mm; alto: 40–430 mm.")
        if not 2 <= self.depth <= 100:
            raise ValueError("La profundidad total debe ser de 2–100 mm.")
        if self.lamp_mode and self.depth < 9:
            raise ValueError("La lámpara necesita 9 mm o más de profundidad (2 mm de frente y cavidad LED).")
        if not 0.4 <= self.artwork_relief <= 15 or not 0.4 <= self.text_relief <= 15:
            raise ValueError("El relieve debe medir de 0.4 a 15 mm.")
        if not 4 <= self.text_size <= 80 or not 2 <= self.margin <= 25:
            raise ValueError("Tamaño de fuente o margen fuera de rango.")
        if self.width <= 2 * self.margin + 5 or self.height <= 3 * self.margin + 18:
            raise ValueError("Reduce el margen o aumenta las dimensiones.")
        if not self.text.strip() or len(self.text) > 80 or "\n" in self.text:
            raise ValueError("Escribe un nombre de una línea (1–80 caracteres).")
        if not self.svg_path.lower().endswith(".svg"):
            raise ValueError("Selecciona una ilustración SVG.")
        if not self.font_path.lower().endswith((".ttf", ".otf")):
            raise ValueError("Selecciona una fuente .ttf o .otf.")
        if not os.path.isfile(self.font_path):
            raise ValueError("No se encuentra el archivo de la tipografía.")
        return self


FIELDS = ("width", "height", "depth", "artwork_relief", "text_relief",
          "text_size", "margin")
DISPLAY = {"width":"Ancho de la caja", "height":"Alto de la caja",
           "depth":"Profundidad total", "artwork_relief":"Relieve del dibujo",
           "text_relief":"Relieve del nombre", "text_size":"Altura del nombre",
           "margin":"Margen"}
SCHEMA = 2
LAMP_FRONT = 2.0  # flat, printable translucent front plate (mm)
LAMP_WALL = 3.0   # adhesive frame width (mm)


def _svg_xml(cfg, previous=None, previous_path=None):
    if previous is not None and previous_path == cfg.svg_path:
        # Embedded copy guarantees reproducibility even if source was moved.
        return previous
    if not os.path.isfile(cfg.svg_path):
        raise ValueError("No se encuentra el SVG: " + cfg.svg_path)
    if os.path.getsize(cfg.svg_path) > 2_000_000:
        raise ValueError("SVG demasiado grande (máximo 2 MB).")
    with open(cfg.svg_path, "rb") as handle:
        data = handle.read()
    if b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
        raise ValueError("Exporta el SVG sin entidades externas ni DOCTYPE.")
    return data.decode("utf-8-sig")


def _faces(shape):
    import Part
    if shape.isNull():
        return []
    if shape.Faces:
        return [face.copy() for face in shape.Faces if face.Area > 1e-5]
    wires = [wire for wire in shape.Wires if wire.isClosed()]
    if not wires:
        return []
    # Bullseye honors holes in letters such as A, O, B and nested SVG paths.
    try:
        face_shape = Part.makeFace(wires, "Part::FaceMakerBullseye")
    except Exception:
        if len(wires) != 1:
            raise ValueError("SVG/fuente con huecos ambiguos: convierte los trazos a rutas cerradas.")
        face_shape = Part.Face(wires[0])
    return [face.copy() for face in face_shape.Faces if face.Area > 1e-5]


def _fit(shape, width, height, center_x, center_y, z):
    import FreeCAD as App
    b = shape.BoundBox
    if b.XLength < 1e-5 or b.YLength < 1e-5:
        raise ValueError("El SVG o texto no tiene una región visible válida.")
    ratio = min(width / b.XLength, height / b.YLength)
    result = shape.copy()
    result.scale(ratio)
    result.translate(App.Vector(center_x - ratio * (b.XMin + b.XMax) / 2,
                                center_y - ratio * (b.YMin + b.YMax) / 2,
                                z - ratio * b.ZMin))
    return result


def _lamp_frame(cfg):
    """Open-back, open-front frame: no unsupported wide roof to bridge.

    Each part is printed separately flat on the bed. The front face is later
    glued to the frame's 3-mm ledge; cable exits via a rear-edge notch.
    """
    import Part
    import FreeCAD as App

    h = cfg.depth - LAMP_FRONT
    w = LAMP_WALL
    outer = Part.makeBox(cfg.width, cfg.height, h)
    inner = Part.makeBox(cfg.width - 2 * w, cfg.height - 2 * w,
                         h + 2, App.Vector(w, w, -1))
    ring = outer.cut(inner)
    notch = Part.makeBox(5.5, w + 2, 3.0,
                         App.Vector(cfg.width / 2 - 2.75, -1, 0))
    ring = ring.cut(notch)
    try:
        ring = ring.removeSplitter()
    except Exception:
        pass
    if not ring.isValid() or len(ring.Solids) != 1:
        raise ValueError("No se pudo generar un marco de lámpara imprimible.")
    return ring


def make_parts(cfg, svg_xml):
    """Return named valid solids for either the box or a two-piece lamp."""
    import FreeCAD as App
    import Part
    import Draft
    import importSVG

    old = App.ActiveDocument
    tempdoc = App.newDocument("RSNameForgeBuild")
    filename = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".svg", delete=False, mode="w", encoding="utf-8") as stream:
            stream.write(svg_xml)
            filename = stream.name
        importSVG.insert(filename, tempdoc.Name)
        tempdoc.recompute()
        source = []
        for obj in tempdoc.Objects:
            if hasattr(obj, "Shape") and not obj.Shape.isNull():
                faces = _faces(obj.Shape)
                if faces:
                    source.extend(faces)
                if len(source) > 350:
                    raise ValueError("SVG con demasiadas regiones: simplifica el dibujo (máximo 350).")
        if not source:
            raise ValueError("El SVG no contiene áreas cerradas. Convierte los trazos a contornos rellenos.")
        artwork = Part.makeCompound(source)
        caption_band = max(cfg.text_size + 2 * cfg.margin, cfg.height * 0.25)
        picture_height = cfg.height - caption_band - 2 * cfg.margin
        if picture_height < 5:
            raise ValueError("La caja es demasiado baja para el dibujo y el nombre.")
        artwork = _fit(artwork, cfg.width - 2 * cfg.margin, picture_height,
                       cfg.width / 2, caption_band + cfg.margin + picture_height / 2,
                       cfg.depth)
        extruded = []
        for face in _faces(artwork):
            solid = face.extrude(App.Vector(0, 0, cfg.artwork_relief))
            if not solid.Solids:
                raise ValueError("Una región SVG no se puede extruir como sólido.")
            extruded.append(solid)

        # Create a ShapeString inside the same temporary document.
        caption = Draft.make_shapestring(cfg.text, cfg.font_path, cfg.text_size, 0)
        tempdoc.recompute()
        caption_shape = caption.Shape
        if caption_shape.isNull():
            raise ValueError("La tipografía no pudo generar contornos.")
        caption_shape = _fit(caption_shape, cfg.width - 2 * cfg.margin,
                             min(cfg.text_size, caption_band - cfg.margin),
                             cfg.width / 2, caption_band / 2, cfg.depth)
        caption_solids = []
        for face in _faces(caption_shape):
            solid = face.extrude(App.Vector(0, 0, cfg.text_relief))
            if solid.Solids:
                caption_solids.append(solid)
        if not caption_solids:
            raise ValueError("La fuente no produjo letras extruibles.")

        # Solid box stays filled. Lamp front is separate, flat-backed
        # and assembled at the top of the open-ended frame (Z = depth - 2).
        face_z = cfg.depth - LAMP_FRONT if cfg.lamp_mode else 0.0
        face_depth = LAMP_FRONT if cfg.lamp_mode else cfg.depth
        joined = Part.makeBox(cfg.width, cfg.height, face_depth,
                              App.Vector(0, 0, face_z))
        for raised in extruded + caption_solids:
            joined = joined.fuse(raised)
        try:
            joined = joined.removeSplitter()
        except Exception:
            pass
        if not joined.isValid() or len(joined.Solids) != 1:
            raise ValueError("No resultó un sólido único: prueba un SVG con regiones cerradas simples.")
        if cfg.lamp_mode:
            return [("nameforge_frente", "Frente translúcido · imprimir plano", joined,
                     (0.82, 0.93, 1.0)),
                    ("nameforge_marco", "Marco hueco · salida de cable", _lamp_frame(cfg),
                     (0.32, 0.42, 0.53))]
        return [("nameforge_solido", "Caja maciza · base plana", joined,
                 (0.61, 0.80, 0.95))]
    finally:
        if filename and os.path.isfile(filename):
            os.remove(filename)
        App.closeDocument(tempdoc.Name)
        if old:
            App.setActiveDocument(old.Name)


def is_project(obj):
    return hasattr(obj, "RSMakerReliefSchema") and obj.RSMakerReliefSchema in (1, SCHEMA)


def project_from_selection():
    import FreeCADGui as Gui
    for obj in Gui.Selection.getSelection():
        if is_project(obj):
            return obj
        for parent in getattr(obj, "InList", []):
            if is_project(parent):
                return parent
    return None


def from_project(root):
    values = {name:float(getattr(root, name.title().replace("_", "")).Value)
              for name in FIELDS}
    return ReliefConfig(svg_path=root.SVGPath, font_path=root.FontPath,
                        text=root.Caption, lamp_mode=bool(getattr(root, "LampMode", False)),
                        **values)


def _properties(root, cfg, svg_xml, create=False):
    if create:
        root.addProperty("App::PropertyInteger", "RSMakerReliefSchema", "RS Maker")
        root.addProperty("App::PropertyString", "SVGPath", "Origen")
        root.addProperty("App::PropertyString", "SVGData", "Origen")
        root.addProperty("App::PropertyString", "FontPath", "Origen")
        root.addProperty("App::PropertyString", "Caption", "Texto")
        for name in FIELDS:
            root.addProperty("App::PropertyLength", name.title().replace("_", ""), "Dimensiones (mm)")
    if not hasattr(root, "LampMode"):
        root.addProperty("App::PropertyBool", "LampMode", "Modo de fabricación")
    root.RSMakerReliefSchema = SCHEMA
    root.LampMode = cfg.lamp_mode
    root.SVGPath = cfg.svg_path
    root.SVGData = svg_xml
    root.FontPath = cfg.font_path
    root.Caption = cfg.text
    for name in FIELDS:
        setattr(root, name.title().replace("_", ""), getattr(cfg, name))


def save_project(cfg, root=None):
    import FreeCAD as App
    cfg.validate()
    xml = _svg_xml(cfg, getattr(root,"SVGData",None), getattr(root,"SVGPath",None))
    parts = make_parts(cfg, xml)  # no mutation of the user's document on failure
    doc = root.Document if root else (App.ActiveDocument or App.newDocument("RSMaker"))
    doc.openTransaction("RS Maker: crear/regenerar NameForge")
    try:
        create = root is None
        if create:
            root = doc.addObject("App::DocumentObjectGroup", "RS_NameForge")
        old = {obj.RSMakerPartKey: obj for obj in root.Group
               if hasattr(obj, "RSMakerPartKey")}
        needed = set()
        for key, label, shape, color in parts:
            needed.add(key)
            part = old.get(key)
            if part is None:
                part = doc.addObject("Part::Feature", "RS_" + key)
                part.addProperty("App::PropertyString", "RSMakerPartKey", "RS Maker")
                part.RSMakerPartKey = key
                root.addObject(part)
            part.Label = label
            part.Shape = shape
            part.ViewObject.ShapeColor = color
        for key, obsolete in old.items():
            if key not in needed:
                doc.removeObject(obsolete.Name)
        _properties(root, cfg, xml, create)
        root.Label = "RS Maker | NameForge | " + cfg.text + (" · Lámpara" if cfg.lamp_mode else " · Maciza")
        doc.recompute()
        doc.commitTransaction()
    except Exception:
        doc.abortTransaction()
        raise
    if App.GuiUp:
        import FreeCADGui as Gui
        Gui.activeDocument().activeView().viewAxonometric()
        Gui.activeDocument().activeView().fitAll()
    return root


class ReliefDialog(QtWidgets.QDialog):
    def __init__(self, root=None, parent=None):
        super().__init__(parent)
        self.root = root
        self.setWindowTitle("RS Maker · NameForge · " + ("Editar" if root else "Crear"))
        self.setMinimumWidth(490)
        layout = QtWidgets.QVBoxLayout(self)
        title = QtWidgets.QLabel("Figura SVG + nombre · Caja o lámpara")
        title.setStyleSheet("font-size: 17px; font-weight: 600;")
        layout.addWidget(title)
        note = QtWidgets.QLabel("Elige el modo con un check: caja maciza o lámpara "
                                "con frente y marco hueco separados para imprimir planos.")
        note.setWordWrap(True)
        layout.addWidget(note)
        form = QtWidgets.QFormLayout()
        layout.addLayout(form)
        self.svg = QtWidgets.QLineEdit()
        self.font = QtWidgets.QLineEdit()
        self.caption = QtWidgets.QLineEdit()
        self.caption.setPlaceholderText("Ej.: RODRIGO")
        for name, target, file_filter in (
                ("Archivo SVG", self.svg, "Imágenes SVG (*.svg)"),
                ("Tipografía", self.font, "Fuentes (*.ttf *.otf)")):
            row = QtWidgets.QHBoxLayout()
            row.addWidget(target)
            browse = QtWidgets.QPushButton("Elegir…")
            browse.clicked.connect(lambda checked=False, t=target, f=file_filter:
                                   self._browse(t, f))
            row.addWidget(browse)
            form.addRow(name, row)
        form.addRow("Nombre", self.caption)
        self.lamp_mode = QtWidgets.QCheckBox("Lámpara (hueca, 2 piezas)")
        self.lamp_mode.setToolTip("Activado: frente de 2 mm + marco de 3 mm sin techo, "
                                  "cavidad para LED y salida para cable. "
                                  "Desactivado: caja 100 % maciza.")
        form.addRow("Modo", self.lamp_mode)
        self.sizes = {}
        defaults = ReliefConfig()
        for name in FIELDS:
            field = QtWidgets.QDoubleSpinBox()
            field.setSuffix(" mm")
            field.setDecimals(2)
            field.setRange(0.1, 500)
            field.setValue(getattr(defaults, name))
            field.setSingleStep(0.5)
            self.sizes[name] = field
            form.addRow(DISPLAY[name], field)
        self.feedback = QtWidgets.QLabel()
        self.feedback.setWordWrap(True)
        layout.addWidget(self.feedback)
        self.lamp_mode.toggled.connect(self._mode_changed)
        self._mode_changed()
        buttons = QtWidgets.QDialogButtonBox()
        self.create_button = buttons.addButton("Regenerar" if root else "Crear sólido",
                                               QtWidgets.QDialogButtonBox.AcceptRole)
        buttons.addButton("Cancelar", QtWidgets.QDialogButtonBox.RejectRole)
        buttons.rejected.connect(self.reject)
        self.create_button.clicked.connect(self.generate)
        layout.addWidget(buttons)
        if root:
            cfg = from_project(root)
            self.svg.setText(cfg.svg_path)
            self.font.setText(cfg.font_path)
            self.caption.setText(cfg.text)
            for name, field in self.sizes.items():
                field.setValue(getattr(cfg, name))
            self.lamp_mode.setChecked(cfg.lamp_mode)

    def _mode_changed(self, *args):
        if self.lamp_mode.isChecked():
            self.feedback.setText("Lámpara: frente de 2 mm + marco hueco de 3 mm "
                                  "con salida trasera para cable. Imprime las dos piezas "
                                  "sobre caras planas y une el frente al marco. "
                                  "Utiliza filamento translúcido en el frente.")
            self.create_button.setText("Regenerar" if self.root else "Crear lámpara") if hasattr(self, "create_button") else None
        else:
            self.feedback.setText("Caja: bloque completamente macizo, "
                                  "cara inferior plana Z=0, texto y SVG en relieve.")
            self.create_button.setText("Regenerar" if self.root else "Crear caja") if hasattr(self, "create_button") else None

    def _browse(self, target, file_filter):
        chosen, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Seleccionar archivo",
                                                          target.text(), file_filter)
        if chosen:
            target.setText(chosen)

    def generate(self):
        cfg = ReliefConfig(svg_path=self.svg.text().strip(),
                           font_path=self.font.text().strip(),
                           text=self.caption.text().strip(),
                           lamp_mode=self.lamp_mode.isChecked(),
                           **{name:field.value() for name,field in self.sizes.items()})
        try:
            self.root = save_project(cfg, self.root)
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "No se pudo generar NameForge", str(exc))
            return
        self.accept()


def show_dialog(root=None):
    import FreeCADGui as Gui
    ReliefDialog(root, Gui.getMainWindow()).exec()
