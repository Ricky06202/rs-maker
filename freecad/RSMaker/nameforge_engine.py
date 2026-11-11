"""Geometry engine for RS Maker NameForge.

Planar painter-order clipping, local spatial queries and in-session SVG/art
caches avoid the quadratic 3D-boolean pipeline of the earlier prototype.
No non-FreeCAD geometry dependencies are required.
"""
from collections import OrderedDict
from hashlib import sha256
from math import floor, sqrt
import os
import tempfile

_SVG_CACHE = OrderedDict()
_ART_CACHE = OrderedDict()
_CACHE_ITEMS = 2


def _remember(cache, key, value):
    cache[key] = value
    cache.move_to_end(key)
    while len(cache) > _CACHE_ITEMS:
        cache.popitem(last=False)
    return value


def overlap_xy(a, b):
    a, b = a.BoundBox, b.BoundBox
    eps = 1e-7
    return (a.XMin < b.XMax - eps and b.XMin < a.XMax - eps
            and a.YMin < b.YMax - eps and b.YMin < a.YMax - eps)


class SpatialBuckets:
    """Uniform-grid broad phase; oversized paths go in a separate list.

    Only genuinely intersecting bounding boxes are forwarded to the OCC
    boolean kernel. Geometry order is retained for SVG painter semantics.
    """

    def __init__(self, bounds, count):
        self.xmin, self.ymin = bounds.XMin, bounds.YMin
        n = min(96, max(8, int(sqrt(max(1, count))) * 2))
        self.n = n
        self.dx = max(float(bounds.XLength) / n, 1e-7)
        self.dy = max(float(bounds.YLength) / n, 1e-7)
        self.cells = {}
        self.large = []
        self.shapes = []
        self.candidate_checks = 0

    def _cells(self, shape):
        b = shape.BoundBox
        x0 = max(0, min(self.n - 1, floor((b.XMin - self.xmin) / self.dx)))
        x1 = max(0, min(self.n - 1, floor((b.XMax - self.xmin) / self.dx)))
        y0 = max(0, min(self.n - 1, floor((b.YMin - self.ymin) / self.dy)))
        y1 = max(0, min(self.n - 1, floor((b.YMax - self.ymin) / self.dy)))
        return x0, x1, y0, y1

    def insert(self, shape):
        index = len(self.shapes)
        self.shapes.append(shape)
        x0, x1, y0, y1 = self._cells(shape)
        if (x1 - x0 + 1) * (y1 - y0 + 1) > 256:
            self.large.append(index)
            return
        for x in range(x0, x1 + 1):
            for y in range(y0, y1 + 1):
                self.cells.setdefault((x, y), []).append(index)

    def overlaps(self, shape):
        x0, x1, y0, y1 = self._cells(shape)
        ids = set(self.large)
        if (x1 - x0 + 1) * (y1 - y0 + 1) > 256:
            # A query spanning most of the drawing can overlap any indexed
            # shape, including shapes whose cells are far from its center.
            ids.update(range(len(self.shapes)))
        else:
            for x in range(x0, x1 + 1):
                for y in range(y0, y1 + 1):
                    ids.update(self.cells.get((x, y), ()))
        self.candidate_checks += len(ids)
        return [self.shapes[i] for i in sorted(ids) if overlap_xy(shape, self.shapes[i])]


def flatten_faces(layers, progress=None):
    """Resolve SVG painting order on 2D faces, not extruded 3D solids.

    Output faces are non-overlapping; each face preserves its filament color.
    A later SVG face masks an earlier face, including holes and outlines.
    """
    if not layers:
        return []
    import Part
    compound = Part.makeCompound([face for face, _ in layers])
    grid = SpatialBuckets(compound.BoundBox, len(layers))
    visible = []
    total = len(layers)
    for i, (face, color) in enumerate(reversed(layers)):
        overlapping = grid.overlaps(face)
        trimmed = face.cut(Part.makeCompound(overlapping)) if overlapping else face
        if not trimmed.isNull():
            for piece in trimmed.Faces:
                if piece.Area > 1e-6:
                    if not piece.isValid():
                        raise ValueError("SVG con caminos inválidos: corrige las intersecciones.")
                    visible.append((piece.copy(), color))
        grid.insert(face)
        if progress and (i % 25 == 0 or i + 1 == total):
            progress(22 + 38 * (i + 1) / total,
                     "Resolviendo regiones del SVG: %d/%d" % (i + 1, total))
    return visible


def _svg_faces(svg_xml, progress=None):
    """Import only once per XML digest; detached BReps survive document close."""
    import FreeCAD as App
    import importSVG
    from .relief import _faces, _svg_color

    key = sha256(svg_xml.encode("utf-8")).hexdigest()
    cached = _SVG_CACHE.get(key)
    if cached is not None:
        _SVG_CACHE.move_to_end(key)
        if progress:
            progress(12, "SVG reutilizado desde la memoria")
        return key, cached

    old = App.ActiveDocument
    tmp = App.newDocument("RSNameForgeSVG")
    path = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".svg", encoding="utf-8",
                                         delete=False) as stream:
            stream.write(svg_xml)
            path = stream.name
        if progress:
            progress(6, "Importando SVG vectorial")
        importSVG.insert(path, tmp.Name)
        tmp.recompute()
        source = []
        for obj in tmp.Objects:
            if hasattr(obj, "Shape") and not obj.Shape.isNull():
                for i, face in enumerate(_faces(obj.Shape)):
                    source.append((face.copy(), _svg_color(obj, i)))
        if not source:
            raise ValueError("El SVG no tiene áreas rellenas cerradas.")
        _remember(_SVG_CACHE, key, tuple(source))
        if progress:
            progress(18, "SVG importado: %d regiones" % len(source))
        return key, _SVG_CACHE[key]
    finally:
        if path and os.path.exists(path):
            os.remove(path)
        App.closeDocument(tmp.Name)
        if old:
            App.setActiveDocument(old.Name)


def _artwork(cfg, svg_xml, progress=None):
    """Cache the *visible* planar illustration across name-only edits."""
    import FreeCAD as App
    import Part

    digest = sha256(svg_xml.encode("utf-8")).hexdigest()
    key = (digest, cfg.width, cfg.height, cfg.margin, cfg.text_size)
    if key in _ART_CACHE:
        _ART_CACHE.move_to_end(key)
        if progress:
            progress(60, "Dibujo reutilizado: solo cambia el nombre")
        return _ART_CACHE[key]

    _, source = _svg_faces(svg_xml, progress)
    caption_band = max(cfg.text_size + 2 * cfg.margin, cfg.height * 0.25)
    picture_height = cfg.height - caption_band - 2 * cfg.margin
    if picture_height < 5:
        raise ValueError("La caja es demasiado baja para el dibujo y el nombre.")

    bbox = Part.makeCompound([f for f, _ in source]).BoundBox
    if bbox.XLength < 1e-5 or bbox.YLength < 1e-5:
        raise ValueError("El SVG no tiene un área visible válida.")
    scale = min((cfg.width - 2 * cfg.margin) / bbox.XLength,
                picture_height / bbox.YLength)
    x = cfg.width / 2 - scale * (bbox.XMin + bbox.XMax) / 2
    y = caption_band + cfg.margin + picture_height / 2 - scale * (bbox.YMin + bbox.YMax) / 2
    planar = []
    for face, color in source:
        f = face.copy()
        f.scale(scale)
        # All SVG regions share the same planar printing surface.
        f.translate(App.Vector(x, y, -f.BoundBox.ZMin))
        planar.append((f, color))
    visible = flatten_faces(planar, progress)
    if not visible:
        raise ValueError("El SVG no dejó áreas visibles después de resolver colores.")
    return _remember(_ART_CACHE, key, tuple(visible))


def _caption(cfg):
    import FreeCAD as App
    import Draft
    from .relief import _faces, _fit

    old = App.ActiveDocument
    doc = App.newDocument("RSNameForgeCaption")
    try:
        caption = Draft.make_shapestring(cfg.text, cfg.font_path, cfg.text_size, 0)
        doc.recompute()
        if caption.Shape.isNull():
            raise ValueError("La tipografía no generó contornos.")
        band = max(cfg.text_size + 2 * cfg.margin, cfg.height * 0.25)
        centered = _fit(caption.Shape, cfg.width - 2 * cfg.margin,
                        min(cfg.text_size, band - cfg.margin),
                        cfg.width / 2, band / 2, 0)
        faces = _faces(centered)
        if not faces:
            raise ValueError("La tipografía no produjo letras cerradas.")
        return [(f, (0.1, 0.65, 0.85)) for f in faces]
    finally:
        App.closeDocument(doc.Name)
        if old:
            App.setActiveDocument(old.Name)


def make_parts(cfg, svg_xml, progress=None):
    """Create flat color inlays by planar clipping and a thin final extrusion.

    This avoids extruding every path before overlay clipping, and replaces a
    multi-body 3D cut on the thick block with a 2D cut on its top face.
    """
    import FreeCAD as App
    import Part
    from .relief import LAMP_FRONT, _lamp_frame

    def report(value, message):
        if progress:
            progress(value, message)

    art = _artwork(cfg, svg_xml, report)
    report(62, "Preparando tipografía y nombre")
    text = _caption(cfg)
    report(68, "Preparando superficies de colores")
    # Text lives outside the picture band. Resolve text self-overlaps.
    printable = list(art) + flatten_faces(text)
    surface = Part.makeCompound([face for face, _ in printable])
    if surface.isNull():
        raise ValueError("No hay superficies multicolor imprimibles.")

    front_z = cfg.depth - LAMP_FRONT if cfg.lamp_mode else 0.0
    front_thickness = LAMP_FRONT if cfg.lamp_mode else cfg.depth
    inlay = min(0.6, front_thickness - 0.6)
    if inlay < 0.1:
        raise ValueError("La profundidad no permite incrustaciones.")
    top_z = front_z + front_thickness - inlay
    # One planar boolean, one extrusion, one fusion. The back remains filled.
    report(73, "Recortando fondo en 2D")
    plane = Part.makePlane(cfg.width, cfg.height)
    remaining = plane.cut(surface)
    if remaining.isNull():
        raise ValueError("Los colores cubren completamente la superficie.")
    report(80, "Extruyendo el fondo y las incrustaciones")
    colored_base = remaining.extrude(App.Vector(0, 0, inlay))
    colored_base.translate(App.Vector(0, 0, top_z))
    substrate = Part.makeBox(cfg.width, cfg.height, front_thickness - inlay,
                             App.Vector(0, 0, front_z))
    backing = substrate.fuse(colored_base)
    if not backing.isValid() or len(backing.Solids) != 1:
        raise ValueError("No se pudo crear una base maciza válida con colores encajados.")
    report(90, "Agrupando cuerpos por filamento")
    palette = OrderedDict()
    for face, color in printable:
        palette.setdefault(color, []).append(face)
    result = [("nameforge_frente" if cfg.lamp_mode else "nameforge_base",
               "Base plana · color de fondo", backing, (0.93, 0.93, 0.93))]
    for index, (color, faces) in enumerate(palette.items(), 1):
        if len(faces) == 1:
            part = faces[0].extrude(App.Vector(0, 0, inlay))
        else:
            part = Part.makeCompound(faces).extrude(App.Vector(0, 0, inlay))
        part.translate(App.Vector(0, 0, top_z))
        if not part.isValid():
            raise ValueError("Error al generar el filamento %d." % index)
        result.append(("nameforge_color_%03d" % index,
                       "Color %d · incrustado" % index, part, color))
    if cfg.lamp_mode:
        result.append(("nameforge_marco", "Marco hueco · salida de cable",
                       _lamp_frame(cfg), (0.32, 0.42, 0.53)))
    report(98, "Geometría preparada")
    return result
