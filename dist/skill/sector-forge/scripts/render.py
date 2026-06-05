"""
render.py — procedural top-down sci-fi tile rendering with Pillow.

Produces a clean, VTT-neutral battlemap: themed floor panels, bulkhead walls,
doors, light fixtures, and simple props. Lighting is intentionally NOT baked in
(VTTs apply dynamic lighting), so the image stays evenly lit and readable.
"""

from PIL import Image, ImageDraw

# Each theme: void (outside), floor base, floor alt (panel checker), seam line,
# wall body, wall trim (inner highlight), accent (consoles/screens).
THEMES = {
    "clean_ship": {
        "void": (8, 10, 16), "floor": (54, 62, 78), "floor_alt": (46, 53, 67),
        "seam": (30, 36, 48), "wall": (150, 162, 180), "wall_trim": (90, 100, 120),
        "accent": (90, 200, 255),
    },
    "derelict_industrial": {
        "void": (6, 6, 7), "floor": (48, 44, 40), "floor_alt": (40, 36, 33),
        "seam": (24, 21, 19), "wall": (96, 88, 78), "wall_trim": (60, 54, 47),
        "accent": (210, 130, 40),
    },
    "station_lab": {
        "void": (10, 14, 18), "floor": (70, 80, 88), "floor_alt": (60, 70, 78),
        "seam": (38, 46, 52), "wall": (175, 188, 196), "wall_trim": (110, 124, 132),
        "accent": (60, 230, 200),
    },
    "military_bunker": {
        "void": (10, 12, 9), "floor": (52, 58, 46), "floor_alt": (44, 50, 39),
        "seam": (26, 30, 23), "wall": (108, 116, 96), "wall_trim": (66, 72, 58),
        "accent": (180, 200, 90),
    },
    "alien_organic": {
        "void": (10, 6, 16), "floor": (54, 40, 66), "floor_alt": (46, 34, 58),
        "seam": (30, 20, 40), "wall": (140, 96, 170), "wall_trim": (86, 58, 108),
        "accent": (90, 240, 200),
    },
}
DEFAULT_THEME = "clean_ship"


def _hash(cx, cy, salt=0):
    """Deterministic pseudo-random in [0,1) from cell coords (no RNG state)."""
    h = (cx * 73856093) ^ (cy * 19349663) ^ (salt * 83492791)
    return ((h & 0x7FFFFFFF) % 10000) / 10000.0


def _shade(color, factor):
    return tuple(max(0, min(255, int(c * factor))) for c in color)


def render(model, spec, out_path):
    pal = THEMES.get(spec.get("theme", DEFAULT_THEME), THEMES[DEFAULT_THEME])
    cell = int(spec["grid"]["cell_px"])
    W = int(spec["size"]["w"]) * cell
    H = int(spec["size"]["h"]) * cell

    img = Image.new("RGB", (W, H), pal["void"])
    d = ImageDraw.Draw(img, "RGBA")

    floor = model["floor"]
    floor_kind = {}  # cell -> floor variant from owning room (any shape)
    for room in model["rooms"].values():
        kind = room.get("floor", "plating")
        for c in room.get("_cells", ()):
            floor_kind[c] = kind

    # --- floor tiles ---
    for (cx, cy) in floor:
        x0, y0 = cx * cell, cy * cell
        kind = floor_kind.get((cx, cy), "plating")
        base = pal["floor"] if (cx + cy) % 2 == 0 else pal["floor_alt"]
        if _hash(cx, cy, 7) < 0.12:  # scattered wear/variation
            base = _shade(base, 0.88 if kind != "tile" else 1.08)
        d.rectangle([x0, y0, x0 + cell, y0 + cell], fill=base)
        _draw_floor_detail(d, x0, y0, cell, kind, pal, cx, cy)

    # --- panel seams between adjacent floor cells ---
    for (cx, cy) in floor:
        x0, y0 = cx * cell, cy * cell
        if (cx + 1, cy) in floor:
            d.line([x0 + cell, y0, x0 + cell, y0 + cell], fill=pal["seam"], width=1)
        if (cx, cy + 1) in floor:
            d.line([x0, y0 + cell, x0 + cell, y0 + cell], fill=pal["seam"], width=1)

    # --- optional grid overlay ---
    if spec.get("grid", {}).get("overlay", True):
        gc = (255, 255, 255, 28)
        for (cx, cy) in floor:
            x0, y0 = cx * cell, cy * cell
            d.rectangle([x0, y0, x0 + cell, y0 + cell], outline=gc, width=1)

    # --- props (decorative) ---
    for p in spec.get("props", []):
        _draw_prop(d, p, cell, pal)

    # --- walls (bulkheads) ---
    wt = max(3, int(cell * 0.14))
    for (a, b) in model["segments"]:
        x1, y1 = a[0] * cell, a[1] * cell
        x2, y2 = b[0] * cell, b[1] * cell
        d.line([x1, y1, x2, y2], fill=pal["wall"], width=wt)
        d.line([x1, y1, x2, y2], fill=pal["wall_trim"], width=max(1, wt // 3))

    # --- doors ---
    for portal in model["portals"]:
        _draw_door(d, portal, cell, pal)

    # --- light fixtures (icon only; real light is dynamic in the VTT) ---
    for lt in spec.get("lights", []):
        lx, ly = lt["x"] * cell, lt["y"] * cell
        r = max(4, int(cell * 0.16))
        col = _hex_to_rgb(lt.get("color", "#ffffff"))
        d.ellipse([lx - r, ly - r, lx + r, ly + r], fill=col + (70,))
        d.ellipse([lx - r // 2, ly - r // 2, lx + r // 2, ly + r // 2], fill=col + (200,))

    img.save(out_path)
    return W, H


def _draw_floor_detail(d, x0, y0, cell, kind, pal, cx, cy):
    if kind == "grating":
        for i in range(1, 4):
            yy = y0 + cell * i / 4
            d.line([x0 + 2, yy, x0 + cell - 2, yy], fill=pal["seam"], width=1)
    elif kind == "tile":
        d.line([x0 + cell / 2, y0, x0 + cell / 2, y0 + cell], fill=pal["seam"], width=1)
        d.line([x0, y0 + cell / 2, x0 + cell, y0 + cell / 2], fill=pal["seam"], width=1)
    elif kind == "organic":
        if _hash(cx, cy, 3) < 0.5:
            d.arc([x0 + 4, y0 + 4, x0 + cell - 4, y0 + cell - 4],
                  start=int(_hash(cx, cy, 5) * 360), end=int(_hash(cx, cy, 6) * 360) + 180,
                  fill=_shade(pal["accent"], 0.5), width=2)
    elif kind == "hazard":
        for i in range(-1, int(cell / 8) + 1):
            d.line([x0 + i * 8, y0, x0 + i * 8 + cell, y0 + cell],
                   fill=(pal["accent"][0], pal["accent"][1], pal["accent"][2], 40), width=3)


def _draw_prop(d, p, cell, pal):
    cx, cy = p["x"] * cell, p["y"] * cell
    t = p.get("type", "crate")
    a = pal["accent"]
    if t == "console":
        d.rounded_rectangle([cx + cell*0.15, cy + cell*0.2, cx + cell*0.85, cy + cell*0.7],
                            radius=4, fill=_shade(pal["wall"], 0.6), outline=pal["wall"])
        d.rectangle([cx + cell*0.25, cy + cell*0.28, cx + cell*0.75, cy + cell*0.55],
                    fill=a + (180,))
    elif t == "crate":
        d.rectangle([cx + cell*0.2, cy + cell*0.2, cx + cell*0.8, cy + cell*0.8],
                    fill=_shade(pal["floor"], 1.3), outline=pal["seam"], width=2)
        d.line([cx + cell*0.2, cy + cell*0.2, cx + cell*0.8, cy + cell*0.8], fill=pal["seam"])
        d.line([cx + cell*0.8, cy + cell*0.2, cx + cell*0.2, cy + cell*0.8], fill=pal["seam"])
    elif t == "terminal":
        d.rectangle([cx + cell*0.3, cy + cell*0.1, cx + cell*0.7, cy + cell*0.45],
                    fill=a + (160,), outline=pal["wall"])
        d.rectangle([cx + cell*0.25, cy + cell*0.45, cx + cell*0.75, cy + cell*0.6],
                    fill=_shade(pal["wall"], 0.6))
    elif t == "reactor":
        for i, f in enumerate((1.0, 0.7, 0.4)):
            rr = cell * 0.4 * f
            d.ellipse([cx + cell/2 - rr, cy + cell/2 - rr, cx + cell/2 + rr, cy + cell/2 + rr],
                      outline=a, width=2, fill=a + (40 + i * 30,))
    elif t == "bed" or t == "pod":
        d.rounded_rectangle([cx + cell*0.2, cy + cell*0.1, cx + cell*0.8, cy + cell*0.9],
                            radius=6, fill=_shade(pal["floor"], 1.2), outline=pal["wall"])
    else:  # generic marker
        d.ellipse([cx + cell*0.3, cy + cell*0.3, cx + cell*0.7, cy + cell*0.7],
                  fill=_shade(pal["floor"], 1.4), outline=pal["wall"])


def _draw_door(d, portal, cell, pal):
    x1, y1 = portal["p0"][0] * cell, portal["p0"][1] * cell
    x2, y2 = portal["p1"][0] * cell, portal["p1"][1] * cell
    colors = {"door": (200, 200, 210), "blast": (215, 130, 40),
              "secret": pal["wall"], "airlock": (90, 200, 255)}
    col = colors.get(portal["type"], (200, 200, 210))
    wt = max(4, int(cell * 0.22))
    if portal["state"] == "open":
        # draw recessed (thin) when open
        d.line([x1, y1, x2, y2], fill=_shade(col, 0.5), width=max(2, wt // 2))
    else:
        d.line([x1, y1, x2, y2], fill=col, width=wt)
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        d.line([x1, y1, x2, y2], fill=_shade(col, 1.3), width=max(1, wt // 4))
        d.ellipse([mx - 2, my - 2, mx + 2, my + 2], fill=(20, 20, 20))


def _hex_to_rgb(h):
    h = h.lstrip("#")
    if len(h) == 8:  # ARGB
        h = h[2:]
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
