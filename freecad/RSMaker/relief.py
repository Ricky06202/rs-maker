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
           "depth":"Profundidad total", "artwork_relief":"Incrustación del dibujo (histórico)",
           "text_relief":"Incrustación del nombre (histórico)", "text_size":"Altura del nombre",
           "margin":"Margen"}
SCHEMA = 3
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



def _overlap_xy(first, second):
    """Cheap collision filter before costly OpenCascade boolean operations."""
    a, b = first.BoundBox, second.BoundBox
    eps = 1e-7
    return (a.XMin < b.XMax - eps and b.XMin < a.XMax - eps
            and a.YMin < b.YMax - eps and b.YMin < a.YMax - eps)


def _visible_layers(layers):
    """Flatten SVG painter order into non-overlapping coplanar color inlays.

    Newer SVG shapes obscure earlier ones. Only shapes whose XY bounds
    overlap require a boolean subtraction; sparse drawings stay inexpensive.
    """
    upper = []
    result = []
    for solid, color in reversed(layers):
        interfering = [other for other in upper if _overlap_xy(solid, other)]
        if interfering:
            import Part
            visible = solid.cut(Part.makeCompound(interfering))
        else:
            visible = solid
        if not visible.isNull() and visible.Volume > 1e-7:
            if not visible.isValid():
                raise ValueError("El SVG contiene rutas inválidas o auto-intersecciones.")
            result.append((visible, color))
        upper.append(solid)
    return result


def _svg_color(obj, index):
    """FreeCAD's SVG importer may provide per-face DiffuseColor values."""
    view = obj.ViewObject
    palette = getattr(view, "DiffuseColor", None)
    if palette and index < len(palette):
        raw = palette[index]
    else:
        raw = getattr(view, "ShapeColor", (0.3, 0.6, 0.85))
    return tuple(round(max(0.0, min(1.0, float(v))), 4) for v in raw[:3])


def make_parts(cfg, svg_xml):
    """Generate a solid plaque or lamp with a perfectly flat multi-color face.

    Every colored region and the caption occupies a recessed, non-overlapping
    volume and ends at the same Z as the background. STL export preserves the
    independent bodies; the slicer must import them as parts of one object.
    """
    import FreeCAD as App
    import Part
    import Draft
    import importSVG

    old = App.ActiveDocument
    tempdoc = App.newDocument("RSNameForgeBuild")
    filename = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".svg", delete=False,
                                         mode="w", encoding="utf-8") as stream:
            stream.write(svg_xml)
            filename = stream.name
        importSVG.insert(filename, tempdoc.Name)
        tempdoc.recompute()

        # SVG areas are not arbitrarily capped. The previous 350-region guard
        # rejected valid, printable illustrations. Import and retain colors.
        source = []
        for obj in tempdoc.Objects:
            if not hasattr(obj, "Shape") or obj.Shape.isNull():
                continue
            for index, face in enumerate(_faces(obj.Shape)):
                if face.Area > 1e-5:
                    source.append((face, _svg_color(obj, index)))
        if not source:
            raise ValueError("El SVG no contiene áreas cerradas. Convierte los trazos a contornos rellenos.")

        caption_band = max(cfg.text_size + 2 * cfg.margin, cfg.height * 0.25)
        picture_height = cfg.height - caption_band - 2 * cfg.margin
        if picture_height < 5:
            raise ValueError("La caja es demasiado baja para el dibujo y el nombre.")

        front_z = cfg.depth - LAMP_FRONT if cfg.lamp_mode else 0.0
        front_thickness = LAMP_FRONT if cfg.lamp_mode else cfg.depth
        # The face is flush; the 0.6 mm inlays preserve backing thickness.
        art_inlay = min(0.6, front_thickness - 0.6)
        text_inlay = art_inlay
        if min(art_inlay, text_inlay) < 0.1:
            raise ValueError("La profundidad no permite incrustar los colores.")

        all_faces = Part.makeCompound([face for face, _ in source])
        bb = all_faces.BoundBox
        if bb.XLength < 1e-5 or bb.YLength < 1e-5:
            raise ValueError("El SVG no tiene un contorno visible válido.")
        scale = min((cfg.width - 2 * cfg.margin) / bb.XLength,
                    picture_height / bb.YLength)
        origin_x = cfg.width / 2 - scale * (bb.XMin + bb.XMax) / 2
        origin_y = caption_band + cfg.margin + picture_height / 2 - scale * (bb.YMin + bb.YMax) / 2
        layers = []
        for face, color in source:
            transformed = face.copy()
            transformed.scale(scale)
            transformed.translate(App.Vector(origin_x, origin_y,
                                              cfg.depth - art_inlay - scale * bb.ZMin))
            extruded = transformed.extrude(App.Vector(0, 0, art_inlay))
            if not extruded.isValid() or not extruded.Solids:
                raise ValueError("Una región del SVG no se pudo convertir en sólido.")
            layers.append((extruded, color))

        caption = Draft.make_shapestring(cfg.text, cfg.font_path, cfg.text_size, 0)
        tempdoc.recompute()
        if caption.Shape.isNull():
            raise ValueError("La fuente no pudo generar contornos.")
        caption_shape = _fit(caption.Shape, cfg.width - 2 * cfg.margin,
                             min(cfg.text_size, caption_band - cfg.margin),
                             cfg.width / 2, caption_band / 2,
                             cfg.depth - text_inlay)
        for face in _faces(caption_shape):
            solid = face.extrude(App.Vector(0, 0, text_inlay))
            if solid.isValid() and solid.Solids:
                layers.append((solid, (0.1, 0.65, 0.85)))
        if len(layers) == len(source):
            raise ValueError("La fuente no produjo letras extruibles.")

        visible = _visible_layers(layers)
        if not visible:
            raise ValueError("No quedaron áreas imprimibles después de procesar el SVG.")
        cutters = Part.makeCompound([shape for shape, _ in visible])
        backing = Part.makeBox(cfg.width, cfg.height, front_thickness,
                               App.Vector(0, 0, front_z)).cut(cutters)
        if not backing.isValid() or len(backing.Solids) != 1:
            raise ValueError("No se pudo crear la base maciza con incrustaciones.")

        # Fewer FreeCAD objects: one compound per distinct filament color.
        groups = {}
        for shape, color in visible:
            groups.setdefault(color, []).append(shape)
        base_name = "nameforge_frente" if cfg.lamp_mode else "nameforge_base"
        result = [(base_name, "Base plana · color de fondo", backing,
                   (0.93, 0.93, 0.93))]
        for index, (color, shapes) in enumerate(groups.items(), 1):
            part = Part.makeCompound(shapes)
            if not part.isValid():
                raise ValueError("No se pudo agrupar el color %d." % index)
            result.append(("nameforge_color_%03d" % index,
                           "Color %d · piezas coplanares" % index, part, color))
        if cfg.lamp_mode:
            result.append(("nameforge_marco", "Marco hueco · salida de cable",
                           _lamp_frame(cfg), (0.32, 0.42, 0.53)))
        return result
    finally:
        if filename and os.path.isfile(filename):
            os.remove(filename)
        App.closeDocument(tempdoc.Name)
        if old:
            App.setActiveDocument(old.Name)


def is_project(obj):
    return hasattr(obj, "RSMakerReliefSchema") and obj.RSMakerReliefSchema in (1, 2, SCHEMA)


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
                                "con frente multicolor liso y marco hueco separados para imprimir planos.")
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
        for name in ("width", "height", "depth", "text_size", "margin"):
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
            self.feedback.setText("Lámpara: frente liso multicolor de 2 mm + marco hueco de 3 mm "
                                  "con salida trasera para cable. Imprime las piezas "
                                  "sobre caras planas y une el frente al marco. "
                                  "Utiliza filamento translúcido en la base del frente.")
            self.create_button.setText("Regenerar" if self.root else "Crear lámpara") if hasattr(self, "create_button") else None
        else:
            self.feedback.setText("Caja: bloque completamente macizo, "
                                  "cara inferior plana Z=0, colores y letras incrustados sin relieve.")
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
