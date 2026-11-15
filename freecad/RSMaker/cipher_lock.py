"""Indexed ring cipher with a comb gate for a lateral RS Maker latch.

The rings turn independently on fixed axles. Each has an off-centre window.
The comb can descend only after every window is indexed to the gate fingers;
the same 12 mm gate then releases the shared horizontal bolt. OpenCascade
checks cover the indexed positions and swept static intersections, not wear.
"""
import math

from .config import DIAL_MARKS
from .sequential_lock import GATE_DROP_MM, make_sequential_lock

CIPHER_RING_COUNT = {"Fácil": 2, "Medio": 3, "Difícil": 4}
RING_RADIUS = 7.0
RING_SPACING = 15.0
WINDOW_OFFSET = 4.5
WINDOW_WIDTH = 2.0
COMB_DROP_MM = GATE_DROP_MM


def cipher_profile(difficulty):
    """Return the actual ring count, index count and non-zero answer indices."""
    if difficulty not in CIPHER_RING_COUNT:
        raise ValueError("Dificultad de cifrado desconocida: %s" % difficulty)
    count = CIPHER_RING_COUNT[difficulty]
    positions = DIAL_MARKS[difficulty]
    code = tuple(1+(i % (positions-1)) for i in range(count))
    return {"rings": count, "positions": positions, "code": code,
            "moves": count+1}


def make_cipher_lock(Part, V, pivot_u, bolt_z, wall, difficulty):
    """Return ``(rings, gate, rails, cap, axle_support, shaft_holes, code)``.

    Ring centers are placed on the lower outside area of each side, above the
    themed emboss zone and clear of the closed latch. The local solution angle
    for each ring is returned in degrees for motion tests and assembly notes.
    """
    profile = cipher_profile(difficulty)
    mk, cyl = Part.makeBox, Part.makeCylinder
    count, positions = profile["rings"], profile["positions"]
    u0 = pivot_u+51.0
    first_x = u0-30.0
    center_z = bolt_z-16.0
    ring_y = -2.8
    rings, holes, code = [], [], []
    axle_support = None
    base_angle = 360.0/positions

    for i in range(count):
        x = first_x+i*RING_SPACING
        z = center_z
        center = V(x,ring_y,z)

        # Independently turning washer with a full radial window. The window
        # is rotated away from the gate finger in the locked position.
        ring = cyl(RING_RADIUS,2.7,center,V(0,1,0))
        bore = cyl(1.50,3.1,V(x,-3.0,z),V(0,1,0))
        ring = ring.cut(bore)
        # The opening begins below the gate's final pin tip. A lower bridge
        # keeps the tumbler a single, printable solid while the aligned pin
        # can descend through its full 12 mm stroke.
        window_bottom = z+RING_RADIUS+1.0-COMB_DROP_MM-0.7
        window_height = COMB_DROP_MM+0.7
        window = mk(WINDOW_WIDTH,1.2,window_height,
                    V(x+WINDOW_OFFSET-WINDOW_WIDTH/2,-3.0,window_bottom))
        answer_index = profile["code"][i]
        answer_angle = answer_index*base_angle
        window.rotate(V(x,ring_y,z),V(0,1,0),answer_angle)

        # Raised index pips make the ring positions visible in the CAD model.
        # Their count scales with the per-face difficulty profile.
        for mark in range(positions):
            angle = 2.0*math.pi*(mark+0.5)/positions
            pip = cyl(0.35,0.65,
                      V(x+5.8*math.cos(angle),-3.25,
                        z+5.8*math.sin(angle)), V(0,1,0))
            ring = ring.fuse(pip)
        # Cut the indexing path through the raised marks too so the moving
        # finger never catches a pip at its aligned gate position.
        ring = ring.cut(window)
        rings.append(ring.removeSplitter())
        code.append(answer_angle)

        # Case-integral spindle and retaining head. The washer's centre bore
        # turns around the spindle with 0.35 mm radial clearance.
        shaft_hole = cyl(1.40,wall+0.4,V(x,-0.5,z),V(0,1,0))
        holes.append(shaft_hole)
        shaft = cyl(1.10,wall+4.0,V(x,-2.8,z),V(0,1,0))
        head = cyl(2.10,1.0,V(x,-3.8,z),V(0,1,0))
        spindle = shaft.fuse(head)
        axle_support = spindle if axle_support is None else axle_support.fuse(spindle)

    # Reuse the proven two-stage guide for a captive 12 mm comb slider. Extend
    # its moving gate with a raised bridge and one finger through every ring.
    rails, gate, cap = make_sequential_lock(Part,V,pivot_u,bolt_z)
    # Move the standard guide 2 mm inward. This leaves a clear path outside
    # its retaining lips for the long moving bridge while preserving the
    # gate's 12 mm travel and its fit within the wall thickness.
    y_shift=V(0,2.0,0)
    rails.translate(y_shift)
    gate.translate(y_shift)
    cap.translate(y_shift)
    first_pin_x = first_x+WINDOW_OFFSET
    last_pin_x = first_x+(count-1)*RING_SPACING+WINDOW_OFFSET
    # The bridge runs outside the fixed rail mounts, then drops connector
    # posts onto the tumbler plane. This keeps the moving comb clear of the
    # guide hardware fused into the case.
    bar = mk(last_pin_x-first_pin_x+WINDOW_WIDTH+1.0,0.8,1.2,
             V(first_pin_x-WINDOW_WIDTH/2-0.5,-12.3,bolt_z+5.5))
    # This neck overlaps the top of the standard gate, outside the bolt path.
    neck = mk(1.4,0.8,3.3,
              V(pivot_u-3.2,-12.3,bolt_z+2.8))
    bridge = mk(last_pin_x-(pivot_u-2.5),0.8,1.2,
                V(pivot_u-2.5,-12.3,bolt_z+5.5))
    gate = gate.fuse(neck).fuse(bridge).fuse(bar)

    for i in range(count):
        x = first_x+i*RING_SPACING+WINDOW_OFFSET
        # The indexing finger sits just above its ring while locked. A 12 mm
        # gate drop carries it through that ring's window.
        finger_bottom = center_z+RING_RADIUS+1.0
        finger = mk(1.2,0.8,bolt_z+6.1-finger_bottom,
                    V(x-0.6,-2.7,finger_bottom))
        connector = mk(1.2,9.2,1.2,
                       V(x-0.6,-11.5,bolt_z+4.9))
        gate = gate.fuse(finger).fuse(connector)

    return (rings,gate.removeSplitter(),rails,cap,
            axle_support.removeSplitter(),holes,tuple(code))
