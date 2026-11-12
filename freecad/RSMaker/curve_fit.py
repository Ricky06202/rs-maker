"""Corner-aware curve planning for printable FreeCAD silhouettes.

This module never imports FreeCAD, OCC or Qt. Its output can be generated in
the NameForge background worker and materialized as Part.BSplineCurve edges
only on the GUI/CAD thread. It never closes apertures or changes topology;
CAD validates faces and can fall back to the original polygon when needed.
"""
from math import hypot

def sharp_corners(points, min_arm=3.0, max_cosine=.55):
    """Find genuinely sharp vertices, ignoring short raster stair-steps.

    The threshold retains meaningful hair spikes and the square corners of
    nameplates, while 1-2 pixel right-angle stair-steps can be rounded.
    """
    n=len(points)
    if n<3:
        return set()
    corners=set()
    for i in range(n):
        prev=points[(i-1)%n]
        current=points[i]
        nxt=points[(i+1)%n]
        incoming=(current[0]-prev[0],current[1]-prev[1])
        outgoing=(nxt[0]-current[0],nxt[1]-current[1])
        a=hypot(*incoming)
        b=hypot(*outgoing)
        if min(a,b)<min_arm:
            continue
        cosine=(incoming[0]*outgoing[0]+
                incoming[1]*outgoing[1])/(a*b)
        if cosine<max_cosine:
            corners.add(i)
    return corners


def smooth_ring(points, iterations=1, max_shift=.68):
    """Round raster stair-steps while anchoring geometric corners.

    Each point stays within max_shift raster pixels of its original position;
    this protects the narrow supports and letter counters better than
    repeated unrestricted Chaikin subdivision.
    """
    original=[(float(x),float(y)) for x,y in points]
    n=len(original)
    if n<5 or iterations<=0:
        return original
    protected=sharp_corners(original)
    current=original
    for _ in range(iterations):
        changed=[]
        for i,(x,y) in enumerate(current):
            if i in protected:
                changed.append(original[i])
                continue
            x0,y0=current[(i-1)%n]
            x1,y1=current[(i+1)%n]
            wanted=(.25*x0+.5*x+.25*x1,
                    .25*y0+.5*y+.25*y1)
            from_original=(wanted[0]-original[i][0],
                           wanted[1]-original[i][1])
            length=hypot(*from_original)
            if length>max_shift:
                ratio=max_shift/length
                wanted=(original[i][0]+from_original[0]*ratio,
                        original[i][1]+from_original[1]*ratio)
            changed.append(wanted)
        current=changed
    return current


def spline_spans(points, max_points=96):
    """Split a closed ring into smoothly fit-able, open spline segments.

    Sharp corners split the ring so the CAD fit doesn't round them away.
    A ring without corners is split into two open spans to avoid periodic
    interpolation quirks in older OpenCascade/FreeCAD releases.
    Every span shares an *identical* vertex with the next one.
    """
    ring=list(points)
    if len(ring)<3:
        return []
    corners=sorted(sharp_corners(ring))
    if len(corners)<2:
        corners=[0,len(ring)//2]
    spans=[]
    n=len(ring)
    for j,start in enumerate(corners):
        stop=corners[(j+1)%len(corners)]
        if stop<=start:
            stop+=n
        section=[ring[index%n] for index in range(start,stop+1)]
        step=max(2,int(max_points)-1)
        for off in range(0,len(section)-1,step):
            fragment=section[off:off+step+1]
            if len(fragment)>=2:
                spans.append(fragment)
    return spans
