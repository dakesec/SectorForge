---
name: sector-forge
description: SectorForge generates sci-fi dungeon, spaceship, and station battlemaps for virtual tabletops (Foundry VTT v13/v14, Roll20, Fantasy Grounds) from narrative direction. Design a deck layout (rooms, corridors, doors, lighting, props) as a map-spec JSON, then a deterministic engine renders a top-down battlemap and auto-derives walls, doors, and dynamic lighting, exporting Universal VTT (.dd2vtt) and native Foundry scene JSON. Use when the user asks for a sci-fi dungeon, ship, or station map, a VTT-ready battlemap, a Foundry-importable scene with walls and lights, an encounter map for a sci-fi campaign, or to turn a described location into a playable tactical map.
license: GPL-3.0
---

# SectorForge — Sci-Fi Dungeon Tile Mapper

Turn a described location ("a derelict mining station with a reactor core, three
crew quarters, and a med-bay") into a **playable VTT battlemap** with working
walls, doors, and dynamic lighting — exported for Foundry VTT and any Universal
VTT-compatible tabletop.

This skill runs in the code-execution sandbox. You (Claude) design the layout as
a **map-spec JSON**; the bundled Python engine renders the image and *auto-derives*
walls and line-of-sight from the floor boundary, then exports the VTT files for
the user to download. You never hand-place walls.

## Environment setup (do this first)

The renderer needs **Pillow**. At the start of a session, ensure it is importable:

```bash
python -c "import PIL" 2>/dev/null || pip install pillow
```

All commands below assume the current working directory is this skill's folder
(so `scripts/...` resolves). If needed, `cd` into the skill directory first.

## Workflow

### 1. Gather the brief
If the user hasn't specified, infer sensible defaults rather than interrogating:
- **Theme** → one of `clean_ship`, `derelict_industrial`, `station_lab`,
  `military_bunker`, `alien_organic`.
- **Rooms** and rough sizes, and how they connect.
- **Grid** in cells (default 30x22) and feet-per-cell (default 5 ft).
- **Mood / lighting** (emergency red, sterile white, bioluminescent, etc.).

### 2. Design the deck and write the spec
Read `references/map-spec-schema.md` for every field, and `references/themes.md`
for palettes, floor types, props, and lighting recipes. Then write a map-spec
JSON to a working file, e.g. `map.json`.

Layout rules of thumb:
- Keep rooms inside `0..size.w` / `0..size.h`; leave a 1-cell margin.
- Rooms take any **`shape`**: `rect` (default), `circle`/`ellipse`, `diamond`,
  `octagon`, or `poly` (arbitrary `points`). `x,y,w,h` is the bounding box.
- Connect rooms with `corridors`: `{ "from": "roomA", "to": "roomB", "width": N }`.
- **Place doors with the connection form** `{ "from": "roomA", "to": "roomB",
  "type": "blast" }` — the engine finds the real opening and spans the door across
  it, so doors always match the entrance. (`autoDoors: true` seals every
  room-corridor opening at once.)
- Add **lights** at fixtures/hazards (range in cells) and **props** for clarity.

### 3. Build the map files
```bash
python scripts/build_map.py map.json --out out
```
Outputs in `out/`:
- `<name>.png` — top-down battlemap
- `<name>.dd2vtt` — **Universal VTT** (image + walls + doors + lights); imports
  into Foundry (drag-drop, v11+), Roll20 (UniversalVTTImporter), Fantasy Grounds
- `<name>.fvtt.json` — **native Foundry scene** (v13/v14 data model)
- `<name>.prompt.txt` — z-image/ComfyUI art prompt for the optional hybrid path

### 4. Show and deliver
Display the PNG inline, then make the `out/` files available for the user to
**download** (the `.dd2vtt` is the one most people want). Summarize how many
walls/doors/lights were generated. Iterate by editing the spec and re-running —
the engine is deterministic, so the same spec always yields the same map.

### 5. (Optional) Hybrid AI art
If the user wants painted/photoreal art instead of the procedural tiles: use
`out/<name>.prompt.txt` to generate a background image, then re-pack it while
keeping all derived walls/lights:
```bash
python scripts/repack_image.py map.json art.png --out out
```

## Importing (tell the user)
- **Foundry VTT:** drag the `.dd2vtt` onto the Scenes tab (v11+) for an
  auto-built scene with walls/doors/lights; or import the `.fvtt.json` into a new
  empty scene via right-click then Import Data (upload the PNG where
  `background.src` points).
- **Roll20:** the UniversalVTTImporter script with the `.dd2vtt`.
- **Fantasy Grounds / Arkenforge / others:** load the `.dd2vtt`.

## Files
- `references/map-spec-schema.md` — full spec field reference (read before authoring)
- `references/themes.md` — themes, floor types, prop catalog, lighting recipes
- `references/vtt-formats.md` — export format details and import steps
- `scripts/build_map.py` — spec to PNG + UVTT + Foundry + prompt
- `scripts/repack_image.py` — swap in AI art, keep VTT data
- `examples/derelict-station.json` — worked example (shapes + connection doors)
