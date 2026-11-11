"""RS Maker NameForge — silhouette lightbox from SVG, PNG, JPG or WebP.

QtSvg/QImage rasterization handles complex source art without requiring OpenCV,
Pillow or external vectorizers inside FreeCAD. A print-safe stencil mask is
then converted to a compact, editable BRep with true holes and text bridges.
"""
import os
import tempfile
from collections import Counter

from . import stencil_core as core

try:
    from PySide import QtCore, QtGui, QtSvg
except ImportError:
    try:
        from PySide6 import QtCore, QtGui, QtSvg
    except ImportError:
        from PySide2 import QtCore, QtGui, QtSvg


_FORMATS=('.svg','.png','.jpg','.jpeg','.webp','.bmp')


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


def prepare_mask(cfg,source,extension,progress=None):
    """Generate connected front and contour-following frame SVGs.

    The front is a single mask: all letters/details are real through-cuts,
    while disconnected glyph centers become manufacturable bridges.
    """
    scale=max(1.6,min(4.0,1300/max(cfg.width,cfg.height)))
    w=max(64,round(cfg.width*scale))
    h=max(64,round(cfg.height*scale))
    margin=max(2,round(cfg.margin*scale))
    band=max(round((cfg.text_size+2*cfg.margin)*scale),round(h*.25))
    top_of_band=h-band
    art_h=top_of_band+round(2*scale)-margin
    art_w=w-2*margin
    if art_h<35 or art_w<35:
        raise ValueError('No hay sitio suficiente para silueta y nombre.')

    if progress:progress(8,'Rasterizando ilustración para silueta')
    sourceimg=_qt_image(source,extension,art_w,art_h)
    ink0=_fg_mask(_pixels(sourceimg),art_w,art_h,45)
    if progress:progress(23,'Calculando contorno exterior')
    closed=core.close(ink0,art_w,art_h,max(1,round(1.3*scale)))
    filled=core.fill_holes(closed,art_w,art_h)
    outer=core.morph(
        core.keep_largest(filled,art_w,art_h),
        art_w,art_h,max(1,round(1.0*scale)),'dilate')
    if not any(outer):
        raise ValueError('La imagen no tiene una silueta reconocible.')

    rows=[y for y in range(art_h)
          if any(outer[y*art_w:(y+1)*art_w])]
    lower=max(rows)
    # Ensure 2 mm overlap between artwork and the solid nameplate.
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
        canvas[y*w:(y+1)*w]=b'\x01'*w

    # Preserve a solid border around each aperture to avoid hairline tips.
    if progress:progress(40,'Abriendo detalles interiores')
    within=core.morph(
        canvas,w,h,max(1,round(1.5*scale)),'erode')
    detail=core.open_mask(
        picture,w,h,max(1,round(.32*scale)))
    cut=bytearray(
        1 if detail[i] and within[i] and i//w<top_of_band else 0
        for i in range(w*h))

    if progress:progress(58,'Calando el nombre en el frente')
    tw=max(5,w-2*margin)
    th=max(5,band-2*margin)
    letters=_font_pixels(cfg.text,cfg.font_path,tw,th)
    for y in range(th):
        dst=(top_of_band+margin+y)*w+margin
        if dst+tw<=w*h:
            for x in range(tw):
                if letters[y*tw+x]:
                    cut[dst+x]=1
    material=bytearray(
        1 if canvas[i] and not cut[i] else 0
        for i in range(w*h))

    if progress:progress(70,'Conectando centros de letras con puentes')
    connected,bridges,removed=core.connect_islands(
        material,canvas,w,h,
        max(1,round(cfg.bridge_width*scale/2)),
        min_island=max(2,round(.2*scale*scale)))
    if progress:progress(80,'Vectorizando máscara y marco')
    rings=core.contours(
        connected,w,h,tolerance=.85,min_area=scale*scale*.5)

    inner=core.morph(
        canvas,w,h,max(1,round(3.0*scale)),'erode')
    frame=bytearray(
        1 if canvas[i] and not inner[i] else 0
        for i in range(w*h))
    frame,frame_bridges,_=core.connect_islands(
        frame,canvas,w,h,max(1,round(scale)),min_island=2)
    frame_rings=core.contours(
        frame,w,h,tolerance=.85,min_area=scale*scale*.6)
    return (
        core.to_svg(rings,w,h,scale),
        core.to_svg(frame_rings,w,h,scale),
        dict(pixels=(w,h),bridges=bridges+frame_bridges,
             removed_islands=removed,paths=len(rings)))


def _to_part(svg_text,doc):
    """Import the low-path-count optimized SVG as a FreeCAD planar face."""
    import importSVG
    import Part
    from .relief import _faces
    path=None
    before={obj.Name for obj in doc.Objects}
    try:
        with tempfile.NamedTemporaryFile(
                mode='w',encoding='utf-8',suffix='.svg',
                delete=False) as stream:
            stream.write(svg_text)
            path=stream.name
        importSVG.insert(path,doc.Name)
        doc.recompute()
        shapes=[]
        for obj in doc.Objects:
            if (obj.Name in before or not hasattr(obj,'Shape')
                    or obj.Shape.isNull()):
                continue
            shapes.extend(_faces(obj.Shape))
        if not shapes:
            raise ValueError('La máscara vectorial no produjo caras en FreeCAD.')
        return Part.makeCompound(shapes) if len(shapes)>1 else shapes[0]
    finally:
        if path and os.path.exists(path):
            os.unlink(path)


def make_lamp(cfg,source,extension,progress=None):
    """Return two valid BReps: perforated front and silhouette-shaped frame."""
    import FreeCAD as App
    import Part

    facade,wall,meta=prepare_mask(cfg,source,extension,progress)
    if progress:progress(88,'Construyendo frontal y marco en FreeCAD')
    old=App.ActiveDocument
    doc=App.newDocument('RSNameForgeStencil')
    try:
        front=_to_part(facade,doc).extrude(App.Vector(0,0,2.0))
        front.translate(App.Vector(0,0,cfg.depth-2.0))
        frame=_to_part(wall,doc).extrude(
            App.Vector(0,0,cfg.depth-2.0))
        bounds=frame.BoundBox
        # Cable opening at the lower edge of the plaque.
        notch=Part.makeBox(
            5.5,5.0,3.0,
            App.Vector(
                (bounds.XMin+bounds.XMax)/2-2.75,
                bounds.YMin-1.0,0))
        frame=frame.cut(notch)
        for shape,label in ((front,'frente'),(frame,'marco')):
            if not shape.isValid() or len(shape.Solids)!=1:
                raise ValueError(
                    'El %s no es una sola pieza imprimible; '
                    'ajusta puente, tamaño o detalle.'%label)
        if progress:progress(98,'Frente con nombre calado listo')
        return [
            ('nameforge_frente',
             'Frente silueta · nombre y detalles calados',
             front,(.94,.94,.94)),
            ('nameforge_marco',
             'Marco siguiendo silueta · iluminación',
             frame,(.20,.25,.34))]
    finally:
        App.closeDocument(doc.Name)
        if old:
            App.setActiveDocument(old.Name)


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
