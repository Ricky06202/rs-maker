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
    """Heavy 2D raster/topology computation. Pure Python, safe on worker."""
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
        ink0=_image_to_mask(prepared["image"])
        if progress:progress(23,"Calculando contorno exterior")
        closed=core.close(ink0,art_w,art_h,max(1,round(1.3*scale)))
        filled=core.fill_holes(closed,art_w,art_h)
        outer=core.morph(
            core.keep_largest(filled,art_w,art_h),
            art_w,art_h,max(1,round(1.0*scale)),"dilate")
        _remember_art(prepared["cache_key"],ink0,outer)
    if not any(outer):
        raise ValueError("La imagen no tiene una silueta reconocible.")
    rows=[y for y in range(art_h)
          if any(outer[y*art_w:(y+1)*art_w])]
    lower=max(rows)
    dy=top_of_band+round(2*scale)-margin-lower
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
    within=core.morph(
        canvas,w,h,max(1,round(1.5*scale)),"erode")
    detail=core.open_mask(
        picture,w,h,max(1,round(.32*scale)))
    cut=bytearray(
        1 if detail[i] and within[i] and i//w<top_of_band else 0
        for i in range(w*h))
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
    inner=core.morph(canvas,w,h,max(1,round(3.0*scale)),"erode")
    frame=bytearray(
        1 if canvas[i] and not inner[i] else 0
        for i in range(w*h))
    frame,frame_bridges,_=core.connect_islands(
        frame,canvas,w,h,max(1,round(scale)),min_island=2)
    frame,frame_diagonals=core.repair_diagonal_contacts(frame,w,h)
    rear_mask=core.fill_holes(connected,w,h)
    rear_mask,_=core.repair_diagonal_contacts(rear_mask,w,h)
    if len(core.connected_components(rear_mask,w,h))!=1:
        raise ValueError("La tapa trasera no conserva una silueta conectada.")
    if progress:progress(82,"Suavizando contornos fuera de la interfaz")
    mode=getattr(cfg,"quality_mode","balanced")
    paths={
        "front_paths": core.cleaned_contours(connected,w,h,mode),
        "frame_paths": core.cleaned_contours(frame,w,h,mode),
        "rear_paths": core.cleaned_contours(rear_mask,w,h,mode),
    }
    if progress:progress(85,"Contornos preparados para el modelo CAD")
    return dict(pixels=(w,h),bridges=bridges+frame_bridges,
                removed_islands=removed,front_mask=connected,
                frame_mask=frame,rear_mask=rear_mask,scale=scale,
                diagonal_repairs=front_diagonals+frame_diagonals,**paths)


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


def _to_part(mask,w,h,pixels_per_mm,label,paths=None):
    """Build watertight faces directly from raster boundary loops.

    The old importSVG round-trip placed many subpaths into one compound
    SVG path, which could lead to FreeCAD's 'Wire is not closed' exception.
    Native Part polygons explicitly repeat their starting vertex and
    Part::FaceMakerBullseye assigns nested loops as holes.
    """
    import FreeCAD as App
    import Part
    errors=[]
    # Preprocessed rings arrive from the background worker. Recompute a raw
    # fallback only if the CAD kernel rejects the prepared (smoothed) face.
    candidates=[]
    if paths is not None:
        candidates.append(("preparado",paths))
    candidates.extend((str(t),None) for t in (.85,.25,0.0))
    for attempt,rings in candidates:
        try:
            if rings is None:
                rings=core.contours(mask,w,h,tolerance=float(attempt),
                                    min_area=(pixels_per_mm**2)*.5)
            wires=[]
            for index,ring in enumerate(rings):
                if len(ring)<3:
                    continue
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
            face=Part.makeFace(wires,"Part::FaceMakerBullseye")
            if face.isNull() or not face.Faces or not face.isValid():
                raise ValueError("No se pudo cerrar la cara con huecos")
            return face
        except Exception as exc:
            errors.append("%s: %s"%(attempt,exc))
    raise ValueError(
        "No se pudo cerrar %s. Prueba aumentar el puente o el tamaño del "
        "diseño. Detalle de tolerancias: %s"%(label,"; ".join(errors)))


def make_lamp(cfg,source,extension,progress=None,mask_meta=None):
    """Generate two printable solids: cut-out front and closed-back housing.

    The rear cover and the perimeter frame share a contact surface and are
    fused into a single watertight housing. The separate front can be mounted
    after fitting the lighting components.
    """
    import FreeCAD as App
    import Part

    # Skip re-vectorization: the native Part faces are built from masks.
    meta=mask_meta if mask_meta is not None else build_masks(
        cfg,prepare_inputs(cfg,source,extension,progress),progress)
    w,h=meta["pixels"]
    scale=meta["scale"]
    front_thickness=2.0
    rear_thickness=2.0
    cavity_height=cfg.depth-front_thickness-rear_thickness
    if cavity_height<4.0:
        raise ValueError("La lámpara necesita espacio para LED y tapa trasera.")

    if progress:progress(86,"Suavizando contornos y cerrando la tapa trasera")
    front=_to_part(meta["front_mask"],w,h,scale,"frente",
                   meta.get("front_paths")).extrude(
        App.Vector(0,0,front_thickness))
    front.translate(App.Vector(0,0,cfg.depth-front_thickness))
    frame=_to_part(meta["frame_mask"],w,h,scale,"marco",
                   meta.get("frame_paths")).extrude(
        App.Vector(0,0,cavity_height))
    frame.translate(App.Vector(0,0,rear_thickness))
    rear=_to_part(meta["rear_mask"],w,h,scale,"tapa trasera",
                   meta.get("rear_paths")).extrude(
        App.Vector(0,0,rear_thickness))

    # Leave a small, explicitly bounded 5-mm exit for low-voltage LED wire.
    # This is a pass-through in the rear cover, not an open back.
    bounds=rear.BoundBox
    cable_x=(bounds.XMin+bounds.XMax)/2.0
    cable_y=bounds.YMin+8.0
    port=Part.makeCylinder(2.5,rear_thickness+1.0,
                           App.Vector(cable_x,cable_y,-0.5))
    rear=rear.cut(port)
    # The back and frame MUST form one printable part. Their coplanar joining
    # faces meet at Z=rear_thickness; a compound would leave two solids.
    housing=rear.fuse(frame)
    try:
        housing=housing.removeSplitter()
    except Exception:
        # removeSplitter is a cosmetic OCC operation: retaining a valid fused
        # housing is preferable to losing the entire model.
        pass
    for shape,label in ((front,"frente"),(housing,"carcasa con fondo integrado")):
        if not shape.isValid() or len(shape.Solids)!=1:
            raise ValueError(
                "El %s no es un sólido único imprimible; "
                "ajusta puente, tamaño o detalle."%label)
    if progress:progress(98,"Frente y carcasa trasera unidos, dos piezas listas")
    return [
        ("nameforge_frente","Frente de silueta · nombre calado",
         front,(.94,.94,.94)),
        ("nameforge_marco","Carcasa · marco y fondo integrados",
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
