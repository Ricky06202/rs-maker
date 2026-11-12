"""Original Space and Beach art packs for the five-face RS Maker puzzle box.

Independent 3D-printable decoration for the top lid, a small original chibi
inside the prize cavity, and low-profile outer-wall relief. These parts do
not change the locking system or override the fifth top puzzle. No brand IP.
All units are millimeters. Physical fit and safety are NOT yet validated.
"""


def _add_mount_pegs(scene, cfg, Part, V, ztop):
    """Use the existing two-hole lid interface, with 0.5-mm radial clearance."""
    from .collection import restaurant_socket_centers
    for x,y in restaurant_socket_centers(cfg):
        scene=scene.fuse(
            Part.makeCylinder(1.85,3.1,V(x,y,ztop-2.7)))
    return scene.removeSplitter()


def make_space_scene(cfg, Part, V, ztop):
    """One-piece stylized landing rocket on the lid, away from the final dial."""
    mk,cyl,sphere=Part.makeBox,Part.makeCylinder,Part.makeSphere
    cx,cy=cfg.width/2.0,cfg.depth/2.0
    platform=mk(60,44,2,V(cx-30,cy-22,ztop))
    rocket=cyl(8.5,18,V(cx,cy,ztop+1.5))
    nose=sphere(8.0,V(cx,cy,ztop+20.0))
    fins=mk(31,6,3.0,V(cx-15.5,cy-3,ztop+4))
    # Entire decoration is fused into its printable mounting platform.
    scene=platform.fuse(rocket).fuse(nose).fuse(fins)
    # A shallow porthole inset is decorative, not a through-cut cavity.
    porthole=cyl(3.0,1.5,V(cx,cy-8.9,ztop+12.5),V(0,1,0))
    scene=scene.cut(porthole)
    return _add_mount_pegs(scene,cfg,Part,V,ztop)


def make_beach_scene(cfg, Part, V, ztop):
    """Two original palm trees on one-piece top display plinth."""
    mk,cyl=Part.makeBox,Part.makeCylinder
    cx,cy=cfg.width/2.0,cfg.depth/2.0
    scene=mk(60,44,2,V(cx-30,cy-22,ztop))
    for dx in (-16,16):
        x=cx+dx
        stem=cyl(3.1,19.0,V(x,cy,ztop+1.5))
        # Flat crossed fronds require no separate loose leaves.
        crown_a=mk(24,4.5,2.2,V(x-12,cy-2.25,ztop+18))
        crown_b=mk(4.5,24,2.2,V(x-2.25,cy-12,ztop+18))
        scene=scene.fuse(stem).fuse(crown_a).fuse(crown_b)
    return _add_mount_pegs(scene,cfg,Part,V,ztop)


def make_astro_chibi(cfg, Part, V):
    """Original tiny astronaut character with engraved helmet visor."""
    mk,cyl,sphere=Part.makeBox,Part.makeCylinder,Part.makeSphere
    sc=cfg.figure_height/32.0
    cx,cy=cfg.width/2.0,cfg.depth/2.0
    z0=cfg.floor+.4
    def p(x,y,z):
        return V(cx+x*sc,cy+y*sc,z0+z*sc)
    torso=cyl(7.3*sc,15*sc,p(0,0,4.5))
    helmet=sphere(9.5*sc,p(0,0,21))
    figure=torso.fuse(helmet)
    for dx in (-4.5,4.5):
        foot=sphere(3.8*sc,p(dx,-1,5.0))
        figure=figure.fuse(foot)
    # Small engraved face visor; not a separate loose part.
    visor=mk(11*sc,3*sc,5*sc,p(-5.5,-10,20))
    figure=figure.cut(visor)
    if cfg.expression=="Sorprendida":
        mouth=cyl(1.5*sc,2*sc,p(0,-9.5,17),V(0,1,0))
        figure=figure.cut(mouth)
    return figure.removeSplitter()


def make_crab_chibi(cfg, Part, V):
    """One-piece beach crab with integrated pincers and engraved expression."""
    mk,cyl,sphere=Part.makeBox,Part.makeCylinder,Part.makeSphere
    sc=cfg.figure_height/32.0
    cx,cy=cfg.width/2.0,cfg.depth/2.0
    z0=cfg.floor+.4
    def p(x,y,z):
        return V(cx+x*sc,cy+y*sc,z0+z*sc)
    body=sphere(10.0*sc,p(0,0,14))
    for dx in (-10.0,10.0):
        body=body.fuse(sphere(4.9*sc,p(dx,0,15)))
    for dx in (-5.0,5.0):
        body=body.fuse(sphere(3.7*sc,p(dx,-4,7.5)))
        body=body.fuse(sphere(2.6*sc,p(dx,-5,22)))
    if cfg.expression=="Sorprendida":
        mouth=cyl(1.6*sc,2.3*sc,p(0,-10.3,13),V(0,1,0))
        body=body.cut(mouth)
    else:
        mouth=mk(4.2*sc,2.0*sc,.9*sc,p(-2.1,-10.8,13))
        body=body.cut(mouth)
    return body.removeSplitter()


def make_themed_side_emboss(cfg, face, L, Part, V, to_global):
    """Space glyph / beach crest safely below the wheel-and-slider stations."""
    mk,cyl=Part.makeBox,Part.makeCylinder
    u0,z0=L/2.0,cfg.floor+22
    symbol=mk(30,1.15,19.0,V(u0-15,-1.1,z0-9.5))
    if cfg.collection=="Espacio":
        # A miniature planet with two orbit streaks.
        symbol=symbol.fuse(cyl(4.5,.8,V(u0,-1.10,z0),V(0,-1,0)))
        for dz in (-6.0,6.0):
            symbol=symbol.fuse(
                mk(20,.85,1.4,V(u0-10,-1.15,z0+dz)))
    elif cfg.collection=="Playa":
        # Sun above two shallow water ripples.
        symbol=symbol.fuse(
            cyl(4.0,.8,V(u0,-1.10,z0+3.5),V(0,-1,0)))
        for dz in (-6.0,-2.0):
            symbol=symbol.fuse(
                mk(24,.8,1.35,V(u0-12,-1.16,z0+dz)))
    else:
        raise ValueError("Colección temática no compatible")
    return to_global(symbol.removeSplitter(),face,cfg.width,cfg.depth,V)
