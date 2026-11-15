"""A captive pointer maze that withdraws the shared side bolt blocker.

All dimensions are millimetres. The fixed guide is pinned to the outside of
the case. The cursor has an outside knob, a guide pin, and an inside tooth;
moving it through the path shifts the tooth clear of the latch's release
stroke. This is geometry and path topology, not a friction or durability test.
"""

MAZE_PATHS = {
    # Each path starts at (0, 0), ends at (-8, 12), and uses axis-aligned
    # segments. More turns mean more decisions before the bolt is released.
    "Fácil": ((0, 0), (0, 5), (-3, 5), (-3, 0), (-8, 0), (-8, 12)),
    "Medio": ((0, 0), (0, 7), (-3, 7), (-3, -7), (-5, -7),
              (-5, 0), (-8, 0), (-8, 12)),
    "Difícil": ((0, 0), (0, 8), (-2, 8), (-2, -8), (-4, -8),
                (-4, 5), (-6, 5), (-6, -5), (-7, -5), (-7, 0),
                (-8, 0), (-8, 12)),
}


def path_for(difficulty):
    """Return a validated centerline and its number of directional turns."""
    try:
        path = MAZE_PATHS[difficulty]
    except KeyError:
        raise ValueError("Dificultad de laberinto desconocida: %s" % difficulty)
    if path[0] != (0, 0) or path[-1] != (-8, 12):
        raise ValueError("El recorrido debe comenzar bloqueado y terminar liberado.")
    for a, b in zip(path, path[1:]):
        if a[0] != b[0] and a[1] != b[1]:
            raise ValueError("El recorrido solo puede usar tramos horizontales y verticales.")
    turns = sum(1 for i in range(1, len(path)-1)
                if ((path[i][0]-path[i-1][0], path[i][1]-path[i-1][1]) !=
                    (path[i+1][0]-path[i][0], path[i+1][1]-path[i][1])))
    return path, turns


def make_maze_lock(Part, V, pivot_u, bolt_z, difficulty):
    """Return fixed guide, moving cursor, and guide mounting-hole centers.

    The plate's slot is closed at both ends so the enlarged knob and blocking
    tooth retain the follower after the guide is mounted. Assembly is performed
    by placing the cursor on the wall before fitting the guide over its pins.
    """
    path, _turns = path_for(difficulty)
    mk, cyl = Part.makeBox, Part.makeCylinder
    width, height, thickness = 29.0, 27.0, 1.6
    x0, z0 = pivot_u-20.0, bolt_z-13.0
    guide = mk(width, thickness, height, V(x0, -1.8, z0))

    # Cut a continuous rounded slot, with a little running clearance around
    # the 1.8 mm follower pin. Segment boxes and junction cylinders overlap.
    cutter = None
    radius = 1.25
    def add_cut(shape):
        nonlocal cutter
        cutter = shape if cutter is None else cutter.fuse(shape)
    for x, z in path:
        add_cut(cyl(radius, thickness+0.4,
                    V(pivot_u+x, -2.0, bolt_z+z), V(0,1,0)))
    for (ax,az),(bx,bz) in zip(path,path[1:]):
        if az == bz:
            add_cut(mk(abs(bx-ax), thickness+0.4, 2*radius,
                       V(pivot_u+min(ax,bx),-2.0,bolt_z+az-radius)))
        else:
            add_cut(mk(2*radius, thickness+0.4, abs(bz-az),
                       V(pivot_u+ax-radius,-2.0,bolt_z+min(az,bz))))
    guide = guide.cut(cutter)

    # Two locating pins fit 0.35 mm radial clearance holes in the case wall.
    anchors = ((pivot_u-18.0, bolt_z+4.5),
               (pivot_u+7.0, bolt_z+4.5))
    for x,z in anchors:
        peg = cyl(1.30, 1.5, V(x,-0.2,z), V(0,1,0))
        guide = guide.fuse(peg)

    # The cursor's outer knob and inner tooth are both wider than the slot.
    # Its tooth keeps the bolt from completing the 20 mm release stroke until
    # the pointer reaches the (-8, 12) exit of the maze.
    slider = cyl(3.2, 2.0, V(pivot_u,-6.2,bolt_z), V(0,1,0))
    pin = cyl(0.90, 2.8, V(pivot_u,-4.3,bolt_z), V(0,1,0))
    tooth = mk(8.0,1.6,14.0,V(pivot_u-4.0,-3.6,bolt_z-7.0))
    slider = slider.fuse(pin).fuse(tooth)
    return guide.removeSplitter(), slider.removeSplitter(), anchors
