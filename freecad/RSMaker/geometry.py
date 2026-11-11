"""Five-station CAD prototype: four side latches + one lid cam + original art.

FreeCAD Part shapes; millimetres. Each side has a wheel that blocks its latch
slider, and the slider enters a horizontal hole in a lug attached to the lid.
A fifth dial under the lid hooks a shelf of the base. The four side designs
share one proven-in-concept mechanism family in v0.2. Real actuation, strength,
retaining hardware and safety MUST be validated with a printed prototype.

All parts are modeled in the LOCKED assembly position, not plate-laid for
printing. STL export preserves separate, identity-labeled parts.
"""
import math
from .config import (PuzzleConfig, FACES, DIAL_MARKS, ARM_HEIGHT,
                     THEMES, RELEASE_TRAVEL)
from .collection import (make_restaurant, make_hamburger, make_side_emboss,
                         restaurant_lid_sockets)

SIDE_COLORS = ((0.96,0.61,0.25),(0.37,0.69,0.82),
               (0.75,0.59,0.86),(0.53,0.78,0.57))


def _face_pose(face, W, D):
    # Right-handed XY coordinate frame: local U along side, V points inward.
    return {"Frontal":(0,(0,0)), "Derecha":(90,(W,0)),
            "Trasera":(180,(W,D)), "Izquierda":(270,(0,D))}[face]


def _to_global(shape, face, W, D, V):
    angle, (ox,oy) = _face_pose(face, W, D)
    result = shape.copy()
    result.rotate(V(0,0,0), V(0,0,1), angle)
    result.translate(V(ox,oy,0))
    return result


def _motif(kind, cx, cy, z, size, height, Part, V):
    def prism(points):
        pts = [V(cx+u*size,cy+v*size,z) for u,v in points]
        wire = Part.makePolygon(pts+[pts[0]])
        return Part.Face(wire).extrude(V(0,0,height))
    if kind == "star":
        return prism([(math.cos(i*math.pi/5-math.pi/2)*(0.5 if i%2==0 else 0.22),
                       math.sin(i*math.pi/5-math.pi/2)*(0.5 if i%2==0 else 0.22))
                      for i in range(10)])
    if kind == "bolt":
        return prism([(-.10,.50),(.20,.06),(.04,.06),(.26,-.50),
                      (-.26,-.05),(-.04,-.05)])
    if kind == "paw":
        shape = Part.makeCylinder(size*.20,height,V(cx,cy-size*.16,z))
        for dx,dy in ((-.30,.19),(-.11,.34),(.14,.32),(.34,.14)):
            shape = shape.fuse(Part.makeCylinder(size*.10,height,
                               V(cx+dx*size,cy+dy*size,z)))
        return shape
    raise ValueError("Motivo desconocido")


def build_shapes(cfg):
    """Return (part_key, solid, color) in closed assembly coordinates.

    Physical release sequence: rotate each side gate 180° towards the side
    away from the slider, pull its latch 20mm, then turn lid cam 90° and lift.
    Wheel shaft and top cam need retaining hardware in the physical assembly.
    """
    cfg.validate()
    import FreeCAD as App
    import Part
    V = App.Vector
    mk = Part.makeBox
    cyl = Part.makeCylinder
    W,D,H,w,f,g = (cfg.width,cfg.depth,cfg.height,
                   cfg.wall,cfg.floor,cfg.clearance)
    body_h, lid_t = H-5.0, 5.0
    z_bolt = body_h-7.0
    lug_start = w+g+1.2
    lug_depth = 9.0
    bolt_v = lug_start+lug_depth/2
    bolt_square = 3.6
    bore_square = bolt_square+2*g

    base = mk(W,D,body_h).cut(mk(W-2*w,D-2*w,body_h-f+.5,V(w,w,f)))
    lid = mk(W-2*g,D-2*g,lid_t,V(g,g,body_h+g))
    parts = []

    # Four independent latches, at the same station on every face. The inner
    # guide is glued geometrically to the wall and has a through square hole.
    for index, face in enumerate(FACES[:4]):
        L = W if index % 2 == 0 else D
        u0 = L/2
        wheel_z = z_bolt-11
        pivot_u = u0-51
        mark_count = DIAL_MARKS[cfg.face_difficulty(face)]
        arm_h = ARM_HEIGHT[cfg.face_difficulty(face)]
        # Recess in the body for a hand-accessible sliding latch stem.
        slot = mk(30,w+1.3,5.3,V(u0-67,-.5,z_bolt-2.65))
        # Round bore supports the wheel shaft through the body wall.
        shaft_hole = cyl(2.65,w+1.2,V(pivot_u,-.5,wheel_z),V(0,1,0))
        # Squared guide block, bridged on the inner wall. Cut along local U.
        guide = mk(9,bolt_v+4.0-w,10,V(u0-25,w,z_bolt-5))
        guide = guide.cut(mk(10,bore_square,bore_square,
                        V(u0-25.5,bolt_v-bore_square/2,z_bolt-bore_square/2)))
        body_mod = guide
        # Ears underneath the lid: 16 mm long, 9 mm deep with tunnel in U.
        lug = mk(16,lug_depth,12+g,
                 V(u0-8,lug_start,body_h-11))
        bore = mk(17,bore_square,bore_square,
                  V(u0-8.5,bolt_v-bore_square/2,z_bolt-bore_square/2))
        lug = lug.cut(bore)
        # Short opening of the inner wall at the knob stem route, but no cut
        # through the wall's very top; therefore it retains an upper rim.
        base = base.cut(_to_global(slot,face,W,D,V))
        base = base.cut(_to_global(shaft_hole,face,W,D,V))
        base = base.fuse(_to_global(body_mod,face,W,D,V))
        lid = lid.fuse(_to_global(lug,face,W,D,V))

        # Latch (rod + stem + outside thumb lever) manufactured as one piece.
        rod = mk(52,bolt_square,bolt_square,
                 V(u0-46,bolt_v-bolt_square/2,z_bolt-bolt_square/2))
        stem = mk(4.0,bolt_v+7,bolt_square,
                  V(u0-45,-7,z_bolt-bolt_square/2))
        grip = mk(8.0,3.0,8.0,V(u0-47,-9,z_bolt-4))
        latch = rod.fuse(stem).fuse(grip)
        parts.append(("C%u_Cerrojo" % (index+1),
                      _to_global(latch,face,W,D,V),SIDE_COLORS[index]))

        # External rotary blocker. Cam arm rises into the thumb lever's path;
        # rotating it out of that path permits the latch to move to the left.
        axle = cyl(2.0,w+7.7,V(pivot_u,-7,wheel_z),V(0,1,0))
        dial = cyl(4.7,3,V(pivot_u,-9,wheel_z),V(0,1,0))
        arm = mk(3.2,3,arm_h,V(pivot_u-1.6,-9,wheel_z+3.0))
        wheel = axle.fuse(dial).fuse(arm)
        # Small raised marks. They provide distinguishable selectable levels,
        # but don't constitute a certified human difficulty measurement.
        for n in range(mark_count):
            a = 2*math.pi*n/mark_count
            pip = cyl(.60,.7,V(pivot_u+3.5*math.cos(a),-9.5,
                               wheel_z+3.5*math.sin(a)),V(0,1,0))
            wheel = wheel.fuse(pip)
        parts.append(("C%u_Rueda" % (index+1),
                      _to_global(wheel,face,W,D,V),(0.95,.83,.39)))

    # Independent TOP dial, hooked under a fixed interior shelf of the base.
    dx,dy = W-32,D-32
    shelf = mk(15.0,23.0,2.8,V(W-20,D-43,body_h-7.0))
    base = base.fuse(shelf)
    lid = lid.cut(cyl(3.05,lid_t+2.0,V(dx,dy,body_h+g-.5)))
    # The top knob/shaft and under-lid cam are independent printable pieces;
    # keyed square shaft, loose-fit cam, plus small retaining washer.
    shaft_z = body_h-12.1
    shaft_h = (body_h+g+lid_t+2.0)-shaft_z
    key = mk(3.8,3.8,shaft_h,V(dx-1.9,dy-1.9,shaft_z))
    knob = cyl(9.0,3.0,V(dx,dy,body_h+g+lid_t+1.4))
    wheel_top = key.fuse(knob)
    for j in range(DIAL_MARKS[cfg.tapa]):
        angle = math.pi*2*j/DIAL_MARKS[cfg.tapa]
        pip = cyl(.9,.6,V(dx+6.5*math.cos(angle),dy+6.5*math.sin(angle),
                            body_h+g+lid_t+4.0))
        wheel_top = wheel_top.fuse(pip)
    cam_z = body_h-10.4
    cam = cyl(5,2.9,V(dx,dy,cam_z))
    cam = cam.fuse(mk(19,6,2.9,V(dx+3,dy-3,cam_z)))
    cam = cam.cut(mk(4.15,4.15,3.9,V(dx-2.075,dy-2.075,cam_z-.5)))
    # Retainer is separately printed and requires a checked retention method.
    keeper = cyl(4,1.2,V(dx,dy,body_h-12.0)).cut(
             mk(4.15,4.15,2,V(dx-2.075,dy-2.075,body_h-12.4)))
    parts.extend((("Tapa_Dial",wheel_top,(0.94,.53,.35)),
                  ("Tapa_Leva",cam,(0.87,.61,.38)),
                  ("Tapa_Retenedor",keeper,(0.84,.77,.65))))

    # Built-in food collection is independent of the five mechanical locks.
    if cfg.collection == "Comida":
        for face in FACES[:4]:
            L = W if face in ("Frontal", "Trasera") else D
            base = base.fuse(make_side_emboss(cfg, face, L, Part, V, _to_global))
        if cfg.scene == "Restaurante":
            lid_top = body_h + g + lid_t
            for tool in restaurant_lid_sockets(cfg, Part, V, lid_top):
                lid = lid.cut(tool)
            parts.append(("Escenario_Restaurante",
                          make_restaurant(cfg, Part, V, lid_top),
                          (.96,.66,.41)))
        if cfg.figure == "Hamburguesita":
            parts.append(("Chibi_Hamburguesita",
                          make_hamburger(cfg, Part, V),
                          (.96,.72,.39)))

    main = [("Base",base.removeSplitter(),(.35,.59,.80)),
            ("Tapa",lid.removeSplitter(),(.87,.92,.97))]
    main.extend(parts)
    motif = THEMES[cfg.theme]
    if motif:
        # Does not overlap top dial; decorative part can be a separate filament.
        main.append(("Decoracion_"+cfg.theme,
                     _motif(motif,W*.45,D*.49,body_h+g+lid_t,
                            min(W,D)*.19,.85,Part,V),
                     (.94,.38,.47)))
    return main
