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

    Multisource BFS from the main body traces the shortest passages through
    apertures to detached components. Tiny loose specks are discarded.
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
            if envelope[n] and not out[n] and not seen[n]:
                seen[n]=1
                parent[n]=p
                q.append(n)
    if len(found)!=len(islands):
        raise ValueError("No se pueden conectar todas las islas: reduce el detalle")
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
