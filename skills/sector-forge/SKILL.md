---
name: sector-forge
description: >
  SectorForge generates sci-fi dungeon, spaceship, and station battlemaps for
  virtual tabletops (Foundry VTT v13/v14, Roll20, Fantasy Grounds) from narrative
  direction. Claude designs the deck layout — rooms, corridors, doors, lighting,
  props — as a structured map-spec JSON, then a deterministic engine renders a
  top-down battlemap and auto-derives walls, doors, and dynamic lighting,
  exporting Universal VTT (.dd2vtt) and native Foundry scene JSON. Optional hybrid
  path swaps in ComfyUI/z-image art while preserving the VTT data. Use when the
  user asks for a sci-fi dungeon/ship/station map, a VTT-ready battlemap, a
  Foundry-importable scene with walls and lights, an encounter map for a sci-fi
  campaign, or to turn a described location into a playable tactical map.
version: 0.2.0
---

# SectorForge — Sci-Fi Dungeon Tile Mapper

Turn a described location ("a derelict mining station with a reactor core, three
crew quarters, and a med-bay") into a **playable VTT battlemap** with working
walls, doors, and dynamic lighting — exported for Foundry VTT and any Universal
VTT-compatible tabletop.

## The division of labor

- **You (Claude) design the layout.** Place rooms on a grid, route corridors,
  position doors/lights/props. This is the creative work.
- **The engine guarantees correctness.** It renders the image and *auto-derives*
  walls and line-of-sight from the floor boundary, so dynamic lighting and
  vision "just work" on import. You never hand-place walls.

You emit a **map-spec JSON**; the engine emits the map files.

## Workflow

### 1. Gather the brief
If the user hasn't specified, settle (briefly — infer sensible defaults rather
than interrogating):
- **Setting/theme** → one of: `clean_ship`, `derelict_industrial`,
  `station_lab`, `military_bunker`, `alien_organic`.
- **Rooms** and rough sizes, and how they connect.
- **Grid size** in cells (default 30×22) and feet-per-cell (default 5 ft).
- **Mood / lighting** (emergency red, sterile white, bioluminescent, etc.).

### 2. Design the deck → write the spec
Lay the rooms out on the cell grid in your head (or sketch coordinates), then
write a map-spec JSON. **Read `references/map-spec-schema.md`** for the full field
reference, and `references/themes.md` for theme palettes and prop/floor options.

Layout rules of thumb:
- Keep rooms inside `0..size.w` / `0..size.h`; leave a 1-cell margin so walls
  aren't flush with the image edge.
- Rooms are rectangles. For non-rectangular spaces, overlap several rooms.
- Connect rooms with `corridors` using `{ "from": "...", "to": "...", "width": N }`
  (auto L-routes between room centers) — quick and reliable.
- Put a **door** on the wall where a corridor meets a room, using the cell just
  inside the room and the `side` facing the corridor (`n/s/e/w`).
- Add **lights** at fixtures and hazards; range is in cells.
- Add **props** for readability (consoles, reactor, beds/pods, crates, terminals).
- For a dark, lights-only scene (derelict, power-out), set top-level
  `"darkness": 1` so Foundry disables global light and only your placed lights
  illuminate. Leave it at `0` (default) for a fully-lit tactical map.

Write the spec to a file, e.g. `out/<name>.json`.

### 3. Build the map files
Run the engine (requires Python 3.9+ and Pillow):

```bash
python ${CLAUDE_PLUGIN_ROOT}/scripts/build_map.py path/to/spec.json --out out
```

Outputs in `out/`:
- `<name>.png` — top-down procedural battlemap
- `<name>.dd2vtt` — **Universal VTT** (image + walls + doors + lights); imports
  into Foundry (drag-drop in v11+, or the *Universal Battlemap Importer*),
  Roll20 (*UniversalVTTImporter* script), and Fantasy Grounds.
- `<name>.fvtt.json` — **native Foundry scene** (v13/v14 data model)
- `<name>.prompt.txt` — z-image/ComfyUI art prompt for the hybrid path

If Pillow is missing: `pip install Pillow`.

### 4. Show and iterate
Display the PNG to the user. Iterate by editing the spec and re-running —
geometry is deterministic, so the same spec always yields the same map.

### 5. (Optional) Hybrid AI art
For painted/photoreal backgrounds instead of the clean procedural tiles:
1. Take `<name>.prompt.txt` and generate art with ComfyUI z-image turbo (the
   `rpg-map-creator` skill covers that pipeline). For best alignment use the
   procedural `<name>.png` as an img2img/control input so room positions match.
2. Re-pack the finished art, keeping all derived walls/lights:
   ```bash
   python ${CLAUDE_PLUGIN_ROOT}/scripts/repack_image.py spec.json art.png --out out
   ```
   This rewrites `<name>.dd2vtt` and `<name>.fvtt.json` around the new image.

See `references/vtt-formats.md` for import steps and per-VTT notes.

## Importing (quick reference)
- **Foundry VTT (recommended):** drag the `.dd2vtt` onto the Scenes tab (v11+) —
  it creates a scene with walls, doors, and lights automatically. Or import the
  `.fvtt.json` into a newly-created empty scene via right-click → *Import Data*
  (place the `.png` where `background.src` points).
- **Roll20:** use the *UniversalVTTImporter* API script with the `.dd2vtt`.
- **Fantasy Grounds / Arkenforge / others:** load the `.dd2vtt`.

## Files
- `references/map-spec-schema.md` — full spec field reference (read before authoring)
- `references/themes.md` — themes, floor types, prop catalog, lighting recipes
- `references/vtt-formats.md` — export format details and import instructions
- `${CLAUDE_PLUGIN_ROOT}/scripts/build_map.py` — spec → PNG + UVTT + Foundry
- `${CLAUDE_PLUGIN_ROOT}/scripts/repack_image.py` — swap in AI art, keep VTT data
- `${CLAUDE_PLUGIN_ROOT}/examples/derelict-station.json` — worked example
