"""Two-step linear gate for a lateral RS Maker puzzle.

Unlike the rotary-wheel lock, this gate must be lowered 12 mm BEFORE the
standard horizontal bolt can slide 20 mm out of the lid lug.

Local frame: X = side U, Y negative = outside, Z vertical. Parts are
modeled in the locked position and are returned separately for 3D printing.

The rail assembly has a bottom travel stop and an independently printed
two-peg top cap: insert the vertical gate from above, then install the cap.
The cap has nominal 0.25 mm radial peg clearance; its actual retention,
friction and safety MUST be verified on printed prototypes. No adhesives
or child-safe snap-fit strength are implied by this CAD prototype.
"""
from .config import RELEASE_TRAVEL

GATE_DROP_MM = 12.0
# The left-moving latch grip sweeps through the gate after 8 mm. This
# is a real, geometric ordering constraint, not simply printed symbols.
LOCK_CHECK_MM = 8.0


def make_sequential_lock(Part, V, pivot_u, bolt_z):
    """Return (fixed guide rails, sliding gate, removable top cap).

    The fixed rails are fused into the outer wall at the upper and lower
    mounts; the moving gate is captured laterally by the two thin lips.
    It remains possible to assemble the device from separately printed STLs.
    """
    mk, cyl = Part.makeBox, Part.makeCylinder

    def box(x0, x1, y0, y1, z0, z1):
        return mk(x1-x0,y1-y0,z1-z0,
                  V(pivot_u+x0,y0,bolt_z+z0))

    gate = box(-3.5,3.5,-11.0,-7.9,-4.0,4.0)
    # Integral thumb button; its inner 0.2 mm overlaps the gate body.
    gate = gate.fuse(box(-2.2,2.2,-14.0,-10.8,-3.0,3.0))

    rails = None
    def add(shape):
        nonlocal rails
        rails = shape if rails is None else rails.fuse(shape)

    for x0,x1 in ((-7.0,-4.2),(4.2,7.0)):
        add(box(x0,x1,-12.8,-9.25,-21.0,7.0))
        # Only these mounts reach the solid base wall, 0.5 mm inside.
        # They are above/below the standard latch's horizontal slot.
        add(box(x0,x1,-12.8,.5,5.3,7.0))
    # Overhanging lips retain the gate in outward (negative-Y) direction;
    # 0.35 mm front clearance and 0.7 mm lateral clearance per side.
    for x0,x1 in ((-4.3,-3.1),(3.1,4.3)):
        add(box(x0,x1,-13.5,-11.35,-21.0,7.0))
    # Lower stop also bonds both rails to the existing box wall.
    add(box(-7.0,7.0,-12.8,.5,-21.0,-18.0))

    for x in (-5.6,5.6):
        rails = rails.cut(cyl(.85,3.0,V(pivot_u+x,-11,bolt_z+4.5)))

    cap = box(-7.0,7.0,-13.15,-9.7,7.35,9.2)
    for x in (-5.6,5.6):
        cap = cap.fuse(cyl(.60,2.6,V(pivot_u+x,-11,bolt_z+4.75)))

    # This check also makes the intended release semantics discoverable for
    # tests/documentation without hardcoding motion in the GUI.
    assert RELEASE_TRAVEL >= LOCK_CHECK_MM + GATE_DROP_MM
    return rails.removeSplitter(),gate.removeSplitter(),cap.removeSplitter()
