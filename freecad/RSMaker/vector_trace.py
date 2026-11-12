"""Subpixel isocontour tracer for printable monochrome line art.

This is a dependency-free marching-squares tracer on a lightly filtered,
supersampled occupancy field, not the pixel-corner polygon tracer used for
legacy fast mode. It preserves closed outer/inner boundaries, detects
ambiguous cells, and rejects topology changes instead of losing letter
counters. All calculations are safe on the NameForge background QThread.
"""
from math import floor
from . import stencil_core as core

# Grid corners order: northwest, northeast, southeast, southwest.
_PAIRS = {
    0: (), 1: ((3,0),), 2: ((0,1),), 3: ((3,1),),
    4: ((1,2),), 5: ((3,0),(1,2)), 6: ((0,2),),
    7: ((3,2),), 8: ((2,3),), 9: ((0,2),),
    10: ((0,1),(2,3)), 11: ((1,2),), 12: ((1,3),),
    13: ((0,1),), 14: ((3,0),), 15: ()
}
_THRESHOLD = 8.05  # 3x3 binomial-filtered occupancy ranges from 0 to 16.


def _blurred(mask,w,h):
    """3×3 separable binomial filter with one outside padding pixel.

    Integer arithmetic ensures neighboring cells calculate *identical*
    subpixel intersections, so closing a traced path does not depend on
    floating point coordinate equality.
    """
    core._validate(mask,w,h)
    pw=w+2
    ph=h+2
    source=bytearray(pw*ph)
    for y in range(h):
        i=(y+1)*pw+1
        source[i:i+w]=mask[y*w:(y+1)*w]
    horizontal=bytearray(pw*ph)
    for y in range(1,ph-1):
        offset=y*pw
        for x in range(1,pw-1):
            i=offset+x
            horizontal[i]=source[i-1]+2*source[i]+source[i+1]
    field=bytearray(pw*ph)
    for y in range(1,ph-1):
        offset=y*pw
        for x in range(1,pw-1):
            i=offset+x
            field[i]=horizontal[i-pw]+2*horizontal[i]+horizontal[i+pw]
    return field,pw,ph


def _edge_key(x,y,edge):
    # Canonical identifiers are shared by both squares touching an edge.
    if edge==0:
        return (0,x,y)
    if edge==1:
        return (1,x+1,y)
    if edge==2:
        return (0,x,y+1)
    return (1,x,y)


def _point(key,field,pw):
    direction,x,y=key
    if direction==0:  # horizontal grid edge
        a,b=field[y*pw+x],field[y*pw+x+1]
        t=(_THRESHOLD-a)/(b-a)
        return (x+t-.5, y-.5)
    a,b=field[y*pw+x],field[(y+1)*pw+x]
    t=(_THRESHOLD-a)/(b-a)
    return (x-.5,y+t-.5)


def _orient_material_right(ring,mask,w,h):
    """Match core.contours winding: solid material to each wire's right."""
    n=len(ring)
    for i in range(n):
        p=ring[i]
        q=ring[(i+1)%n]
        dx,dy=q[0]-p[0],q[1]-p[1]
        length=(dx*dx+dy*dy)**.5
        if length<.2:
            continue
        nx,ny=-dy/length,dx/length
        mx,my=(p[0]+q[0])*.5,(p[1]+q[1])*.5
        for delta in (.42,.65,.9):
            rx,ry=floor(mx+delta*nx),floor(my+delta*ny)
            lx,ly=floor(mx-delta*nx),floor(my-delta*ny)
            right=bool(0<=rx<w and 0<=ry<h and mask[ry*w+rx])
            left=bool(0<=lx<w and 0<=ly<h and mask[ly*w+lx])
            if right!=left:
                return ring if right else list(reversed(ring))
    return ring


def subpixel_contours(mask,w,h,tolerance=.65,min_area=.5,
                      validate_topology=True):
    """Trace filtered mask at a continuous subpixel level.

    Reject if the filter merges or splits rings, or if a wire does not close.
    The caller should then use core.contours (safe legacy polygon mode).
    """
    field,pw,ph=_blurred(mask,w,h)
    adjacency={}
    for y in range(ph-1):
        row=y*pw
        for x in range(pw-1):
            i=row+x
            a,b,c,d=field[i],field[i+1],field[i+pw+1],field[i+pw]
            state=(int(a>_THRESHOLD) |
                   int(b>_THRESHOLD)<<1 |
                   int(c>_THRESHOLD)<<2 |
                   int(d>_THRESHOLD)<<3)
            for e0,e1 in _PAIRS[state]:
                k0=_edge_key(x,y,e0)
                k1=_edge_key(x,y,e1)
                adjacency.setdefault(k0,[]).append(k1)
                adjacency.setdefault(k1,[]).append(k0)
    if not adjacency:
        raise ValueError("No quedan contornos después del trazado.")
    if any(len(other)!=2 for other in adjacency.values()):
        raise ValueError("La vectorización produjo un contorno ramificado.")
    visited=set()
    rings=[]
    for start in adjacency:
        if start in visited:
            continue
        ring=[]
        previous=None
        current=start
        while True:
            if current in visited:
                if current!=start:
                    raise ValueError("El trazado regresó a un vértice incorrecto.")
                break
            visited.add(current)
            ring.append(_point(current,field,pw))
            choices=adjacency[current]
            nxt=choices[0] if choices[0]!=previous else choices[1]
            previous,current=current,nxt
        if len(ring)<4 or abs(core.polygon_area(ring))<min_area:
            continue
        if tolerance>0:
            reduced=core._rdp(ring+[ring[0]],tolerance)
            if reduced[-1]==reduced[0]:
                reduced.pop()
            if len(reduced)>=3:
                ring=reduced
        ring=_orient_material_right(ring,mask,w,h)
        rings.append(ring)
    if validate_topology:
        original=core.contours(mask,w,h,tolerance=0,min_area=min_area)
        if len(rings)!=len(original):
            raise ValueError(
                "El suavizado alteraría los huecos o la silueta (%d vs %d); "
                "se conservará el contorno seguro."
                % (len(rings),len(original)))
        positives=sum(core.polygon_area(loop)>0 for loop in rings)
        negatives=len(rings)-positives
        orig_positive=sum(core.polygon_area(loop)>0 for loop in original)
        if positives!=orig_positive or negatives!=(len(original)-orig_positive):
            raise ValueError("El trazado cambiaría la orientación de los huecos.")
    return rings


def trace_or_fallback(mask,w,h,mode):
    """Specialized line-art tracing; conservative polygons if unsafe.

    Fast mode intentionally uses cheap polygons. Balance/high modes try
    subpixel contours without importing OpenCV, Pillow or an external binary.
    """
    if mode=="fast":
        return core.cleaned_contours(mask,w,h,mode),"rápido"
    tolerance=.85 if mode=="balanced" else .52
    try:
        rings=subpixel_contours(mask,w,h,tolerance=tolerance)
        if not rings:
            raise ValueError("No hay anillos")
        return rings,"subpíxel"
    except (ValueError,IndexError,KeyError,ZeroDivisionError):
        return core.cleaned_contours(mask,w,h,mode),"respaldo poligonal"
