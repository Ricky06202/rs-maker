"""Deterministic, printer-bed-aware STL export for RS Maker.

This module is importable without FreeCAD so packaging geometry can be tested
in CI. Actual triangulation is delegated to FreeCAD's MeshPart at export time.
No automatic flipping/tilting is performed: XY footprint packing alone does
not imply a support-free orientation or a print-ready child-safe product.
"""
from dataclasses import dataclass
import json
import math
import os
import re
import tempfile

_VALID_KEY=re.compile(r"^[A-Za-z0-9_\-]+$")
_EPS=1e-7


@dataclass(frozen=True)
class Placement:
    key: str
    plate: int
    x: float
    y: float
    width: float
    depth: float


def plan_plates(items, bed_width=430.0, bed_depth=430.0,
                margin=8.0, gap=6.0):
    """Pack (key, width, depth) onto shelf rows without XY overlap.

    The original XY orientation is preserved deliberately: some functional
    parts require manual orientation to reduce supports or optimize strength.
    Each shelf has fixed height, with a guaranteed gap to the next shelf.
    """
    for name,value in (("ancho de cama",bed_width),
                       ("fondo de cama",bed_depth),
                       ("margen",margin),("separación",gap)):
        if not math.isfinite(value) or value<0:
            raise ValueError("%s debe ser un número válido." % name)
    if bed_width<=2*margin or bed_depth<=2*margin or gap<2:
        raise ValueError("La cama es demasiado pequeña o la separación menor a 2 mm.")
    objects=list(items)
    if not objects:
        raise ValueError("No hay piezas para distribuir.")
    if len(objects)>1000:
        raise ValueError("Demasiadas piezas para una sola operación.")
    seen=set()
    for key,width,depth in objects:
        if not isinstance(key,str) or not _VALID_KEY.fullmatch(key):
            raise ValueError("Nombre de pieza STL no válido.")
        if key in seen:
            raise ValueError("Hay claves de pieza duplicadas: %s" % key)
        seen.add(key)
        if (not math.isfinite(width) or not math.isfinite(depth) or
                width<=0 or depth<=0):
            raise ValueError("Pieza %s: medidas inválidas." % key)
        if width>bed_width-2*margin+_EPS or depth>bed_depth-2*margin+_EPS:
            raise ValueError(
                "La pieza %s (%.1f × %.1f mm) no cabe en una cama "
                "%.1f × %.1f mm sin cambiar su orientación."
                % (key,width,depth,bed_width,bed_depth))
    ordered=sorted(objects,key=lambda p:(-p[1]*p[2],-p[2],p[0]))
    plates=[]  # list[list[dict(y,height,next_x)]]
    placements=[]
    for key,width,depth in ordered:
        chosen=None
        for pi,shelves in enumerate(plates):
            for shelf in shelves:
                if (depth<=shelf["height"]+_EPS and
                    shelf["next_x"]+width<=bed_width-margin+_EPS):
                    chosen=(pi,shelf)
                    break
            if chosen:
                break
            y=(margin if not shelves
               else shelves[-1]["y"]+shelves[-1]["height"]+gap)
            if y+depth<=bed_depth-margin+_EPS:
                shelf={"y":y,"height":depth,"next_x":margin}
                shelves.append(shelf)
                chosen=(pi,shelf)
                break
        if chosen is None:
            shelf={"y":margin,"height":depth,"next_x":margin}
            plates.append([shelf])
            chosen=(len(plates)-1,shelf)
        pi,shelf=chosen
        x=shelf["next_x"]
        placements.append(Placement(key,pi+1,x,shelf["y"],width,depth))
        shelf["next_x"]=x+width+gap
    return tuple(sorted(placements,key=lambda p:(p.plate,p.y,p.x,p.key)))


def _generated_objects(root):
    objects=[]
    for obj in root.Group:
        key=getattr(obj,"RSMakerPartKey",None)
        shape=getattr(obj,"Shape",None)
        if not key or shape is None:
            continue
        if hasattr(shape,"isNull") and shape.isNull():
            raise ValueError("Pieza %s: geometría vacía." % key)
        if hasattr(shape,"isValid") and not shape.isValid():
            raise ValueError("Pieza %s: sólido CAD inválido." % key)
        if hasattr(shape,"Solids") and len(shape.Solids)!=1:
            raise ValueError("Pieza %s: no es un sólido único." % key)
        objects.append((key,obj))
    if not objects:
        raise ValueError("No se encontraron sólidos generados.")
    return objects


def _bounds(obj):
    b=obj.Shape.BoundBox
    return (float(b.XMin),float(b.YMin),float(b.ZMin),
            float(b.XMax-b.XMin),float(b.YMax-b.YMin),
            float(b.ZMax-b.ZMin))


def _mesh(obj, meshpart):
    return meshpart.meshFromShape(
        Shape=obj.Shape,LinearDeflection=0.10,
        AngularDeflection=0.30,Relative=False)


def export_separate(root, folder, keep_xy=False):
    """Export every STL on its own print surface, never floating above Z=0."""
    import FreeCAD as App
    import MeshPart
    objects=_generated_objects(root)
    result=[]
    with tempfile.TemporaryDirectory(prefix=".rs-maker-",dir=folder) as temp:
        for key,obj in objects:
            if not _VALID_KEY.fullmatch(key):
                raise ValueError("Nombre de pieza STL no válido.")
            x,y,z,*_= _bounds(obj)
            mesh=_mesh(obj,MeshPart)
            mesh.translate(App.Vector(0 if keep_xy else -x,
                                      0 if keep_xy else -y,-z))
            target=key+".stl"
            mesh.write(os.path.join(temp,target))
            result.append(target)
        for name in result:
            os.replace(os.path.join(temp,name),os.path.join(folder,name))
    return result


def export_plates(root,folder,bed_width=430.0,bed_depth=430.0,
                  margin=8.0,gap=6.0):
    """Write one multi-shell STL per plate and a readable JSON manifest.

    Non-overlap is checked on the original CAD XY footprints, even when
    individual parts have complicated hollow footprints. Original Z minima
    are lowered to the bed separately. Nothing is mirrored or reoriented.
    """
    import FreeCAD as App
    import Mesh
    import MeshPart
    objects=dict(_generated_objects(root))
    specs=[]
    box={}
    for key,obj in objects.items():
        bounds=_bounds(obj)
        box[key]=bounds
        specs.append((key,bounds[3],bounds[4]))
    placements=plan_plates(specs,bed_width,bed_depth,margin,gap)
    filenames=[]
    report=dict(format="rs-maker-print-plates-v1",
                bed_mm=[bed_width,bed_depth],margin_mm=margin,gap_mm=gap,
                orientation="Ensamblaje XY original; cada pieza apoyada en Z=0",
                print_warning=(
                    "Verificar orientación, soportes, tolerancias y resistencia "
                    "en el laminador. STL no conserva color ni identidad de subpartes."),
                plates=[])
    with tempfile.TemporaryDirectory(prefix=".rs-maker-",dir=folder) as temp:
        for pi in sorted({p.plate for p in placements}):
            combined=Mesh.Mesh()
            entries=[]
            for pos in (p for p in placements if p.plate==pi):
                obj=objects[pos.key]
                bx,by,bz,bw,bd,bh=box[pos.key]
                mesh=_mesh(obj,MeshPart)
                mesh.translate(App.Vector(pos.x-bx,pos.y-by,-bz))
                combined.addMesh(mesh)
                entries.append(dict(key=pos.key,x_mm=round(pos.x,4),
                                    y_mm=round(pos.y,4),
                                    width_mm=round(bw,4),
                                    depth_mm=round(bd,4),
                                    height_mm=round(bh,4)))
            name="Plato_%02d.stl"%pi
            combined.write(os.path.join(temp,name))
            filenames.append(name)
            report["plates"].append(dict(file=name,parts=entries))
        with open(os.path.join(temp,"Platos_RS_Maker.json"),"w",encoding="utf-8") as fp:
            json.dump(report,fp,indent=2,ensure_ascii=False)
            fp.write("\n")
        filenames.append("Platos_RS_Maker.json")
        for name in filenames:
            os.replace(os.path.join(temp,name),os.path.join(folder,name))
    return report
