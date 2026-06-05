#!/usr/bin/env python3
"""
repack_image.py — the hybrid step.

Take a finished art image (e.g. ComfyUI z-image output) and rebuild the UVTT
(.dd2vtt) and Foundry scene using THAT image as the background, while keeping
all walls / doors / lights derived from the original map-spec.

Usage:
    python repack_image.py SPEC.json ART.png [--out DIR]

The art image should be a top-down render aligned to the same grid as the spec
(width = size.w * cell_px is ideal). If the art is a different resolution, the
exporter rescales pixels-per-grid so the geometry still lines up.
"""

import argparse
import json
import os
import shutil
import sys

import geometry
import build_map as bm

try:
    from PIL import Image
    HAVE_PIL = True
except Exception:
    HAVE_PIL = False


def main(argv=None):
    ap = argparse.ArgumentParser(description="Repack VTT files around a finished art image.")
    ap.add_argument("spec")
    ap.add_argument("art", help="path to the finished background image (PNG/WebP/JPG)")
    ap.add_argument("--out", default="out")
    args = ap.parse_args(argv)

    with open(args.spec, "r", encoding="utf-8-sig") as f:  # tolerate BOM (Windows)
        spec = json.load(f)
    spec.setdefault("grid", {}).setdefault("cell_px", 140)
    spec["grid"].setdefault("distance", 5)
    spec.setdefault("size", {"w": 20, "h": 20})

    os.makedirs(args.out, exist_ok=True)
    name = bm._slug(spec.get("name", "map"))
    model = geometry.derive(spec)

    # Determine art dimensions and a grid scale that keeps geometry aligned.
    if HAVE_PIL:
        with Image.open(args.art) as im:
            art_w, art_h = im.size
    else:
        art_w = int(spec["size"]["w"]) * int(spec["grid"]["cell_px"])
        art_h = int(spec["size"]["h"]) * int(spec["grid"]["cell_px"])
        print("WARNING: Pillow not installed; assuming art matches spec resolution.",
              file=sys.stderr)

    ppg = round(art_w / float(spec["size"]["w"]))
    if HAVE_PIL and abs(art_h - ppg * spec["size"]["h"]) > ppg * 0.5:
        print(f"WARNING: art aspect ({art_w}x{art_h}) does not match grid "
              f"{spec['size']['w']}x{spec['size']['h']}; walls may be offset.",
              file=sys.stderr)

    # Copy the art next to the scene so Foundry's background.src resolves.
    art_ext = os.path.splitext(args.art)[1] or ".png"
    art_dest = os.path.join(args.out, f"{name}{art_ext}")
    if os.path.abspath(args.art) != os.path.abspath(art_dest):
        shutil.copyfile(args.art, art_dest)

    # UVTT with the art embedded
    uvtt = bm.export_uvtt(spec, model, art_dest, ppg)
    uvtt_path = os.path.join(args.out, f"{name}.dd2vtt")
    with open(uvtt_path, "w", encoding="utf-8") as f:
        json.dump(uvtt, f)
    print(f"[uvtt]  {uvtt_path}  (ppg {ppg})")

    # Foundry scene pointing at the art
    fvtt = bm.export_foundry(spec, model, f"{name}{art_ext}", art_w, art_h, ppg)
    fvtt_path = os.path.join(args.out, f"{name}.fvtt.json")
    with open(fvtt_path, "w", encoding="utf-8") as f:
        json.dump(fvtt, f, indent=2)
    print(f"[fvtt]  {fvtt_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
