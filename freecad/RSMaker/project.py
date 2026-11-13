"""Safe FreeCAD document updates and schema-2/3/4 compatibility."""
from .config import PuzzleConfig, SIDE_MECHANISM_FIELDS
from .geometry import build_shapes

DIMENSION_FIELDS = ("width", "depth", "height", "wall", "floor", "clearance")
DIFFICULTY_FIELDS = ("frontal", "derecha", "trasera", "izquierda", "tapa")
ART_FIELDS = ("collection", "figure", "scene", "expression")
ALL_FIELDS = (DIMENSION_FIELDS + DIFFICULTY_FIELDS +
              SIDE_MECHANISM_FIELDS + ("theme", "figure_height") + ART_FIELDS)
GENERATOR_VERSION = "0.4.0"


def _set_parameters(root, cfg, create=False):
    if create:
        root.addProperty("App::PropertyString", "GeneratorVersion", "RS Maker")
        root.addProperty("App::PropertyInteger", "RSMakerSchema", "RS Maker")
        root.addProperty("App::PropertyString", "Notes", "RS Maker")
        root.addProperty("App::PropertyString", "Theme", "RS Maker")
        for f in DIMENSION_FIELDS:
            root.addProperty("App::PropertyLength", f, "Medidas (mm)")
        for f in DIFFICULTY_FIELDS:
            root.addProperty("App::PropertyString", f.capitalize(), "Dificultades (5 caras)")
    for field in ART_FIELDS:
        prop=field.capitalize()
        if not hasattr(root, prop):
            root.addProperty("App::PropertyString",prop,"Arte original")
    if not hasattr(root,"FigureHeight"):
        root.addProperty("App::PropertyLength","FigureHeight","Arte original")
    for field in SIDE_MECHANISM_FIELDS:
        prop=field.title().replace("_","")
        if not hasattr(root,prop):
            root.addProperty("App::PropertyString",prop,"Mecanismos (4 laterales)")
    root.RSMakerSchema = 4
    root.GeneratorVersion = GENERATOR_VERSION
    root.Notes = ("Cinco retos mecánicos, cuatro laterales con familia elegible "
                  "(rueda o compuerta lineal) y leva superior; arte original "
                  "con mini escenario y chibi. Prototipo sin validar físicamente: "
                  "retención, resistencia y holguras requieren impresión de prueba.")
    root.Theme = cfg.theme
    for field in ART_FIELDS:
        setattr(root,field.capitalize(),getattr(cfg,field))
    root.FigureHeight = cfg.figure_height
    for field in SIDE_MECHANISM_FIELDS:
        setattr(root,field.title().replace("_",""),getattr(cfg,field))
    for name in DIMENSION_FIELDS:
        setattr(root,name,getattr(cfg,name))
    for name in DIFFICULTY_FIELDS:
        setattr(root,name.capitalize(),getattr(cfg,name))


def _add_generated(doc, root, parts):
    for key, shape, color in parts:
        obj = doc.addObject("Part::Feature", "RS_"+key)
        obj.Label = key.replace("_", " ")
        obj.addProperty("App::PropertyString", "RSMakerPartKey", "RS Maker")
        obj.RSMakerPartKey = key
        obj.Shape = shape
        obj.ViewObject.ShapeColor = color
        root.addObject(obj)


def create_project(cfg, doc=None):
    import FreeCAD as App
    cfg.validate()
    parts = build_shapes(cfg)  # fail before touching documents
    doc = doc or App.ActiveDocument or App.newDocument("RSMaker")
    doc.openTransaction("Crear caja puzzle cinco caras RS Maker")
    try:
        root = doc.addObject("App::DocumentObjectGroup", "RS_Puzzle")
        root.Label = "RS Maker | Cinco caras + tapa final"
        _set_parameters(root,cfg,create=True)
        _add_generated(doc,root,parts)
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


def _is_project(obj):
    return (hasattr(obj,"RSMakerSchema") and int(obj.RSMakerSchema) in (2,3,4))


def get_project_from_selection():
    import FreeCADGui as Gui
    for obj in Gui.Selection.getSelection():
        if _is_project(obj):
            return obj
        for parent in getattr(obj,"InList",[]):
            if _is_project(parent):
                return parent
    return None


def config_from_project(root):
    if not _is_project(root):
        raise ValueError("Proyecto incompatible: crea uno nuevo con RS Maker.")
    def length(name):
        val = getattr(root,name)
        return float(getattr(val,"Value",val))
    values = {name:length(name) for name in DIMENSION_FIELDS}
    for name in DIFFICULTY_FIELDS:
        values[name] = getattr(root,name.capitalize())
    values["theme"] = root.Theme
    for field in ART_FIELDS:
        values[field] = getattr(root,field.capitalize(),getattr(PuzzleConfig(),field))
    for field in SIDE_MECHANISM_FIELDS:
        values[field]=getattr(root,field.title().replace("_",""),
                              getattr(PuzzleConfig(),field))
    height = getattr(root,"FigureHeight",30.0)
    values["figure_height"] = float(getattr(height,"Value",height))
    return PuzzleConfig(**values).validate()


def regenerate_project(root,cfg):
    cfg.validate()
    if not _is_project(root):
        raise ValueError("Solo se pueden regenerar proyectos del esquema 2, 3 o 4.")
    parts = build_shapes(cfg)
    doc = root.Document
    doc.openTransaction("Regenerar cinco puzzles RS Maker")
    try:
        old = {o.RSMakerPartKey:o for o in root.Group if hasattr(o,"RSMakerPartKey")}
        expected = set()
        for key,shape,color in parts:
            expected.add(key)
            obj = old.get(key)
            if obj is None:
                obj = doc.addObject("Part::Feature","RS_"+key)
                obj.addProperty("App::PropertyString","RSMakerPartKey","RS Maker")
                obj.RSMakerPartKey=key
                root.addObject(obj)
            obj.Label = key.replace("_"," ")
            obj.Shape = shape
            obj.ViewObject.ShapeColor = color
        for key,obj in old.items():
            if key not in expected:
                doc.removeObject(obj.Name)
        _set_parameters(root,cfg)
        doc.recompute()
        doc.commitTransaction()
    except Exception:
        doc.abortTransaction()
        raise
    return root
