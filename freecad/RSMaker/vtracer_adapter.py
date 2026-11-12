"""Optional out-of-process VTracer vectorization for NameForge.

Both 0.6 and 1.0-alpha Python APIs are supported. VTracer runs in another
Python process: a native Rust segfault cannot take FreeCAD down with it.
If the child fails or changes hole topology, the internal tracer remains
available. The returned SVG is parsed as curves, never imported via importSVG.
"""
import math
import os
import re
import shutil
import struct
import subprocess
import sys
import xml.etree.ElementTree as ET
import zlib

from . import stencil_core as core
from .vector_trace import _match_score, _orient_material_right

TOKEN = re.compile(r"[MmLlHhVvCcSsQqTtZz]|[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")
COMMANDS = set("MmLlHhVvCcSsQqTtZz")
COUNTS = {"M":2,"L":2,"H":1,"V":1,"C":6,"S":4,"Q":4,"T":2}
MAX_PIXELS = 3_250_000
MAX_SVG = 12_000_000
CHILD = '''import sys
try:
    import vtracer
    data=sys.stdin.buffer.read()
    if hasattr(vtracer,"Config"):
        cfg=vtracer.Config.bw()
        cfg.mode="spline"
        cfg.hierarchical="cutout"
        cfg.filter_speckle=2
        svg=cfg.convert_bytes(data,format="png")
    else:
        svg=vtracer.convert_raw_image_to_svg(
            data,img_format="png",colormode="binary",hierarchical="cutout",
            mode="spline",filter_speckle=2,corner_threshold=65,
            length_threshold=4.0,path_precision=3)
    sys.stdout.buffer.write(svg if isinstance(svg,bytes) else svg.encode("utf8"))
except Exception as error:
    print(str(error),file=sys.stderr)
    sys.exit(2)
'''


def mask_png(mask,w,h):
    """Black material on white, 8-bit grayscale PNG without Pillow."""
    core._validate(mask,w,h)
    if w*h>MAX_PIXELS:
        raise ValueError("Demasiados píxeles para VTracer")
    raw=bytearray()
    for y in range(h):
        raw.append(0)
        raw.extend(0 if v else 255 for v in mask[y*w:(y+1)*w])
    def chunk(name,data):
        payload=name+data
        return (struct.pack(">I",len(data))+payload+
                struct.pack(">I",zlib.crc32(payload)&0xffffffff))
    return (b"\x89PNG\r\n\x1a\n"+
            chunk(b"IHDR",struct.pack(">2I5B",w,h,8,0,0,0,0))+
            chunk(b"IDAT",zlib.compress(raw,5))+chunk(b"IEND",b""))


def run_external(png,timeout=35):
    """The native vectorizer must not run inside the FreeCAD process."""
    configured=os.environ.get("RS_MAKER_VTRACER_PYTHON","").strip()
    binary=(configured or
            (sys.executable if os.path.basename(sys.executable).lower().startswith("python")
             else shutil.which("python3")))
    if not binary:
        raise RuntimeError("No se encontró Python externo con VTracer")
    child=subprocess.run([binary,"-c",CHILD],input=png,
                         stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                         timeout=timeout,check=False)
    if child.returncode!=0:
        raise RuntimeError("VTracer externo no disponible (código %s): %s" %
                           (child.returncode,
                            child.stderr.decode("utf8","replace")[-220:]))
    if not child.stdout or len(child.stdout)>MAX_SVG:
        raise ValueError("SVG de VTracer vacío o excesivo")
    return child.stdout.decode("utf8","strict")


def _flatness(p,a,b):
    dx,dy=b[0]-a[0],b[1]-a[1]
    d=math.hypot(dx,dy)
    return (abs((p[0]-a[0])*dy-(p[1]-a[1])*dx)/d if d>1e-10
            else math.hypot(p[0]-a[0],p[1]-a[1]))


def _flatten(a,b,c,d,tol=.34):
    points=[]
    def visit(a,b,c,d,level):
        if level>=10 or max(_flatness(b,a,d),_flatness(c,a,d))<=tol:
            points.append(d)
            return
        ab=((a[0]+b[0])*.5,(a[1]+b[1])*.5)
        bc=((b[0]+c[0])*.5,(b[1]+c[1])*.5)
        cd=((c[0]+d[0])*.5,(c[1]+d[1])*.5)
        abc=((ab[0]+bc[0])*.5,(ab[1]+bc[1])*.5)
        bcd=((bc[0]+cd[0])*.5,(bc[1]+cd[1])*.5)
        mid=((abc[0]+bcd[0])*.5,(abc[1]+bcd[1])*.5)
        visit(a,ab,abc,mid,level+1)
        visit(mid,bcd,cd,d,level+1)
    visit(a,b,c,d,0)
    return points


def path_rings(path):
    """Closed M/L/H/V/C/S/Q/T/Z SVG subpaths; fail on unsupported syntax."""
    if len(path)>MAX_SVG:
        raise ValueError("Ruta SVG demasiado grande")
    tokens=TOKEN.findall(path)
    if len(tokens)>700_000 or TOKEN.sub("",path).strip(" ,\n\r\t"):
        raise ValueError("Ruta SVG inválida")
    loops=[]
    ring=[]
    current=(0.,0.)
    beginning=current
    control=None
    previous=""
    command=None
    index=0
    def add(point):
        if not all(math.isfinite(v) and abs(v)<10_000_000 for v in point):
            raise ValueError("Coordenada SVG fuera de límites")
        if not ring or math.dist(ring[-1],point)>1e-7:
            ring.append(point)
    while index<len(tokens):
        if tokens[index] in COMMANDS:
            command=tokens[index]
            index+=1
            if command in "Zz":
                if not ring:
                    raise ValueError("Cierre SVG sin punto inicial")
                if math.dist(ring[0],ring[-1])<1e-6:
                    ring.pop()
                if len(ring)>=3:
                    loops.append(list(ring))
                ring.clear()
                current=beginning
                control=None
                previous=command
                command=None
                continue
        if command is None:
            raise ValueError("Comando SVG ausente")
        kind=command.upper()
        count=COUNTS[kind]
        if index+count>len(tokens) or any(x in COMMANDS for x in tokens[index:index+count]):
            raise ValueError("Comando SVG incompleto")
        v=[float(x) for x in tokens[index:index+count]]
        index+=count
        relative=command.islower()
        def point(x,y):
            return ((current[0]+x,current[1]+y) if relative else (x,y))
        if kind=="M":
            if ring:
                raise ValueError("Subtrazo sin cierre")
            current=point(*v)
            beginning=current
            add(current)
            command="l" if relative else "L"
            control=None
        elif kind=="L":
            current=point(*v);add(current);control=None
        elif kind=="H":
            current=(current[0]+v[0] if relative else v[0],current[1])
            add(current);control=None
        elif kind=="V":
            current=(current[0],current[1]+v[0] if relative else v[0])
            add(current);control=None
        else:
            if kind=="C":
                a=point(v[0],v[1]);b=point(v[2],v[3])
                end=point(v[4],v[5]);control=b
            elif kind=="S":
                a=((2*current[0]-control[0],2*current[1]-control[1])
                   if control and previous.upper() in ("C","S") else current)
                b=point(v[0],v[1]);end=point(v[2],v[3]);control=b
            else:
                if kind=="Q":
                    q=point(v[0],v[1]);end=point(v[2],v[3])
                else:
                    q=((2*current[0]-control[0],2*current[1]-control[1])
                       if control and previous.upper() in ("Q","T") else current)
                    end=point(v[0],v[1])
                a=(current[0]+2*(q[0]-current[0])/3,
                   current[1]+2*(q[1]-current[1])/3)
                b=(end[0]+2*(q[0]-end[0])/3,end[1]+2*(q[1]-end[1])/3)
                control=q
            for p in _flatten(current,a,b,end):
                add(p)
            current=end
        previous=command
    if ring:
        raise ValueError("Contorno SVG sin cierre")
    return loops


def _matmul(a,b):
    """SVG affine 2D transforms: a after b (nested groups supported)."""
    return (a[0]*b[0]+a[2]*b[1],
            a[1]*b[0]+a[3]*b[1],
            a[0]*b[2]+a[2]*b[3],
            a[1]*b[2]+a[3]*b[3],
            a[0]*b[4]+a[2]*b[5]+a[4],
            a[1]*b[4]+a[3]*b[5]+a[5])


def _parse_transform(source):
    """Handle standard safe SVG group transforms emitted by VTracer 0.6."""
    identity=(1.,0.,0.,1.,0.,0.)
    if not source:
        return identity
    pattern=re.compile(r"([A-Za-z]+)\s*\(([^)]*)\)")
    rest=source
    result=identity
    for match in pattern.finditer(source):
        before=rest.split(match.group(0),1)[0]
        if before.strip(" ,\n\t"):
            raise ValueError("Transformación SVG inválida")
        rest=rest.split(match.group(0),1)[1]
        kind=match.group(1).lower()
        numbers=[float(x) for x in re.findall(
            r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?",match.group(2))]
        if not all(math.isfinite(x) for x in numbers):
            raise ValueError("Transformación SVG fuera de rango")
        if kind=="translate" and len(numbers) in (1,2):
            op=(1.,0.,0.,1.,numbers[0],numbers[1] if len(numbers)==2 else 0.)
        elif kind=="scale" and len(numbers) in (1,2):
            op=(numbers[0],0.,0.,
                numbers[1] if len(numbers)==2 else numbers[0],0.,0.)
        elif kind=="matrix" and len(numbers)==6:
            op=tuple(numbers)
        elif kind=="rotate" and len(numbers) in (1,3):
            angle=math.radians(numbers[0])
            cs,sn=math.cos(angle),math.sin(angle)
            turn=(cs,sn,-sn,cs,0.,0.)
            if len(numbers)==3:
                cx,cy=numbers[1],numbers[2]
                turn=_matmul((1.,0.,0.,1.,cx,cy),
                             _matmul(turn,(1.,0.,0.,1.,-cx,-cy)))
            op=turn
        else:
            raise ValueError("Tipo de transformación SVG no permitido")
        result=_matmul(result,op)
    if rest.strip(" ,\n\t"):
        raise ValueError("Transformación SVG desconocida")
    return result


def svg_rings(svg,mask,w,h):
    if len(svg)>MAX_SVG or "<!DOCTYPE" in svg.upper() or "<!ENTITY" in svg.upper():
        raise ValueError("SVG inseguro o excesivo")
    root=ET.fromstring(svg)
    if root.tag.split("}")[-1]!="svg":
        raise ValueError("VTracer no devolvió un SVG")
    vb=root.attrib.get("viewBox")
    if vb:
        view=[float(x) for x in re.split(r"[,\s]+",vb.strip())]
        if len(view)!=4 or not all(math.isfinite(x) for x in view) or view[2]<=0 or view[3]<=0:
            raise ValueError("viewBox SVG incorrecto")
        x0,y0,sw,sh=view
        if abs(sw-w)>max(1,w*.08) or abs(sh-h)>max(1,h*.08):
            raise ValueError("Dimensiones SVG distintas de la máscara")
    else:
        x0=y0=0.;sw=float(w);sh=float(h)
    rings=[]
    visited=[0]
    identity=(1.,0.,0.,1.,0.,0.)

    def visit(node,parent_matrix,parent_fill=""):
        matrix=_matmul(parent_matrix,_parse_transform(node.attrib.get("transform","")))
        fill=node.attrib.get("fill",parent_fill).strip().lower()
        style=node.attrib.get("style","").replace(" ","").lower()
        if "fill:" in style:
            fill=style.split("fill:",1)[1].split(";",1)[0]
        if node.tag.split("}")[-1]=="path":
            visited[0]+=1
            if visited[0]>12_000:
                raise ValueError("Demasiados trazos SVG")
            if fill not in ("none","white","#fff","#ffffff","rgb(255,255,255)"):
                for ring in path_rings(node.attrib.get("d","")):
                    converted=[]
                    for x,y in ring:
                        gx=matrix[0]*x+matrix[2]*y+matrix[4]
                        gy=matrix[1]*x+matrix[3]*y+matrix[5]
                        converted.append(((gx-x0)*w/sw,(gy-y0)*h/sh))
                    if abs(core.polygon_area(converted))>=.5:
                        rings.append(_orient_material_right(converted,mask,w,h))
        for child in node:
            visit(child,matrix,fill)
    visit(root,identity)
    if not rings:
        raise ValueError("VTracer no produjo contornos válidos")
    return rings


def trace(mask,w,h,mode,runner=None):
    """Match VTracer rings to original mask; preserve every printable counter."""
    if mode=="fast":
        raise ValueError("VTracer desactivado en modo rápido")
    svg=(runner or run_external)(mask_png(mask,w,h))
    rings=svg_rings(svg,mask,w,h)
    original=core.cleaned_contours(mask,w,h,mode)
    if len(original)>900 or len(rings)>max(5000,len(original)*3+50):
        raise ValueError("Dibujo demasiado complejo para emparejar contornos")
    available=set(range(len(rings)))
    chosen=[]
    replaced=0
    for old in original:
        sign=core.polygon_area(old)>0
        index=None
        best=.55
        for i in available:
            ring=rings[i]
            if (core.polygon_area(ring)>0)!=sign:
                continue
            score=_match_score(old,ring)
            if score>best:
                index,best=i,score
        if index is None:
            chosen.append(old)
        else:
            chosen.append(rings[index])
            available.remove(index)
            replaced+=1
    if not replaced:
        raise ValueError("VTracer alteró los huecos del dibujo")
    return chosen,replaced,len(original)
