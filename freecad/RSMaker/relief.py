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
    palette_colors: int = 8
    bridge_width: float = 1.6
    quality_mode: str = "balanced"
    compute_backend: str = "auto"
    vector_backend: str = "auto"

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
        if not self.svg_path.lower().endswith((".svg", ".png", ".jpg", ".jpeg", ".webp", ".bmp")):
            raise ValueError("Selecciona SVG, PNG, JPG, WebP o BMP.")
        if not 2 <= self.palette_colors <= 16:
            raise ValueError("Selecciona entre 2 y 16 colores para la caja.")
        if not 1.0 <= self.bridge_width <= 3.5:
            raise ValueError("El ancho del puente debe ser 1.0–3.5 mm.")
        if self.quality_mode not in ("fast","balanced","high"):
            raise ValueError("Selecciona calidad rápida, balanceada o alta.")
        if self.compute_backend not in ("auto","opencl","cpu"):
            raise ValueError("Selecciona un procesador válido (automático, OpenCL o CPU).")
        if self.vector_backend not in ("auto","vtracer","builtin"):
            raise ValueError("Selecciona un vectorizador válido.")
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
SCHEMA = 7
LAMP_FRONT = 2.0  # flat, printable translucent front plate (mm)
LAMP_WALL = 3.0   # adhesive frame width (mm)


def viewport_mesh_quality(mode):
    """FreeCAD preview tessellation (percent deviation, angular degrees).

    Curved OCC geometry can still look faceted if the Part view provider
    tessellates it with coarse default values.
    """
    settings = {
        "fast": (0.5, 28.5),
        "balanced": (0.15, 15.0),
        "high": (0.06, 8.0),
    }
    return settings[mode]


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


def make_parts(cfg, svg_xml, progress=None):
    """Delegate to the optimized 2D/filament engine."""
    from .nameforge_engine import make_parts as build
    return build(cfg, svg_xml, progress=progress)


def is_project(obj):
    return hasattr(obj, "RSMakerReliefSchema") and obj.RSMakerReliefSchema in (1, 2, 3, 4, 5, 6, SCHEMA)


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
    bridge=getattr(root,"BridgeWidth",1.6)
    return ReliefConfig(svg_path=root.SVGPath, font_path=root.FontPath,
                        text=root.Caption, lamp_mode=bool(getattr(root, "LampMode", False)),
                        palette_colors=int(getattr(root,"PaletteColors",8)),
                        bridge_width=float(getattr(bridge,"Value",bridge)),
                        quality_mode=str(getattr(root,"QualityMode","balanced")),
                        compute_backend=str(getattr(root,"ComputeBackend","auto")),
                        vector_backend=str(getattr(root,"VectorBackend","auto")), **values)


def _properties(root, cfg, source, create=False):
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
    import base64
    if not hasattr(root, "SourceData"):
        root.addProperty("App::PropertyString", "SourceData", "Origen")
    if not hasattr(root, "PaletteColors"):
        root.addProperty("App::PropertyInteger", "PaletteColors", "Fabricación")
    if not hasattr(root, "BridgeWidth"):
        root.addProperty("App::PropertyLength", "BridgeWidth", "Fabricación")
    if not hasattr(root, "QualityMode"):
        root.addProperty("App::PropertyString", "QualityMode", "Fabricación")
    if not hasattr(root,"ComputeBackend"):
        root.addProperty("App::PropertyString","ComputeBackend","Fabricación")
    if not hasattr(root,"VectorBackend"):
        root.addProperty("App::PropertyString","VectorBackend","Fabricación")
    root.RSMakerReliefSchema = SCHEMA
    root.VectorBackend = cfg.vector_backend
    root.ComputeBackend = cfg.compute_backend
    root.QualityMode = cfg.quality_mode
    root.LampMode = cfg.lamp_mode
    root.SVGPath = cfg.svg_path
    root.SVGData = source.decode("utf-8-sig") if cfg.svg_path.lower().endswith(".svg") else ""
    root.SourceData = base64.b64encode(source).decode("ascii")
    root.PaletteColors = cfg.palette_colors
    root.BridgeWidth = cfg.bridge_width
    root.FontPath = cfg.font_path
    root.Caption = cfg.text
    for name in FIELDS:
        setattr(root, name.title().replace("_", ""), getattr(cfg, name))


def _read_source(cfg, root):
    """Preserve image/SVG bytes in FreeCAD, including when source file moves."""
    import base64
    if root and getattr(root, "SVGPath", None) == cfg.svg_path:
        saved = getattr(root, "SourceData", "")
        if saved:
            return base64.b64decode(saved)
        old_svg = getattr(root, "SVGData", "")
        if old_svg:
            return old_svg.encode("utf-8")
    from .lamp_stencil import source_bytes
    return source_bytes(cfg.svg_path)


def save_project(cfg, root=None, progress=None, lamp_mask_meta=None):
    import FreeCAD as App
    cfg.validate()
    source = _read_source(cfg, root)
    from . import lamp_stencil
    extension = os.path.splitext(cfg.svg_path)[1].lower()
    if cfg.lamp_mode:
        # A genuine open LED lightbox with a single, connected stencil front.
        parts = lamp_stencil.make_lamp(cfg, source, extension, progress,
                                       mask_meta=lamp_mask_meta)
    else:
        # SVGs and images are posterized into a small, editable flat palette.
        prepared = lamp_stencil.optimize_svg(
            source, extension, colors=cfg.palette_colors, progress=progress)
        parts = make_parts(cfg, prepared, progress=progress)
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
            if cfg.lamp_mode and App.GuiUp:
                # View-only tessellation: independent of the actual accurate
                # BSpline BRep, and applicable to exports using view meshing.
                deviation, angle = viewport_mesh_quality(cfg.quality_mode)
                part.ViewObject.Deviation = deviation
                part.ViewObject.AngularDeflection = angle
        for key, obsolete in old.items():
            if key not in needed:
                doc.removeObject(obsolete.Name)
        _properties(root, cfg, source, create)
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
        note = QtWidgets.QLabel("Elige caja maciza multicolor o lámpara de dos piezas: "
                                "frente calado y carcasa con fondo integrado, sin tapa suelta.")
        note.setWordWrap(True)
        layout.addWidget(note)
        form = QtWidgets.QFormLayout()
        layout.addLayout(form)
        self.svg = QtWidgets.QLineEdit()
        self.font = QtWidgets.QLineEdit()
        self.caption = QtWidgets.QLineEdit()
        self.caption.setPlaceholderText("Ej.: RODRIGO")
        for name, target, file_filter in (
                ("Imagen o SVG", self.svg, "Diseños (*.svg *.png *.jpg *.jpeg *.webp *.bmp)"),
                ("Tipografía", self.font, "Fuentes (*.ttf *.otf)")):
            row = QtWidgets.QHBoxLayout()
            row.addWidget(target)
            browse = QtWidgets.QPushButton("Elegir…")
            browse.clicked.connect(lambda checked=False, t=target, f=file_filter:
                                   self._browse(t, f))
            row.addWidget(browse)
            form.addRow(name, row)
        form.addRow("Nombre", self.caption)
        self.lamp_mode = QtWidgets.QCheckBox("Lámpara: frontal y carcasa integrada (2 piezas)")
        self.lamp_mode.setToolTip("Activado: frente calado y carcasa maciza trasera "
                                  "fusionada con el marco (2 piezas). Cavidad LED "
                                  "y orificio de cable. Desactivado: caja maciza.")
        form.addRow("Modo", self.lamp_mode)
        self.palette = QtWidgets.QSpinBox()
        self.palette.setRange(2, 16)
        self.palette.setValue(8)
        self.palette.setToolTip("Solo caja: paleta reducida de la imagen o SVG.")
        form.addRow("Colores de la caja", self.palette)
        self.bridge = QtWidgets.QDoubleSpinBox()
        self.bridge.setRange(1.0, 3.5)
        self.bridge.setDecimals(1)
        self.bridge.setSingleStep(0.2)
        self.bridge.setValue(1.6)
        self.bridge.setSuffix(" mm")
        self.bridge.setToolTip("Solo lámpara: conecta los centros de A, O, B, R, D y otros recortes.")
        form.addRow("Ancho de los puentes", self.bridge)
        self.quality = QtWidgets.QComboBox()
        for label,value in (("Rápido · vista previa","fast"),
                            ("Balanceado · recomendado","balanced"),
                            ("Alta calidad · detalle fino","high")):
            self.quality.addItem(label,value)
        self.quality.setCurrentIndex(1)
        self.quality.setToolTip(
            "Controla la resolución y el suavizado; los límites de memoria "
            "evitan que diseños grandes saturen FreeCAD.")
        form.addRow("Calidad del contorno",self.quality)
        self.vectorizer = QtWidgets.QComboBox()
        for label,value in (
                ("Automático · VTracer o trazador interno","auto"),
                ("Preferir VTracer · respaldo interno","vtracer"),
                ("Solo trazador interno · seguro","builtin")):
            self.vectorizer.addItem(label,value)
        self.vectorizer.setToolTip(
            "VTracer es opcional y corre en un Python externo aislado. "
            "Sin VTracer se usa el trazador subpíxel incorporado.")
        form.addRow("Vectorización",self.vectorizer)
        self.backend = QtWidgets.QComboBox()
        for label,value in (
                ("Automático · AMD/OpenCL si disponible","auto"),
                ("Preferir GPU · OpenCL (respaldo CPU)","opencl"),
                ("Solo CPU · sin dependencias extra","cpu")):
            self.backend.addItem(label,value)
        self.backend.setToolTip(
            "OpenCV y un controlador OpenCL funcional son opcionales. "
            "La fase final de FreeCAD/OpenCascade sigue utilizando CPU.")
        form.addRow("Procesamiento de imagen",self.backend)
        self.sizes = {}
        defaults = ReliefConfig()
        for name in ("width", "height", "depth", "text_size", "margin"):
            field = QtWidgets.QDoubleSpinBox()
            field.setSuffix(" mm")
            field.setDecimals(2)
            limits = {"width": (30, 430), "height": (40, 430),
                      "depth": (2, 100), "text_size": (4, 80),
                      "margin": (2, 25)}
            field.setRange(*limits[name])
            field.setValue(getattr(defaults, name))
            field.setSingleStep(0.5)
            self.sizes[name] = field
            form.addRow(DISPLAY[name], field)
        self.ratio_note = QtWidgets.QLabel("Ancho y alto vinculados: conservar proporciones")
        self.ratio_note.setWordWrap(True)
        form.addRow("Escala proporcional", self.ratio_note)
        self.suggest_button = QtWidgets.QPushButton("Sugerir dimensiones según el detalle")
        self.suggest_button.setToolTip(
            "Analiza los bordes y la complejidad del dibujo. "
            "No modifica la profundidad ni garantiza detalle mínimo en impresión.")
        self.suggest_button.clicked.connect(self._suggest_dimensions)
        form.addRow("", self.suggest_button)
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
            self.palette.setValue(cfg.palette_colors)
            self.bridge.setValue(cfg.bridge_width)
            quality_index=self.quality.findData(cfg.quality_mode)
            self.quality.setCurrentIndex(max(0,quality_index))
            vector_index=self.vectorizer.findData(cfg.vector_backend)
            self.vectorizer.setCurrentIndex(max(0,vector_index))
            compute_index=self.backend.findData(cfg.compute_backend)
            self.backend.setCurrentIndex(max(0,compute_index))
            self.lamp_mode.setChecked(cfg.lamp_mode)
        self._ratio = self.sizes["width"].value() / self.sizes["height"].value()
        self._updating_link = False
        self._show_ratio()
        for name in ("width", "height"):
            self.sizes[name].valueChanged.connect(
                lambda value, changed=name: self._keep_proportions(changed, value))

    def _show_ratio(self):
        self.ratio_note.setText(
            "Ancho y alto siempre vinculados · relación %.3f:1" % self._ratio)

    def _set_linked_size(self, width, height, new_ratio=False):
        if new_ratio:
            self._ratio = width / height
        self._updating_link = True
        try:
            for name, size in (("width", width), ("height", height)):
                spin = self.sizes[name]
                previous = spin.blockSignals(True)
                try:
                    spin.setValue(size)
                finally:
                    spin.blockSignals(previous)
        finally:
            self._updating_link = False
        self._show_ratio()

    def _keep_proportions(self, changed, value):
        if self._updating_link:
            return
        from .stencil_core import proportional_size
        width = self.sizes["width"].value()
        height = self.sizes["height"].value()
        matched = proportional_size(width, height, self._ratio, changed)
        self._set_linked_size(*matched)

    def _suggest_dimensions(self):
        import os
        from . import lamp_stencil
        from .stencil_core import suggest_dimensions
        from .relief import _read_source
        path = self.svg.text().strip()
        if not path:
            QtWidgets.QMessageBox.information(
                self, "Selecciona una imagen", "Elige una imagen o SVG para analizarla.")
            return
        try:
            cfg = ReliefConfig(svg_path=path)
            data = _read_source(cfg, self.root)
            image = lamp_stencil._qt_image(
                data, os.path.splitext(path)[1].lower(), 360, 360)
            mask = lamp_stencil._fg_mask(
                lamp_stencil._pixels(image), image.width(), image.height(), 45)
            suggestion = suggest_dimensions(
                mask, image.width(), image.height(), len(self.caption.text()))
            self._set_linked_size(
                suggestion["width"], suggestion["height"], new_ratio=True)
            QtWidgets.QMessageBox.information(
                self, "Dimensiones sugeridas",
                "Ancho: %.0f mm · alto: %.0f mm.\n"
                "Detalle estimado: %s.\n"
                "La profundidad no se ha modificado. "
                "Puedes cambiar cualquier dimensión sin perder la proporción. "
                "Revisa los detalles en el laminador antes de imprimir." %
                (suggestion["width"], suggestion["height"], suggestion["detail"]))
        except Exception as exc:
            QtWidgets.QMessageBox.warning(
                self, "No se pudo analizar la imagen", str(exc))

    def _mode_changed(self, *args):
        is_lamp = self.lamp_mode.isChecked()
        self.palette.setEnabled(not is_lamp)
        self.bridge.setEnabled(is_lamp)
        self.quality.setEnabled(is_lamp)
        self.vectorizer.setEnabled(is_lamp)
        self.backend.setEnabled(is_lamp)
        if is_lamp:
            self.feedback.setText(
                "Lámpara: silueta exterior, detalles y nombre calados. "
                "Los centros de letras quedan sujetos con puentes; "
                "el marco y la tapa trasera están fusionados en una sola carcasa. "
                "Imprime frontal y carcasa por separado.")
        else:
            self.feedback.setText(
                "Caja maciza: imagen o SVG se reduce a una paleta configurable "
                "y sus colores se incrustan en la cara plana, sin relieve.")
        if hasattr(self, "create_button"):
            self.create_button.setText(
                "Regenerar" if self.root else
                ("Crear lámpara calada" if is_lamp else "Crear caja multicolor"))

    def _browse(self, target, file_filter):
        chosen, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Seleccionar archivo",
                                                          target.text(), file_filter)
        if chosen:
            target.setText(chosen)

    def _build_lamp_masks_responsive(self, cfg, progress, dialog):
        """Qt signals keep the dialog alive while mask processing runs off UI.

        FreeCAD/Part remain strictly on the GUI thread after the worker exits.
        A cancel request is cooperative and we always await completion before
        releasing the QThread, avoiding 'destroyed while thread is running'.
        """
        from . import lamp_stencil
        from .nameforge_worker import MaskWorker
        from .lamp_stencil import QtCore
        data=_read_source(cfg,self.root)
        from . import crash_diagnostics
        crash_diagnostics.checkpoint("qt:prepare-inputs")
        prepared=lamp_stencil.prepare_inputs(
            cfg,data,os.path.splitext(cfg.svg_path)[1].lower(),progress)
        crash_diagnostics.checkpoint("qt:prepared")
        worker=MaskWorker(cfg,prepared,self)
        loop=QtCore.QEventLoop(self)

        def update(value,message):
            # Emitted on the worker; Qt queues the slot on the UI thread.
            # Avoid calling processEvents() recursively inside the slot.
            dialog.setLabelText(message)
            dialog.setValue(min(99,int(value)))

        def cancel():
            worker.cancel()
            dialog.setLabelText("Cancelando después de la etapa actual…")
            dialog.setCancelButton(None)

        worker.progressed.connect(update)
        dialog.canceled.connect(cancel)
        worker.finished.connect(loop.quit)
        try:
            worker.start()
            if worker.isRunning():
                if hasattr(loop,"exec"):
                    loop.exec()
                else:
                    loop.exec_()
            worker.wait()
            if worker.error:
                raise RuntimeError(worker.error)
            if dialog.wasCanceled():
                raise RuntimeError("Generación cancelada.")
            if worker.result is None:
                raise RuntimeError("No se generó la máscara.")
            return worker.result
        finally:
            if worker.isRunning():
                worker.cancel()
                worker.wait()
            worker.deleteLater()

    def generate(self):
        cfg = ReliefConfig(svg_path=self.svg.text().strip(),
                           font_path=self.font.text().strip(),
                           text=self.caption.text().strip(),
                           lamp_mode=self.lamp_mode.isChecked(),
                           palette_colors=self.palette.value(),
                           bridge_width=self.bridge.value(),
                           quality_mode=str(self.quality.currentData()),
                           compute_backend=str(self.backend.currentData()),
                           vector_backend=str(self.vectorizer.currentData()),
                           **{name:field.value() for name,field in self.sizes.items()})
        dialog = QtWidgets.QProgressDialog(
            "Preparando diseño...", "Cancelar", 0, 100, self)
        dialog.setWindowTitle("RS Maker · Generando NameForge")
        dialog.setMinimumDuration(0)
        dialog.setValue(0)
        self.create_button.setEnabled(False)
        self.suggest_button.setEnabled(False)
        success = False

        def on_progress(value, message):
            dialog.setLabelText(message)
            dialog.setValue(min(99, int(value)))
            QtWidgets.QApplication.processEvents()
            if dialog.wasCanceled():
                raise RuntimeError("Generación cancelada; no se modificó el proyecto.")

        try:
            cfg.validate()
            from . import crash_diagnostics
            crash_diagnostics.start_generation(cfg)
            meta = (self._build_lamp_masks_responsive(cfg, on_progress, dialog)
                    if cfg.lamp_mode else None)
            if cfg.lamp_mode:
                crash_diagnostics.checkpoint("cad:start")
                on_progress(86, "Construyendo sólidos en FreeCAD (fase CAD)")
            self.root = save_project(
                cfg, self.root, progress=on_progress, lamp_mask_meta=meta)
            if meta:
                import FreeCAD as App
                diagnostics=meta.get("acceleration",{})
                timings=meta.get("timings",{})
                artwork=meta.get("artwork",{})
                App.Console.PrintMessage(
                    "RS Maker NameForge | Tipo de imagen: %s | "
                    "densidad de negro: %.1f%% | "
                    "microhuecos descartados: %d\\n" %
                    (artwork.get("style","no detectado"),
                     100*artwork.get("ink_density",0),
                     artwork.get("removed_cutouts",0)))
                methods=meta.get("trace_methods",{})
                fallbacks=meta.get("vector_fallbacks",{})
                for name,error in fallbacks.items():
                    App.Console.PrintWarning(
                        "RS Maker NameForge | VTracer %s: %s · "
                        "trazador interno activado\n" % (name,error))
                App.Console.PrintMessage(
                    "RS Maker NameForge | Vectorización: frontal %s, "
                    "carcasa %s, cavidad %s\\n" %
                    (methods.get("front","poligonal"),
                     methods.get("rear","poligonal"),
                     methods.get("cavity","poligonal")))
                App.Console.PrintMessage(
                    "RS Maker NameForge | Procesador: %s | %s | "
                    "preparación: %.2f s, silueta: %.2f s, "
                    "máscaras: %.2f s, contornos: %.2f s\\n" %
                    (diagnostics.get("backend","CPU"),
                     diagnostics.get("detail",""),
                     timings.get("total_preparation_s",0),
                     timings.get("silhouette_s",0),
                     timings.get("mask_and_bridges_s",0),
                     timings.get("contours_s",0)))
            crash_diagnostics.checkpoint("generate:success")
            dialog.setValue(100)
            success = True
        except Exception as exc:
            from . import crash_diagnostics
            crash_diagnostics.checkpoint("generate:python-error",error=type(exc).__name__)
            if "cancelada" not in str(exc).lower():
                QtWidgets.QMessageBox.critical(
                    self, "No se pudo generar NameForge", str(exc))
        finally:
            self.create_button.setEnabled(True)
            self.suggest_button.setEnabled(True)
            dialog.close()
            dialog.deleteLater()
        if success:
            self.accept()


def show_dialog(root=None):
    import FreeCADGui as Gui
    ReliefDialog(root, Gui.getMainWindow()).exec()
