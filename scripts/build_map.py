#!/usr/bin/env python3
"""
build_map.py — turn a map-spec JSON into VTT-ready map files.

Usage:
    python build_map.py SPEC.json [--out DIR] [--no-image] [--prompt-only]

Outputs (written to --out, default ./out):
    <name>.png          procedural top-down battlemap
    <name>.dd2vtt       Universal VTT (image + walls + doors + lights)
    <name>.fvtt.json    native Foundry VTT scene document (v12/v13 data model)
    <name>.prompt.txt   z-image/ComfyUI art prompt for the hybrid path

The map-spec schema is documented in references/map-spec-schema.md.
Coordinates in the spec are in GRID UNITS (cells); cell (cx,cy) spans
[cx,cx+1] x [cy,cy+1]. Pixels = grid * grid.cell_px.
"""

import argparse
import base64
import json
import math
import os
import re
import sys

import geometry

try:
    import render
    HAVE_PIL = True
except Exception:
    HAVE_PIL = False


def _slug(name):
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "map"


def _hex_rgb(h):
    h = h.lstrip("#")
    if len(h) == 8:
        h = h[2:]
    return "#" + h.lower()


def _to_argb(h, alpha="ff"):
    h = h.lstrip("#")
    if len(h) == 8:
        return h.lower()
    return (alpha + h).lower()


# --- Universal VTT (.dd2vtt) -------------------------------------------------

def export_uvtt(spec, model, image_path, pixels_per_grid):
    distance = spec["grid"].get("distance", 5)
    los = [
        [{"x": float(a[0]), "y": float(a[1])}, {"x": float(b[0]), "y": float(b[1])}]
        for (a, b) in model["segments"]
    ]

    portals = []
    for p in model["portals"]:
        (x1, y1), (x2, y2) = p["p0"], p["p1"]
        horizontal = y1 == y2
        portals.append({
            "position": {"x": (x1 + x2) / 2.0, "y": (y1 + y2) / 2.0},
            "bounds": [{"x": float(x1), "y": float(y1)}, {"x": float(x2), "y": float(y2)}],
            "rotation": 0.0 if horizontal else math.pi / 2,
            "closed": p["state"] != "open",
            "freestanding": p["type"] in ("door", "airlock"),
        })

    lights = []
    for lt in spec.get("lights", []):
        lights.append({
            "position": {"x": float(lt["x"]), "y": float(lt["y"])},
            "range": float(lt.get("range", 4)),      # in grid units (cells)
            "intensity": float(lt.get("intensity", 1.0)),
            "color": _to_argb(lt.get("color", "#ffffff")),
            "shadows": bool(lt.get("shadows", True)),
        })

    data = {
        "format": 0.3,
        "resolution": {
            "map_origin": {"x": 0, "y": 0},
            "map_size": {"x": int(spec["size"]["w"]), "y": int(spec["size"]["h"])},
            "pixels_per_grid": int(pixels_per_grid),
        },
        "line_of_sight": los,
        "objects_line_of_sight": [],
        "portals": portals,
        "lights": lights,
        "environment": {
            "baked_lighting": False,
            "ambient_light": _to_argb(spec.get("ambient", "#222230")),
        },
    }
    if image_path and os.path.exists(image_path):
        with open(image_path, "rb") as f:
            data["image"] = base64.b64encode(f.read()).decode("ascii")
    return data


# --- Foundry VTT scene document (v13 / v14) ----------------------------------
#
# Targets the Foundry v13/v14 Scene data model. Key differences vs v11:
#   * walls carry a `threshold` object (proximity-wall config)
#   * the removed top-level `globalLight` / `darkness` / `fogExploration` are
#     replaced by the `environment` and `fog` objects (added in v12, current in
#     v13/v14). Emitting the old fields would just be dropped on import.
# Enums (stable across v10-v14): movement/sense/sound 0=none, 20=normal;
# door 0=none 1=door 2=secret; ds 0=closed 1=open 2=locked.

WALL_NORMAL = 20
DOOR_TYPE = {"door": 1, "blast": 1, "airlock": 1, "secret": 2}
DOOR_STATE = {"closed": 0, "open": 1, "locked": 2}


def _wall(c, door=0, ds=0):
    return {
        "c": c,
        "light": WALL_NORMAL, "move": WALL_NORMAL,
        "sight": WALL_NORMAL, "sound": WALL_NORMAL,
        "dir": 0, "door": door, "ds": ds,
        "threshold": {"light": None, "sight": None, "sound": None, "attenuation": False},
    }


def export_foundry(spec, model, image_rel, width_px, height_px, cell_px):
    distance = spec["grid"].get("distance", 5)

    walls = [
        _wall([a[0] * cell_px, a[1] * cell_px, b[0] * cell_px, b[1] * cell_px])
        for (a, b) in model["segments"]
    ]
    for p in model["portals"]:
        (x1, y1), (x2, y2) = p["p0"], p["p1"]
        walls.append(_wall(
            [x1 * cell_px, y1 * cell_px, x2 * cell_px, y2 * cell_px],
            door=DOOR_TYPE.get(p["type"], 1),
            ds=DOOR_STATE.get(p["state"], 0),
        ))

    lights = []
    for lt in spec.get("lights", []):
        rng_ft = float(lt.get("range", 4)) * distance
        lights.append({
            "x": lt["x"] * cell_px, "y": lt["y"] * cell_px,
            "elevation": 0, "rotation": 0, "walls": True, "vision": False,
            "config": {
                "negative": False, "priority": 0,
                "alpha": min(1.0, float(lt.get("intensity", 1.0)) * 0.5),
                "angle": 360, "bright": rng_ft / 2.0, "dim": rng_ft,
                "color": _hex_rgb(lt.get("color", "#ffffff")),
                "coloration": 1, "attenuation": 0.5, "luminosity": 0.5,
                "saturation": 0, "contrast": 0, "shadows": 0,
                "animation": {"type": lt.get("animation", ""), "speed": 5,
                              "intensity": 5, "reverse": False},
                "darkness": {"min": 0, "max": 1},
            },
        })

    darkness = max(0.0, min(1.0, float(spec.get("darkness", 0))))

    return {
        "name": spec.get("name", "Untitled Map"),
        "navigation": True,
        "width": width_px, "height": height_px, "padding": 0.25,
        "backgroundColor": _hex_rgb(spec.get("ambient", "#000000")),
        "grid": {
            "type": 1, "size": cell_px, "distance": distance,
            "units": spec["grid"].get("units", "ft"),
            "style": "solidLines", "thickness": 1, "color": "#000000", "alpha": 0.2,
        },
        "background": {"src": image_rel},
        "tokenVision": True,
        "fog": {
            "exploration": True, "reset": 0, "overlay": None,
            "colors": {"explored": None, "unexplored": None},
        },
        "environment": {
            "darknessLevel": darkness, "darknessLock": False, "cycle": True,
            "globalLight": {
                "enabled": darkness < 1, "alpha": 0.5, "bright": False,
                "color": None, "coloration": 1, "luminosity": 0,
                "saturation": 0, "contrast": 0, "shadows": 0,
                "darkness": {"min": 0, "max": 1},
            },
            "base": {"hue": 0, "intensity": 0, "luminosity": 0, "saturation": 0, "shadows": 0},
            "dark": {"hue": 0, "intensity": 0, "luminosity": 0, "saturation": 0, "shadows": 0},
        },
        "walls": walls,
        "lights": lights,
        "tokens": [], "notes": [], "sounds": [], "drawings": [],
        "tiles": [], "templates": [], "regions": [],
        "flags": {"sector-forge": {"version": "0.2.0", "foundryTarget": "v13-v14"}},
    }


# --- ComfyUI / z-image hybrid prompt -----------------------------------------

def build_art_prompt(spec, model):
    theme = spec.get("theme", "clean_ship").replace("_", " ")
    rooms = ", ".join(
        r.get("label", r["id"]) for r in model["rooms"].values()
    )
    w, h = spec["size"]["w"], spec["size"]["h"]
    return (
        f"top-down orthographic battle map, sci-fi {theme} interior, "
        f"spaceship/station deck plan, {w}x{h} grid tiles, "
        f"rooms: {rooms}. Metal bulkheads, panel flooring, glowing consoles, "
        f"airlocks and blast doors, cabling and vents. "
        f"Clean tactical VTT map, high contrast, even lighting, sharp grid alignment, "
        f"no perspective, no characters, no tokens, highly detailed, 4k. "
        f"NEGATIVE: isometric, perspective, people, text, watermark, blurry"
    )


# --- main --------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(description="Build VTT map files from a map-spec JSON.")
    ap.add_argument("spec", help="path to map-spec JSON")
    ap.add_argument("--out", default="out", help="output directory (default: out)")
    ap.add_argument("--no-image", action="store_true", help="skip PNG rendering")
    ap.add_argument("--prompt-only", action="store_true",
                    help="only emit the z-image art prompt (no geometry/exports)")
    args = ap.parse_args(argv)

    with open(args.spec, "r", encoding="utf-8-sig") as f:  # tolerate BOM (Windows)
        spec = json.load(f)

    spec.setdefault("grid", {}).setdefault("cell_px", 140)
    spec["grid"].setdefault("distance", 5)
    spec.setdefault("size", {"w": 20, "h": 20})

    os.makedirs(args.out, exist_ok=True)
    name = _slug(spec.get("name", "map"))
    cell_px = int(spec["grid"]["cell_px"])

    model = geometry.derive(spec)

    if args.prompt_only:
        prompt = build_art_prompt(spec, model)
        ppath = os.path.join(args.out, f"{name}.prompt.txt")
        with open(ppath, "w", encoding="utf-8") as f:
            f.write(prompt)
        print(f"[prompt] {ppath}")
        return 0

    # render the procedural battlemap
    png_path = os.path.join(args.out, f"{name}.png")
    width_px = int(spec["size"]["w"]) * cell_px
    height_px = int(spec["size"]["h"]) * cell_px
    if not args.no_image:
        if not HAVE_PIL:
            print("WARNING: Pillow not installed — skipping PNG. `pip install Pillow`",
                  file=sys.stderr)
        else:
            width_px, height_px = render.render(model, spec, png_path)
            print(f"[png]    {png_path}  ({width_px}x{height_px})")

    # Universal VTT
    uvtt = export_uvtt(spec, model, png_path if os.path.exists(png_path) else None, cell_px)
    uvtt_path = os.path.join(args.out, f"{name}.dd2vtt")
    with open(uvtt_path, "w", encoding="utf-8") as f:
        json.dump(uvtt, f)
    print(f"[uvtt]   {uvtt_path}  (walls:{len(uvtt['line_of_sight'])} "
          f"doors:{len(uvtt['portals'])} lights:{len(uvtt['lights'])})")

    # Foundry scene
    fvtt = export_foundry(spec, model, f"{name}.png", width_px, height_px, cell_px)
    fvtt_path = os.path.join(args.out, f"{name}.fvtt.json")
    with open(fvtt_path, "w", encoding="utf-8") as f:
        json.dump(fvtt, f, indent=2)
    print(f"[fvtt]   {fvtt_path}  (walls:{len(fvtt['walls'])} lights:{len(fvtt['lights'])})")

    # hybrid art prompt
    prompt = build_art_prompt(spec, model)
    ppath = os.path.join(args.out, f"{name}.prompt.txt")
    with open(ppath, "w", encoding="utf-8") as f:
        f.write(prompt)
    print(f"[prompt] {ppath}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
