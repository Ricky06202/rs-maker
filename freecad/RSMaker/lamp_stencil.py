"""RS Maker NameForge — silhouette lightbox from SVG, PNG, JPG or WebP.

QtSvg/QImage rasterization handles complex source art without requiring OpenCV,
Pillow or external vectorizers inside FreeCAD. A print-safe stencil mask is
then converted to a compact, editable BRep with true holes and text bridges.
"""
import os
import tempfile
from collections import Counter, OrderedDict
from hashlib import sha256
from threading import Lock

from . import stencil_core as core

try:
    from PySide import QtCore, QtGui, QtSvg
except ImportError:
    try:
        from PySide6 import QtCore, QtGui, QtSvg
    except ImportError:
        from PySide2 import QtCore, QtGui, QtSvg


_FORMATS=('.svg','.png','.jpg','.jpeg','.webp','.bmp')
_ART_CACHE = OrderedDict()
_ART_CACHE_LOCK = Lock()
_MAX_CACHE_ENTRIES = 2


def _cached_art(key):
    with _ART_CACHE_LOCK:
        value = _ART_CACHE.get(key)
        if value is not None:
            _ART_CACHE.move_to_end(key)
        return value


def _remember_art(key, ink, outer):
    with _ART_CACHE_LOCK:
        _ART_CACHE[key] = (bytes(ink), bytes(outer))
        _ART_CACHE.move_to_end(key)
        while len(_ART_CACHE) > _MAX_CACHE_ENTRIES:
            _ART_CACHE.popitem(last=False)


def _image_to_mask(image, threshold=45):
    """Read QImage directly in the worker, avoiding huge temporary RGB lists."""
    w, h = image.width(), image.height()
    points=((0,0),(w-1,0),(0,h-1),(w-1,h-1))
    corners=[]
    for x,y in points:
        p=image.pixel(x,y)
        corners.append(((p>>16)&255,(p>>8)&255,p&255))
    r0,g0,b0=Counter(corners).most_common(1)[0][0]
    out=bytearray(w*h)
    index=0
    for y in range(h):
        for x in range(w):
            pixel=image.pixel(x,y)
            red=(pixel>>16)&255
            green=(pixel>>8)&255
            blue=pixel&255
            out[index]=int(max(abs(red-r0),abs(green-g0),abs(blue-b0))>threshold)
            index+=1
    return out


def source_bytes(path,embedded=None):
    """Return the source content without altering the user's original."""
    if embedded is not None:
        return embedded
    if os.path.getsize(path)>15_000_000:
        raise ValueError('Imagen demasiado grande (máximo 15 MB).')
    with open(path,'rb') as f:
        data=f.read()
    if path.lower().endswith('.svg') and (
            b'<!doctype' in data.lower() or b'<!entity' in data.lower()):
        raise ValueError('Exporta el SVG sin DOCTYPE ni entidades externas.')
    return data


def _qt_image(source,extension,w,h):
    """Rasterize source on a neutral matte, preserving aspect ratio."""
    qimg=QtGui.QImage(w,h,QtGui.QImage.Format_ARGB32)
    qimg.fill(QtGui.QColor(255,255,255))
    painter=QtGui.QPainter(qimg)
    try:
        painter.setRenderHint(QtGui.QPainter.Antialiasing,True)
        if extension.lower()=='.svg':
            renderer=QtSvg.QSvgRenderer(QtCore.QByteArray(source))
            if not renderer.isValid():
                raise ValueError('SVG inválido: revisa su sintaxis.')
            size=renderer.defaultSize()
            iw=max(size.width(),1)
            ih=max(size.height(),1)
            scale=min(w/iw,h/ih)
            dw=iw*scale
            dh=ih*scale
            renderer.render(painter,QtCore.QRectF((w-dw)/2,(h-dh)/2,dw,dh))
        else:
            raw=QtGui.QImage()
            if not raw.loadFromData(source):
                raise ValueError('No se puede abrir esta imagen.')
            iw=max(raw.width(),1)
            ih=max(raw.height(),1)
            scale=min(w/iw,h/ih)
            dw=iw*scale
            dh=ih*scale
            painter.drawImage(QtCore.QRectF((w-dw)/2,(h-dh)/2,dw,dh),raw)
    finally:
        painter.end()
    return qimg


def _pixels(image):
    w,h=image.width(),image.height()
    return [(image.pixel(x,y)>>16&255,
             image.pixel(x,y)>>8&255,
             image.pixel(x,y)&255)
            for y in range(h) for x in range(w)]


def _fg_mask(pixels,w,h,threshold):
    """Treat the most common corner color as background, not artwork."""
    corners=[pixels[0],pixels[w-1],pixels[(h-1)*w],pixels[h*w-1]]
    bg=Counter(corners).most_common(1)[0][0]
    return bytearray(
        1 if max(abs(c[i]-bg[i]) for i in range(3))>threshold else 0
        for c in pixels)


def _font_pixels(text,font_path,w,h):
    """Render the chosen TTF/OTF to a monochrome cutout mask."""
    fontid=QtGui.QFontDatabase.addApplicationFont(font_path)
    if fontid<0:
        raise ValueError('No se pudo cargar la tipografía TTF/OTF.')
    try:
        families=QtGui.QFontDatabase.applicationFontFamilies(fontid)
        font=QtGui.QFont(families[0] if families else '')
        font.setBold(False)
        font.setPixelSize(max(4,int(h*.8)))
        metrics=QtGui.QFontMetrics(font)
        while metrics.horizontalAdvance(text)>w and font.pixelSize()>4:
            font.setPixelSize(font.pixelSize()-1)
            metrics=QtGui.QFontMetrics(font)
        result=QtGui.QImage(w,h,QtGui.QImage.Format_ARGB32)
        result.fill(QtGui.QColor(255,255,255))
        painter=QtGui.QPainter(result)
        try:
            painter.setPen(QtGui.QColor(0,0,0))
            painter.setRenderHint(QtGui.QPainter.TextAntialiasing,True)
            painter.setFont(font)
            painter.drawText(QtCore.QRect(0,0,w,h),int(QtCore.Qt.AlignCenter),text)
        finally:
            painter.end()
        return bytearray(
            1 if (result.pixel(x,y)>>16&255)<140 else 0
            for y in range(h) for x in range(w))
    finally:
        QtGui.QFontDatabase.removeApplicationFont(fontid)


def prepare_inputs(cfg,source,extension,progress=None):
    """Do Qt painting/font loading on the GUI thread, then return raw masks.

    No Qt object is handed to the worker running the expensive pixel geometry.
    """
    settings=core.quality_settings(getattr(cfg, "quality_mode", "balanced"),
                                   cfg.width, cfg.height)
    scale=settings["scale"]
    w=max(64,round(cfg.width*scale))
    h=max(64,round(cfg.height*scale))
    margin=max(2,round(cfg.margin*scale))
    band=max(round((cfg.text_size+2*cfg.margin)*scale),round(h*.25))
    top_of_band=h-band
    art_h=top_of_band+round(2*scale)-margin
    art_w=w-2*margin
    if art_h<35 or art_w<35:
        raise ValueError("No hay sitio suficiente para silueta y nombre.")
    if progress:progress(8,"Preparando ilustración")
    digest=sha256(source).hexdigest()
    key=(digest,extension,art_w,art_h,round(scale,3))
    cached=_cached_art(key)
    image=None if cached is not None else _qt_image(source,extension,art_w,art_h)
    tw=max(5,w-2*margin)
    th=max(5,band-2*margin)
    if progress:progress(17,"Preparando fuente y texto")
    letters=_font_pixels(cfg.text,cfg.font_path,tw,th)
    return dict(scale=scale,w=w,h=h,margin=margin,top_of_band=top_of_band,
                art_h=art_h,art_w=art_w,cache_key=key,cached=cached,
                image=image,letters=letters,text_w=tw,text_h=th)


def build_masks(cfg,prepared,progress=None):
    """Heavy 2D raster/topology computation; optional OpenCL/AMD backend.

    Only OpenCV UMat operations use OpenCL. CAD always runs after this on the
    FreeCAD GUI thread. If unavailable or slower in practice, choose CPU.
    """
    from time import perf_counter
    from .gpu_accel import ImageAccelerator, cpu_morph
    from . import crash_diagnostics
    started=perf_counter()
    preference=getattr(cfg,"compute_backend","auto")
    if os.environ.get("RSM_NAMEFORGE_SAFE_MODE")=="1":
        preference="cpu"
    crash_diagnostics.checkpoint("worker:accelerator",backend=preference)
    accelerator=ImageAccelerator(preference)
    timings={}
    scale=prepared["scale"]
    w,h=prepared["w"],prepared["h"]
    margin=prepared["margin"]
    top_of_band=prepared["top_of_band"]
    art_h,art_w=prepared["art_h"],prepared["art_w"]
    cached=prepared.get("cached")
    if cached is not None:
        ink0,outer=cached
        if progress:progress(30,"Reutilizando silueta ya procesada")
    else:
        if progress:progress(20,"Analizando píxeles de la imagen")
        ink0=accelerator.image_mask(prepared["image"], _image_to_mask)
        if progress:progress(23,"Calculando contorno exterior")
        closed=accelerator.morph(ink0,art_w,art_h,max(1,round(1.3*scale)),
                                 "close",cpu_morph)
        filled=core.fill_holes(closed,art_w,art_h)
        outer=accelerator.morph(
            core.keep_largest(filled,art_w,art_h),
            art_w,art_h,max(1,round(1.0*scale)),"dilate",cpu_morph)
        _remember_art(prepared["cache_key"],ink0,outer)
    timings["silhouette_s"]=round(perf_counter()-started,3)
    if not any(outer):
        raise ValueError("La imagen no tiene una silueta reconocible.")
    # A black cat/logo is a solid silhouette with white windows. Manga
    # line-art is the inverse: dark strokes should become perforations.
    # Treating both as line art used to cut away nearly the entire cat.
    art_style,ink_coverage=core.classify_artwork(
        ink0,outer,art_w,art_h)
    if progress:
        progress(35,"Arte: "+(
            "silueta negra" if art_style=="silhouette" else "ilustración de líneas"))
    rows=[y for y in range(art_h)
          if any(outer[y*art_w:(y+1)*art_w])]
    lower=max(rows)
    # Create a deliberate >=5 mm overlap with the nameplate: a point-like
    # junction produces fragile prints and ambiguous exterior vector loops.
    overlap=max(round(5.0*scale),round(cfg.bridge_width*scale*2.5))
    dy=top_of_band+overlap-margin-lower
    canvas=bytearray(w*h)
    picture=bytearray(w*h)
    for y in range(art_h):
        yy=y+margin+dy
        if 0<=yy<h:
            o=y*art_w
            d=yy*w+margin
            canvas[d:d+art_w]=outer[o:o+art_w]
            picture[d:d+art_w]=ink0[o:o+art_w]
    for y in range(top_of_band,h):
        canvas[y*w:(y+1)*w]=b"\x01"*w
    if progress:progress(40,"Abriendo detalles interiores")
    within=accelerator.morph(
        canvas,w,h,max(1,round(1.5*scale)),"erode",cpu_morph)
    if art_style=="silhouette":
        # Keep black filled material and perforate white *negative spaces*:
        # eyes, ear insets, bowtie and intentional body highlights.
        cut=bytearray(
            1 if within[i] and not picture[i] and i//w<top_of_band else 0
            for i in range(w*h))
    else:
        # Manga/engraving style: the dark linework is the opening.
        detail=accelerator.morph(
            picture,w,h,max(1,round(.32*scale)),"open",cpu_morph)
        cut=bytearray(
            1 if detail[i] and within[i] and i//w<top_of_band else 0
            for i in range(w*h))
    cut,discarded_cutouts=core.clean_tiny_cutouts(
        cut,w,h,max(2,round(.18*scale*scale)))
    if progress:progress(58,"Calando el nombre en el frente")
    tw,th=prepared["text_w"],prepared["text_h"]
    letters=prepared["letters"]
    for y in range(th):
        dst=(top_of_band+margin+y)*w+margin
        if dst+tw<=w*h:
            for x in range(tw):
                if letters[y*tw+x]:
                    cut[dst+x]=1
    material=bytearray(
        1 if canvas[i] and not cut[i] else 0
        for i in range(w*h))
    if progress:progress(70,"Conectando centros de letras")
    connected,bridges,removed=core.connect_islands(
        material,canvas,w,h,
        max(1,round(cfg.bridge_width*scale/2)),
        min_island=max(2,round(.2*scale*scale)))
    if progress:progress(79,"Reparando contornos")
    connected,front_diagonals=core.repair_diagonal_contacts(connected,w,h)
    # Rear shape must originate from the main silhouette + rectangular name
    # plate, not from the detailed front. Stencil bridges may close exterior
    # pockets; filling their holes used to generate diagonal rear wedges.
    rear_mask=core.solid_rear_envelope(canvas,w,h)
    # The cavity is offset *inside the very same rear silhouette*. It no
    # longer depends on a separately sampled exterior frame boundary. One
    # outer solid minus this inset cavity is always the same physical shell.
    cavity=accelerator.morph(
        rear_mask,w,h,max(1,round(3.0*scale)),"erode",cpu_morph)
    # Remove microscopic closed pockets before asking OCC to cut them out.
    min_cavity=max(2,int(3.0*scale*scale))
    cavity_clean=bytearray(w*h)
    for region in core.connected_components(cavity,w,h,min_area=min_cavity):
        for pixel in region:
            cavity_clean[pixel]=1
    cavity=cavity_clean
    if not any(cavity):
        raise ValueError(
            "La silueta es demasiado estrecha para una cavidad LED de 3 mm. "
            "Aumenta el tamaño de la lámpara.")
    frame=bytearray(
        1 if rear_mask[i] and not cavity[i] else 0
        for i in range(w*h))
    frame_bridges=0
    frame_diagonals=0
    timings["mask_and_bridges_s"]=round(perf_counter()-started-
                                        timings["silhouette_s"],3)
    if progress:progress(82,"Vectorizando contornos a precisión subpíxel")
    crash_diagnostics.checkpoint("worker:vector-tracing")
    from .vector_trace import trace_or_fallback
    from . import vtracer_adapter
    mode=getattr(cfg,"quality_mode","balanced")
    backend=getattr(cfg,"vector_backend","auto")
    if os.environ.get("RSM_NAMEFORGE_SAFE_MODE")=="1":
        backend="builtin"
    vector_errors={}
    # VTracer can be unavailable inside NixOS Flatpak even when installed
    # on the host. Only attempt its isolated helper once after a failure.
    external_failed=False

    def vectorize(mask,name):
        nonlocal external_failed
        if backend!="builtin" and mode!="fast" and not external_failed:
            crash_diagnostics.checkpoint("worker:vtracer-start",part=name)
            try:
                traced,replaced,total=vtracer_adapter.trace(mask,w,h,mode)
                crash_diagnostics.checkpoint("worker:vtracer-ok",
                                             part=name,rings=replaced)
                return traced,("VTracer %d/%d"%(replaced,total))
            except Exception as exc:
                external_failed=True
                vector_errors[name]="%s: %s"%(type(exc).__name__,str(exc)[:180])
                crash_diagnostics.checkpoint("worker:vtracer-fallback",
                                             part=name,error=type(exc).__name__)
        return trace_or_fallback(mask,w,h,mode)

    front_paths,front_trace=vectorize(connected,"front")
    rear_paths,rear_trace=vectorize(rear_mask,"rear")
    cavity_paths,cavity_trace=vectorize(cavity,"cavity")
    paths={
        "front_paths": front_paths,
        "rear_paths": rear_paths,
        "cavity_paths": cavity_paths,
        "vector_backend_requested": backend,
        "vector_fallbacks": vector_errors,
        "trace_methods": {
            "front": front_trace,
            "rear": rear_trace,
            "cavity": cavity_trace,
        },
    }
    if mode!="fast":
        from .curve_fit import spline_spans
        paths.update({
            "front_splines": [spline_spans(r) for r in front_paths],
            "rear_splines": [spline_spans(r) for r in rear_paths],
            "cavity_splines": [spline_spans(r) for r in cavity_paths],
        })
    timings["total_preparation_s"]=round(perf_counter()-started,3)
    timings["contours_s"]=round(timings["total_preparation_s"]-
                               timings["silhouette_s"]-
                               timings["mask_and_bridges_s"],3)
    timings.update(accelerator.timings)
    if progress:
        progress(85,"Trazado %s · %s" % (front_trace,accelerator.backend))
    crash_diagnostics.checkpoint("worker:vector-complete",
                                front_rings=len(front_paths),
                                rear_rings=len(rear_paths),
                                cavity_rings=len(cavity_paths))
    return dict(pixels=(w,h),bridges=bridges+frame_bridges,
                removed_islands=removed,front_mask=connected,
                frame_mask=frame,rear_mask=rear_mask,cavity_mask=cavity,
                scale=scale,
                diagonal_repairs=front_diagonals+frame_diagonals,
                artwork=dict(style=art_style,ink_density=round(ink_coverage,3),
                             removed_cutouts=discarded_cutouts),
                acceleration=dict(backend=accelerator.backend,
                                  detail=accelerator.detail,
                                  requested=accelerator.requested),
                timings=timings,**paths)


def prepare_mask(cfg,source,extension,progress=None):
    """Compatibility API with explicit, optional SVG diagnostic previews."""
    prepared=prepare_inputs(cfg,source,extension,progress)
    meta=build_masks(cfg,prepared,progress)
    w,h=meta["pixels"]
    rings=core.contours(meta["front_mask"],w,h,tolerance=.85,
                        min_area=meta["scale"]**2*.5)
    frame_rings=core.contours(meta["frame_mask"],w,h,tolerance=.85,
                              min_area=meta["scale"]**2*.6)
    return (core.to_svg(rings,w,h,meta["scale"]),
            core.to_svg(frame_rings,w,h,meta["scale"]),meta)


def _spline_tolerance(pixels_per_mm):
    """Maximum allowed geometric deviation for a smooth fitted CAD curve.

    Always far smaller than the 1.0 mm minimum support bridge and bounded in
    physical units so making a lamp bigger does not round away extra detail.
    """
    return max(0.035,min(0.20,0.78/float(pixels_per_mm)))


def _spline_wire(spans,w,h,pixels_per_mm):
    """Approximate jagged pixels instead of interpolating every pixel corner.

    Critically, BSplineCurve.interpolate() passes THROUGH each sample and
    therefore faithfully reproduces pixel stair-steps. approximate() fits a
    C1 curve within a measured geometric error. The endpoints are connected
    back to the exact planned vertices so all wires are watertight. Deliberate
    tips and nameplate corners are kept by the precomputed spline spans.
    """
    import FreeCAD as App
    import Part
    tol=_spline_tolerance(pixels_per_mm)
    edges=[]
    for span in spans:
        vectors=[App.Vector(float(x)/pixels_per_mm,
                            float(h-y)/pixels_per_mm,0)
                 for x,y in span]
        if len(vectors)<6:
            edges.extend(Part.makePolygon(vectors).Edges)
            continue
        try:
            spline=Part.BSplineCurve()
            spline.approximate(Points=vectors,DegMin=3,DegMax=5,
                               Continuity="C1",Tolerance=tol)
            fitted=spline.toShape()
            first=fitted.Vertexes[0].Point
            last=fitted.Vertexes[-1].Point
            if first.distanceToPoint(vectors[0])>tol*1.75 or (
                    last.distanceToPoint(vectors[-1])>tol*1.75):
                raise ValueError("La curva suavizada se alejó del trazo")
            if first.distanceToPoint(vectors[0])>1e-6:
                edges.append(Part.makeLine(vectors[0],first))
            edges.append(fitted)
            if last.distanceToPoint(vectors[-1])>1e-6:
                edges.append(Part.makeLine(last,vectors[-1]))
        except Exception:
            # A degenerate or very straight span should not invalidate the
            # entire engraving; retain this one as a trustworthy polyline.
            edges.extend(Part.makePolygon(vectors).Edges)
    wire=Part.Wire(edges)
    if not wire.isClosed() or not wire.isValid():
        raise ValueError("La curva B-spline no quedó cerrada")
    return wire


def _to_part(mask,w,h,pixels_per_mm,label,paths=None,splines=None):
    """Build faces with true CAD curves; fall back to printable polygons.

    All subpaths are guaranteed closed before Part::FaceMakerBullseye
    assigns interior islands and cut-through letter counters as holes.
    """
    import FreeCAD as App
    import Part
    from . import crash_diagnostics
    errors=[]
    candidates=[]
    if paths is not None and splines is not None:
        candidates.append(("curvas CAD",paths,splines))
    if paths is not None:
        candidates.append(("polígono preparado",paths,None))
    candidates.extend((str(t),None,None) for t in (.85,.25,0.0))
    for attempt,rings,plans in candidates:
        crash_diagnostics.checkpoint("cad:face-attempt",
                                     name=label,method=attempt)
        try:
            if rings is None:
                rings=core.contours(mask,w,h,tolerance=float(attempt),
                                    min_area=(pixels_per_mm**2)*.5)
            if plans is not None and len(plans)!=len(rings):
                raise ValueError("Plan de curvas incompleto")
            wires=[]
            for index,ring in enumerate(rings):
                if len(ring)<3:
                    continue
                if plans is not None:
                    try:
                        wire=_spline_wire(plans[index],w,h,pixels_per_mm)
                    except Exception:
                        # An invalid micro-detail must not force the entire
                        # artwork back to jagged polygons. Keep real fitted
                        # curves for all other printable contour rings.
                        vectors=[App.Vector(float(x)/pixels_per_mm,
                                            float(h-y)/pixels_per_mm,0)
                                 for x,y in ring]
                        wire=Part.Wire(
                            Part.makePolygon(vectors+[vectors[0]]).Edges)
                else:
                    vectors=[App.Vector(float(x)/pixels_per_mm,
                                        float(h-y)/pixels_per_mm,0)
                             for x,y in ring]
                    poly=Part.makePolygon(vectors+[vectors[0]])
                    wire=Part.Wire(poly.Edges)
                if not wire.isClosed() or not wire.isValid():
                    raise ValueError("Contorno %d inválido"%(index+1))
                wires.append(wire)
            if not wires:
                raise ValueError("No hay contornos imprimibles")
            crash_diagnostics.checkpoint("cad:part-makeface",
                                         name=label,wires=len(wires),
                                         method=attempt)
            face=Part.makeFace(wires,"Part::FaceMakerBullseye")
            if face.isNull() or not face.Faces or not face.isValid():
                raise ValueError("No se pudo cerrar la cara con huecos")
            crash_diagnostics.checkpoint("cad:face-valid",name=label)
            if plans is not None or splines is not None:
                # Allows diagnosing a rejected smooth contour without
                # exposing the user to a failed build.
                try:
                    App.Console.PrintMessage(
                        "RS Maker NameForge | %s: %s\\n" % (label,attempt))
                except (AttributeError,TypeError):
                    pass
            return face
        except Exception as exc:
            errors.append("%s: %s"%(attempt,exc))
    raise ValueError(
        "No se pudo cerrar %s. Prueba aumentar el puente o el tamaño del "
        "diseño. Detalle de tolerancias: %s"%(label,"; ".join(errors)))


def _closed_back_housing(meta,w,h,scale,cfg,front_thickness=2.0,
                         rear_thickness=2.0,progress=None,robust=False):
    """One watertight body, milled open from one outer extrusion.

    The previous rear.fuse(frame) could return two solids because the two
    masks had separately smoothed boundaries. The new housing can never
    lose contact between the rear and the frame: both originate from the
    exact same outer solid. A 3-mm inward inset cuts the LED cavity down
    to the 2-mm solid back, leaving the top open for the removable front.
    """
    import FreeCAD as App
    import Part
    from . import crash_diagnostics
    height=cfg.depth-front_thickness
    cavity_depth=height-rear_thickness
    if cavity_depth<4.0:
        raise ValueError("La lámpara necesita espacio para LED y fondo.")
    failures=[]
    for smooth in (True,False):
        try:
            rear_face=_to_part(
                meta["rear_mask"],w,h,scale,"perímetro de carcasa",
                meta.get("rear_paths") if smooth else None,
                meta.get("rear_splines") if smooth and not robust else None)
            cavity_mask=meta.get("cavity_mask")
            if cavity_mask is None:
                # Compatibility when editing projects generated before this
                # mask was included in the worker's output.
                cavity_mask=core.morph(meta["rear_mask"],w,h,
                                      max(1,round(3.0*scale)),"erode")
            if not any(cavity_mask):
                raise ValueError("No quedó cavidad para los LED.")
            inset_face=_to_part(
                cavity_mask,w,h,scale,"cavidad interior",
                meta.get("cavity_paths") if smooth else None,
                meta.get("cavity_splines") if smooth and not robust else None)
            crash_diagnostics.checkpoint("cad:housing-extrude")
            outer_solid=rear_face.extrude(App.Vector(0,0,height))
            # Extend the tool beyond the top to make a clean, open cavity.
            tool=inset_face.extrude(App.Vector(0,0,cavity_depth+1.0))
            tool.translate(App.Vector(0,0,rear_thickness))
            crash_diagnostics.checkpoint("cad:housing-cut-cavity")
            housing=outer_solid.cut(tool)
            crash_diagnostics.checkpoint("cad:housing-cut-complete")
            bounds=housing.BoundBox
            port=Part.makeCylinder(
                2.5,rear_thickness+1.0,
                App.Vector(
                    (bounds.XMin+bounds.XMax)/2.0,
                    bounds.YMin+8.0,-0.5))
            crash_diagnostics.checkpoint("cad:housing-cut-cable")
            housing=housing.cut(port)
            try:
                housing=housing.removeSplitter()
            except Exception:
                pass
            if not housing.isValid() or len(housing.Solids)!=1:
                raise ValueError(
                    "El resultado tiene %d sólidos; la cavidad no es "
                    "válida." % len(housing.Solids))
            crash_diagnostics.checkpoint("cad:housing-valid")
            if progress:
                progress(96,"Carcasa integrada · "+(
                    ("polígonos subpíxel" if robust else "curvas CAD")
                    if smooth else "contornos seguros"))
            return housing
        except Exception as exc:
            failures.append(("curvas" if smooth else "seguro")+": "+str(exc))
    raise ValueError(
        "No se pudo crear la carcasa como un sólido único. "
        "Se intentaron curvas y contornos seguros. Detalles: "+
        "; ".join(failures))


def make_lamp(cfg,source,extension,progress=None,mask_meta=None):
    """Generate exactly two printable solids: front and solid-back housing."""
    import FreeCAD as App

    meta=mask_meta if mask_meta is not None else build_masks(
        cfg,prepare_inputs(cfg,source,extension,progress),progress)
    w,h=meta["pixels"]
    scale=meta["scale"]
    from . import crash_diagnostics
    # Filled-black icons need continuous, reliable subpixel polygons: their
    # pupils and tiny counters can make OCC cubic approximation singular.
    # Converting those loops to CAD polygons keeps vectorized subpixel
    # coordinates while avoiding high-degree native spline fitting.
    robust=(meta.get("artwork",{}).get("style")=="silhouette" or
            os.environ.get("RSM_NAMEFORGE_SAFE_MODE")=="1")
    crash_diagnostics.checkpoint("cad:profile",
        profile="subpixel-polygons" if robust else "bspline")
    front_thickness=2.0
    if cfg.depth-front_thickness-2.0<4.0:
        raise ValueError("La lámpara necesita espacio para LED y fondo.")
    if progress:progress(86,"Construyendo frontal y carcasa monolítica")
    front=_to_part(
        meta["front_mask"],w,h,scale,"frente",
        meta.get("front_paths"),
        None if robust else meta.get("front_splines")).extrude(
            App.Vector(0,0,front_thickness))
    front.translate(App.Vector(0,0,cfg.depth-front_thickness))
    housing=_closed_back_housing(meta,w,h,scale,cfg,
                                 front_thickness=front_thickness,
                                 rear_thickness=2.0,progress=progress,
                                 robust=robust)
    if not front.isValid() or len(front.Solids)!=1:
        raise ValueError(
            "El frente calado no es una sola pieza imprimible. "
            "Revisa el ancho de los puentes.")
    if progress:progress(98,"Frontal y carcasa monolítica listos")
    return [
        ("nameforge_frente","Frente de silueta · nombre calado",
         front,(.94,.94,.94)),
        ("nameforge_marco","Carcasa monolítica · fondo integrado",
         housing,(.20,.25,.34))]


def optimize_svg(source,extension,colors=8,progress=None):
    """Convert raster art or complex SVG to a smaller flat-palette SVG."""
    colors=max(2,min(16,int(colors)))
    image=_qt_image(source,extension,420,420)
    w,h=image.width(),image.height()
    pixels=_pixels(image)
    sample=pixels[::max(1,len(pixels)//2500)]
    # Deterministic farthest-color seeding and several Lloyd iterations.
    centers=[(255,255,255)]
    for _ in range(colors-1):
        p=max(
            sample,key=lambda rgb:min(
                sum((rgb[i]-c[i])**2 for i in range(3))
                for c in centers))
        if p in centers:
            break
        centers.append(p)
    for _ in range(5):
        totals=[[0,0,0,0] for _ in centers]
        for rgb in sample:
            i=min(
                range(len(centers)),
                key=lambda k:sum(
                    (rgb[j]-centers[k][j])**2 for j in range(3)))
            row=totals[i]
            row[0]+=rgb[0]
            row[1]+=rgb[1]
            row[2]+=rgb[2]
            row[3]+=1
        centers=[
            tuple(int(round(row[i]/row[3])) for i in range(3))
            if row[3] else centers[k]
            for k,row in enumerate(totals)]
    masks=[bytearray(w*h) for _ in centers]
    for index,rgb in enumerate(pixels):
        ci=min(
            range(len(centers)),
            key=lambda k:sum(
                (rgb[j]-centers[k][j])**2 for j in range(3)))
        masks[ci][index]=1
    bg=min(
        range(len(centers)),
        key=lambda k:sum((255-v)**2 for v in centers[k]))
    paths=[]
    for i,(color,mask) in enumerate(zip(centers,masks)):
        if i==bg:
            continue
        if progress:
            progress(
                20+55*i/len(centers),
                'Simplificando color %d de %d' %(i+1,len(centers)))
        simplified=core.open_mask(mask,w,h,1)
        loops=core.contours(
            simplified,w,h,tolerance=.65,min_area=5)
        if loops:
            d=' '.join(
                'M '+' L '.join('%s,%s'%p for p in loop)+' Z'
                for loop in loops)
            paths.append(
                '<path fill="#%02x%02x%02x" fill-rule="evenodd" d="%s"/>' %
                (*color,d))
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="%s" height="%s" '
        'viewBox="0 0 %s %s">\n%s\n</svg>\n'%
        (w,h,w,h,'\n'.join(paths)))
