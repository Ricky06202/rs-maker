"""Original food-themed collectible parts for RS Maker.

All dimensions are mm. No third-party characters or franchise artwork.
The chibi is one fused solid with engraved eyes and mouth: there are no loose
face pieces. The restaurant and its two pegs are one printable solid; the lid
contains corresponding clearance sockets. Physical fit remains unvalidated.
"""

FOOD_COLLECTION = "Comida"
COLLECTIONS = ("Ninguna", FOOD_COLLECTION)
FIGURES = ("Ninguna", "Hamburguesita")
SCENES = ("Ninguno", "Restaurante")
EXPRESSIONS = ("Feliz", "Sorprendida")


def restaurant_socket_centers(cfg):
    """Socket positions, away from the v0.2 final top dial."""
    cx, cy = cfg.width / 2.0, cfg.depth / 2.0
    return ((cx - 18.0, cy), (cx + 18.0, cy))


def restaurant_lid_sockets(cfg, Part, V, ztop):
    """Return two separate cutting tools for the decorative locating pins."""
    return [Part.makeCylinder(2.35, 3.3, V(x, y, ztop - 3.2))
            for x, y in restaurant_socket_centers(cfg)]


def make_restaurant(cfg, Part, V, ztop):
    """Small original fast-food shop with roof, canopy, door, sign and two pegs."""
    mk, cyl = Part.makeBox, Part.makeCylinder
    cx, cy = cfg.width / 2.0, cfg.depth / 2.0
    base = mk(60, 44, 2, V(cx - 30, cy - 22, ztop))
    shop = mk(48, 32, 17, V(cx - 24, cy - 16, ztop + 2))
    # Recessed door and windows (not holes through the shell).
    shop = shop.cut(mk(10, 1.5, 11, V(cx - 5, cy - 16.05, ztop + 2)))
    for x in (cx - 19, cx + 10):
        shop = shop.cut(mk(9, 1.5, 6, V(x, cy - 16.05, ztop + 8)))
    roof = mk(56, 40, 3, V(cx - 28, cy - 20, ztop + 19))
    awning = mk(50, 6, 2, V(cx - 25, cy - 21, ztop + 15.5))
    sign = mk(30, 2.7, 4.5, V(cx - 15, cy - 19, ztop + 13))
    scene = base.fuse(shop).fuse(roof).fuse(awning).fuse(sign)
    # Engraved sign motif: two eyes + a line suggest a smiling burger without
    # creating small separate pieces. This is intentionally simple CAD art.
    for x in (cx - 5, cx + 5):
        dot = cyl(1.1, 1.0, V(x, cy - 19.1, ztop + 15.2), V(0, 1, 0))
        scene = scene.cut(dot)
    # Pins attach to platform and fit into pockets in the lid (radial gap 0.5mm).
    for x, y in restaurant_socket_centers(cfg):
        scene = scene.fuse(cyl(1.85, 3.1, V(x, y, ztop - 2.7)))
    return scene.removeSplitter()


def make_hamburger(cfg, Part, V):
    """One-piece round chibi with engraved facial features, no loose eyes."""
    mk, cyl, sphere = Part.makeBox, Part.makeCylinder, Part.makeSphere
    scale = cfg.figure_height / 32.0
    cx, cy, z0 = cfg.width / 2.0, cfg.depth / 2.0, cfg.floor + 0.4

    def p(dx, dy, dz):
        return V(cx + dx * scale, cy + dy * scale, z0 + dz * scale)

    bun_bottom = cyl(11.5 * scale, 5.2 * scale, p(0, 0, 7.2))
    patty = cyl(12.0 * scale, 3.3 * scale, p(0, 0, 12.4))
    cheese = mk(23 * scale, 23 * scale, 1.6 * scale, p(-11.5, -11.5, 15.7))
    bun_mid = cyl(11.8 * scale, 4.2 * scale, p(0, 0, 17.3))
    cap = sphere(12 * scale, p(0, 0, 20.0)).common(
        mk(26 * scale, 26 * scale, 11.0 * scale, p(-13, -13, 21.0)))
    result = bun_bottom.fuse(patty).fuse(cheese).fuse(bun_mid).fuse(cap)
    for dx in (-6.5, 6.5):
        result = result.fuse(sphere(3.7 * scale, p(dx, -3, 4.4)))
    # Raised front of head faces -Y. Shallow cuts create safely integrated eyes.
    for dx in (-4.2, 4.2):
        result = result.cut(cyl(1.2 * scale, 5.3 * scale,
                                p(dx, -13.6, 25.0), V(0, 1, 0)))
    if cfg.expression == "Sorprendida":
        result = result.cut(cyl(1.65 * scale, 4.1 * scale,
                                p(0, -13.2, 21.0), V(0, 1, 0)))
    else:
        result = result.cut(mk(4.6 * scale, 3.1 * scale, .85 * scale,
                               p(-2.3, -13.2, 20.5)))
    return result.removeSplitter()


def make_side_emboss(cfg, face, L, Part, V, to_global):
    """Fused low-profile burger-shaped relief in the lower area of each side."""
    mk, cyl = Part.makeBox, Part.makeCylinder
    u0, zz = L/2.0, cfg.floor + 22
    # Two horizontal bun bands, plate detail; shape touches the outer wall.
    base = mk(30, 1.15, 19.0, V(u0-15, -1.1, zz-9.5))
    for dz in (-4.0, 4.0):
        ridge = mk(21, .55, 2.1, V(u0-10.5, -1.55, zz+dz))
        base = base.fuse(ridge)
    disc = cyl(5.0, .8, V(u0, -1.12, zz), V(0, -1, 0))
    base = base.fuse(disc)
    return to_global(base.removeSplitter(), face, cfg.width, cfg.depth, V)
