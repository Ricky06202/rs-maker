"""Pure-Python mask analysis for printable NameForge lamp fronts.

No Pillow, NumPy, OpenCV or external tracer required in FreeCAD.
"""
from array import array
from collections import deque


def _validate(mask, w, h):
    if w < 1 or h < 1 or len(mask) != w*h:
        raise ValueError("Dimensiones incorrectas de la máscara")


def _rows(mask, w, h):
    return [sum((1 << x) for x, value in enumerate(mask[y*w:(y+1)*w]) if value)
            for y in range(h)]


def _from_rows(rows, w):
    result=bytearray(w*len(rows))
    for y,bits in enumerate(rows):
        while bits:
            low=bits & -bits
            x=low.bit_length()-1
            if x<w:
                result[y*w+x]=1
            bits ^= low
    return result


def morph(mask,w,h,radius,operation):
    """Dilate or erode with a square kernel using fast Python integer bitsets."""
    _validate(mask,w,h)
    if radius<=0:
        return bytearray(mask)
    r=int(radius)
    bound=(1<<w)-1
    src=_rows(mask,w,h)
    horizontal=[]
    for bits in src:
        out=bits
        for shift in range(1,r+1):
            if operation=='dilate':
                out |= (bits<<shift)|(bits>>shift)
            else:
                out &= ((bits<<shift)&bound)&(bits>>shift)
        horizontal.append(out&bound)
    vertical=[]
    for y in range(h):
        out=horizontal[y]
        for off in range(1,r+1):
            low=horizontal[y-off] if y-off>=0 else 0
            high=horizontal[y+off] if y+off<h else 0
            if operation=='dilate':
                out |= low|high
            else:
                out &= low&high
        vertical.append(out)
    return _from_rows(vertical,w)


def close(mask,w,h,radius):
    return morph(morph(mask,w,h,radius,'dilate'),w,h,radius,'erode')


def open_mask(mask,w,h,radius):
    return morph(morph(mask,w,h,radius,'erode'),w,h,radius,'dilate')


def neighbors(index,w,h):
    x=index%w
    y=index//w
    if x>0:yield index-1
    if x+1<w:yield index+1
    if y>0:yield index-w
    if y+1<h:yield index+w


def fill_holes(mask,w,h):
    """Fill background components not connected to image exterior."""
    _validate(mask,w,h)
    outside=bytearray(w*h)
    stack=deque()
    for x in range(w):
        for p in (x,(h-1)*w+x):
            if not mask[p] and not outside[p]:
                outside[p]=1
                stack.append(p)
    for y in range(h):
        for p in (y*w,y*w+w-1):
            if not mask[p] and not outside[p]:
                outside[p]=1
                stack.append(p)
    while stack:
        p=stack.popleft()
        for n in neighbors(p,w,h):
            if not mask[n] and not outside[n]:
                outside[n]=1
                stack.append(n)
    return bytearray(0 if outside[p] else 1 for p in range(w*h))


def connected_components(mask,w,h,min_area=1):
    """Four-connected filled components, largest first."""
    _validate(mask,w,h)
    found=bytearray(w*h)
    output=[]
    for start,value in enumerate(mask):
        if not value or found[start]:
            continue
        points=[]
        q=deque([start])
        found[start]=1
        while q:
            p=q.popleft()
            points.append(p)
            for n in neighbors(p,w,h):
                if mask[n] and not found[n]:
                    found[n]=1
                    q.append(n)
        if len(points)>=min_area:
            output.append(points)
    return sorted(output,key=len,reverse=True)


def keep_largest(mask,w,h):
    comps=connected_components(mask,w,h)
    if not comps:
        return bytearray(w*h)
    result=bytearray(w*h)
    for p in comps[0]:
        result[p]=1
    return result


def connect_islands(material,envelope,w,h,bridge_radius,min_island=2):
    """Insert supporting stencil bridges for counters and isolated islands.

    Multisource BFS from the main body connects islands with support paths.
    Reached islands become traversable portals to enclosed, nested cutouts
    without filling their material again. Tiny loose specks are discarded.
    """
    _validate(material,w,h)
    _validate(envelope,w,h)
    out=bytearray(material)
    components=connected_components(out,w,h)
    if not components:
        raise ValueError("No hay material suficiente para el frente")
    if len(components)==1:
        return out,0,0
    root=components[0]
    islands=[c for c in components[1:] if len(c)>=min_island]
    removed=0
    for comp in components[1:]:
        if len(comp)<min_island:
            for p in comp:out[p]=0
            removed+=1
    if not islands:
        return out,0,removed
    groups=array('i',[-1])*(w*h)
    for i,comp in enumerate(islands):
        for p in comp:groups[p]=i
    seen=bytearray(w*h)
    parent=array('i',[-1])*(w*h)
    q=deque()
    for p in root:
        for n in neighbors(p,w,h):
            if envelope[n] and not out[n] and not seen[n]:
                seen[n]=1
                parent[n]=p
                q.append(n)
    found={}
    while q and len(found)<len(islands):
        p=q.popleft()
        for n in neighbors(p,w,h):
            i=groups[n]
            if i>=0 and i not in found:
                found[i]=p
                # This island is now reachable by a supporting bridge.
                # Its own material is free to traverse, so expose the empty
                # regions on *all* its sides to the BFS. Without this portal,
                # nested cutouts (O inside R, multiple layered outlines, etc.)
                # become unreachable even though a manufacturable path exists.
                # Each blank pixel has only one BFS parent; passing across
                # solid island pixels requires no extra printed material.
                for member in islands[i]:
                    for beyond in neighbors(member,w,h):
                        if envelope[beyond] and not out[beyond] and not seen[beyond]:
                            seen[beyond]=1
                            parent[beyond]=p
                            q.append(beyond)
            if envelope[n] and not out[n] and not seen[n]:
                seen[n]=1
                parent[n]=p
                q.append(n)
    if len(found)!=len(islands):
        raise ValueError(
            "Hay islas fuera de la silueta conectada. "
            "Verifica que el dibujo y su base se toquen; "
            "aumentar el tamaño o el detalle no debería impedir conectar "
            "los huecos interiores.")
    guides=bytearray(w*h)
    for last in found.values():
        p=last
        while p>=0 and not out[p]:
            guides[p]=1
            p=parent[p]
    expanded=morph(guides,w,h,max(1,int(bridge_radius)),'dilate')
    for p,active in enumerate(expanded):
        if active and envelope[p]:
            out[p]=1
    if len(connected_components(out,w,h))!=1:
        raise ValueError("El frente sigue teniendo islas sin soporte")
    return out,len(found),removed



def classify_artwork(ink, outer, w, h):
    """Detect filled logos/silhouettes versus sparse ink line drawings.

    Silhouette art has broad dark regions, and white negative spaces are
    intended openings. In line art, the dark strokes themselves can become
    cutouts. Misclassifying a solid black icon as line art removes most of its
    body and can create an excessive number of disconnected CAD islands.

    Density is measured inside the buffered silhouette rather than over the
    full page, so white page margins do not affect the classification.
    """
    _validate(ink,w,h)
    _validate(outer,w,h)
    dark=0
    filled=0
    for fg,shape in zip(ink,outer):
        if shape:
            filled+=1
            if fg:
                dark+=1
    if filled<4:
        raise ValueError("La imagen no tiene un dibujo reconocible.")
    fraction=dark/filled
    return ("silhouette" if fraction>=0.62 else "lineart"),fraction


def clean_tiny_cutouts(cut,w,h,min_pixels):
    """Discard sub-nozzle perforations before expensive CAD vectorization.

    4-connected specks that cannot reasonably be printed do not create
    wires, isolated slivers or fragile through-holes. Larger eye/ear holes
    and letter counters are preserved.
    """
    _validate(cut,w,h)
    if min_pixels<=1:
        return bytearray(cut),0
    out=bytearray(w*h)
    removed=0
    for comp in connected_components(cut,w,h):
        if len(comp)<min_pixels:
            removed+=1
        else:
            for i in comp:
                out[i]=1
    return out,removed



def solid_rear_envelope(envelope,w,h):
    """Use the intended outer silhouette, NEVER holes/bridges of the front.

    fill_holes(front) is not a valid rear silhouette: front stencil bridges
    can close triangular exterior pockets at the base join, turning an
    originally empty region into an unwanted printable wedge on the back.
    """
    _validate(envelope,w,h)
    result,_=repair_diagonal_contacts(envelope,w,h)
    pieces=connected_components(result,w,h)
    if len(pieces)!=1:
        raise ValueError(
            "La figura y la placa no forman una carcasa continua. "
            "Revisa el solape entre la ilustración y el nombre.")
    return result



def repair_diagonal_contacts(mask,w,h):
    """Resolve checkerboard pixel corners that become self-touching OCC wires.

    A 4-connected body may have two background regions touching diagonally;
    a vector boundary then revisits one vertex and produces an invalid wire.
    Adding the minimum possible supporting material (one pixel per diagonal
    contact) removes these pinches while preserving through-cut letter counters
    and their existing structural bridges.
    """
    _validate(mask,w,h)
    out=bytearray(mask)
    count=0
    for _ in range(8):
        changed=0
        for y in range(h-1):
            row=y*w
            for x in range(w-1):
                i=row+x
                a,b,c,d=out[i],out[i+1],out[i+w],out[i+w+1]
                if a and d and not b and not c:
                    out[i+1]=1
                    changed+=1
                elif b and c and not a and not d:
                    out[i]=1
                    changed+=1
        count+=changed
        if not changed:
            break
    return out,count


def polygon_area(points):
    return sum(points[i][0]*points[(i+1)%len(points)][1]-
               points[(i+1)%len(points)][0]*points[i][1]
               for i in range(len(points)))/2.0


def _rdp(points,tolerance):
    """Iterative Douglas-Peucker simplification for closed pixel contours."""
    if len(points)<3:return points
    sq=tolerance*tolerance
    keep={0,len(points)-1}
    stack=[(0,len(points)-1)]
    while stack:
        a,b=stack.pop()
        x1,y1=points[a]
        x2,y2=points[b]
        dx,dy=x2-x1,y2-y1
        denom=dx*dx+dy*dy
        far=-1
        maxdist=sq
        for i in range(a+1,b):
            x,y=points[i]
            if denom==0:
                d=(x-x1)**2+(y-y1)**2
            else:
                t=max(0.0,min(1.0,((x-x1)*dx+(y-y1)*dy)/denom))
                d=(x-x1-t*dx)**2+(y-y1-t*dy)**2
            if d>maxdist:
                maxdist,far=d,i
        if far!=-1:
            keep.add(far)
            stack.append((a,far))
            stack.append((far,b))
    return [points[i] for i in sorted(keep)]


def contours(mask,w,h,tolerance=1.1,min_area=3.0):
    """Extract exterior and hole rings as correctly oriented closed polygons."""
    _validate(mask,w,h)
    edges={}
    for y in range(h):
        pos=y*w
        for x in range(w):
            if not mask[pos+x]:
                continue
            if y==0 or not mask[pos+x-w]:
                edges.setdefault((x,y),[]).append((x+1,y))
            if x==w-1 or not mask[pos+x+1]:
                edges.setdefault((x+1,y),[]).append((x+1,y+1))
            if y==h-1 or not mask[pos+x+w]:
                edges.setdefault((x+1,y+1),[]).append((x,y+1))
            if x==0 or not mask[pos+x-1]:
                edges.setdefault((x,y+1),[]).append((x,y))
    loops=[]
    edge_count=sum(len(v) for v in edges.values())
    def direction(a,b):
        return {(1,0):0,(0,1):1,(-1,0):2,(0,-1):3}[(b[0]-a[0],b[1]-a[1])]
    while edges:
        start=next(iter(edges))
        current=start
        prev=None
        ring=[start]
        for _ in range(edge_count+1):
            options=edges.get(current)
            if not options:
                raise ValueError("El contorno SVG contiene un borde abierto")
            if prev is None or len(options)==1:
                nxt=options.pop()
            else:
                incoming=direction(prev,current)
                nxt=min(options,key=lambda p:(direction(current,p)-incoming)%4)
                options.remove(nxt)
            if not options:
                del edges[current]
            if nxt==start:
                break
            ring.append(nxt)
            prev,current=current,nxt
        else:
            raise ValueError("No se pudo cerrar el contorno SVG")
        if len(ring)<4:
            continue
        smooth=[]
        for i,p in enumerate(ring):
            previous=ring[i-1]
            following=ring[(i+1)%len(ring)]
            if (previous[0]==p[0]==following[0] or
                    previous[1]==p[1]==following[1]):
                continue
            smooth.append(p)
        if len(smooth)<3 or abs(polygon_area(smooth))<min_area:
            continue
        reduced=_rdp(smooth+[smooth[0]],tolerance)
        if reduced[-1]==reduced[0]:
            reduced.pop()
        if len(reduced)>=3:
            loops.append(reduced)
    return loops



def soften_contour(points, iterations=1):
    """Reduce staircase edges without rounding long, deliberate sharp points.

    A light Chaikin pass is applied to short segments (pixel steps). Long
    geometric edges retain their vertices so character spikes stay defined.
    Output remains a closed *ring* represented without duplicate endpoint.
    """
    if len(points)<5 or iterations<1:
        return list(points)
    result=list(points)
    for _ in range(iterations):
        output=[]
        count=len(result)
        for i,point in enumerate(result):
            nxt=result[(i+1)%count]
            dx=nxt[0]-point[0]
            dy=nxt[1]-point[1]
            length=(dx*dx+dy*dy)**.5
            if length>=5.0:
                output.append(point)
            else:
                output.append((.75*point[0]+.25*nxt[0],
                               .75*point[1]+.25*nxt[1]))
                output.append((.25*point[0]+.75*nxt[0],
                               .25*point[1]+.75*nxt[1]))
        result=output
    return result


def suggest_dimensions(mask,w,h,text_length=6):
    """Recommend printable dimensions from artwork silhouette and line density.

    This is an advisory heuristic for a 0.4 mm nozzle, not a guarantee:
    details below roughly 0.8 mm may disappear during slicing.
    """
    _validate(mask,w,h)
    pixels=[i for i,v in enumerate(mask) if v]
    if not pixels:
        raise ValueError("La imagen no tiene un dibujo visible.")
    x0=min(p%w for p in pixels)
    x1=max(p%w for p in pixels)
    y0=min(p//w for p in pixels)
    y1=max(p//w for p in pixels)
    aspect=max(.15,min(4.,(x1-x0+1)/max(1,y1-y0+1)))
    transitions=0
    for y in range(h):
        off=y*w
        for x in range(w):
            if x+1<w and mask[off+x]!=mask[off+x+1]:
                transitions+=1
            if y+1<h and mask[off+x]!=mask[off+x+w]:
                transitions+=1
    detail=transitions/max(1,len(pixels))
    if detail>=.45:
        art_height,level=205,"alto"
    elif detail>=.22:
        art_height,level=170,"medio"
    else:
        art_height,level=140,"bajo"
    # Leave room for a readable, printable 19 mm-high caption and borders.
    recommended_width=max(110,art_height*aspect+20,90+min(24,text_length)*5)
    recommended_height=art_height+max(45,art_height*.32)+12
    recommended_width=min(430,max(45,round(recommended_width/5)*5))
    recommended_height=min(430,max(50,round(recommended_height/5)*5))
    return dict(width=recommended_width,height=recommended_height,
                detail=level,edge_ratio=round(detail,3))


def proportional_size(width,height,ratio,changed):
    """Return a valid locked-aspect pair within NameForge's CAD limits.

    changed is 'width' or 'height'; an impossible requested value is clamped
    to the nearest feasible pair, not allowed to distort the design.
    """
    if ratio<=0:
        raise ValueError("La proporción debe ser positiva")
    min_w,max_w=30.,430.
    min_h,max_h=40.,430.
    low=max(min_w,min_h*ratio)
    high=min(max_w,max_h*ratio)
    if low>high:
        raise ValueError("Las proporciones no caben en las dimensiones permitidas")
    if changed=="width":
        w=max(low,min(high,float(width)))
        h=w/ratio
    elif changed=="height":
        h=max(low/ratio,min(high/ratio,float(height)))
        w=h*ratio
    else:
        raise ValueError("Debe editarse ancho o alto")
    return round(w,2),round(h,2)



QUALITY_MODES = {
    # Target px/mm and maximum total raster pixels. Higher modes prioritize
    # fidelity; all modes remain bounded for complex or very large artwork.
    "fast": dict(px_per_mm=3.5, max_pixels=650_000, tolerance=1.25,
                 outer_smooth=0, inner_smooth=0),
    "balanced": dict(px_per_mm=5.5, max_pixels=1_650_000, tolerance=.82,
                     outer_smooth=1, inner_smooth=0),
    "high": dict(px_per_mm=8.0, max_pixels=3_200_000, tolerance=.52,
                 outer_smooth=2, inner_smooth=1),
}


def quality_settings(mode, width, height):
    """Calculate effective bounded raster resolution for a lamp (millimeters)."""
    from math import sqrt
    if mode not in QUALITY_MODES:
        raise ValueError("Calidad de NameForge desconocida")
    if width <= 0 or height <= 0:
        raise ValueError("Dimensiones inválidas para la calidad")
    options = QUALITY_MODES[mode].copy()
    scale = min(options["px_per_mm"],
                sqrt(options["max_pixels"] / (float(width) * float(height))),
                2500.0 / max(width, height))
    options["scale"] = round(max(1.0, scale), 3)
    return options


def cleaned_contours(mask, width, height, mode="balanced", tolerance=None):
    """Prepare vector loops away from the FreeCAD CAD/UI thread.

    Outer outlines can be smoothed more than the internal lettering/detail
    cutouts. CAD fallback can still request unsmoothed contours if required.
    """
    from .curve_fit import smooth_ring
    options = QUALITY_MODES[mode]
    tol = options["tolerance"] if tolerance is None else tolerance
    loops = contours(mask, width, height, tolerance=tol, min_area=.5)
    output = []
    for ring in loops:
        iterations = (options["outer_smooth"] if polygon_area(ring)>0
                      else options["inner_smooth"])
        # Preserve sharp corners and tiny supports: never move a contour
        # point more than 0.68 source pixels. True B-spline fitting happens
        # later in Part, after the worker has prepared open curve spans.
        output.append(smooth_ring(ring, iterations=iterations))
    return output


def to_svg(loops,w,h,pixels_per_mm,fill='#000000'):
    """Even-odd fill guarantees that counter loops become true through-holes."""
    def fmt(v):
        return ('%.3f'%(v/pixels_per_mm)).rstrip('0').rstrip('.') or '0'
    paths=[]
    for loop in loops:
        paths.append('M '+' L '.join('%s %s'%(fmt(x),fmt(y)) for x,y in loop)+' Z')
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="%smm" height="%smm" '
            'viewBox="0 0 %s %s">\n<path fill="%s" fill-rule="evenodd" d="%s"/>\n</svg>\n'
            %(fmt(w),fmt(h),fmt(w),fmt(h),fill,' '.join(paths)))
