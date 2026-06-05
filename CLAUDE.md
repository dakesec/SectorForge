# CLAUDE.md

Guidance for Claude Code (and contributors) working in this repository.

## What this is

**SectorForge** is a Claude Code **plugin** that turns a described sci-fi location
into a VTT-ready battlemap. The user describes a place; Claude designs the deck
layout as a structured **map-spec JSON**; a deterministic Python engine renders a
top-down battlemap and **auto-derives walls, doors, and dynamic lighting**, then
exports:

- `*.dd2vtt` — **Universal VTT** (portable: Foundry, Roll20, Fantasy Grounds)
- `*.fvtt.json` — **native Foundry VTT scene**, targeting the **v13/v14** data model
- `*.png` — the procedural battlemap image
- `*.prompt.txt` — a ComfyUI z-image art prompt for the optional hybrid path

Core principle: **LLM for creativity, code for VTT-data correctness.** Claude
never hand-places walls — they are derived from the floor boundary, so the
exported line-of-sight and lighting are always consistent with the layout.

## Architecture / data flow

```
narrative direction
   │  Claude authors  →  map-spec JSON  (see skills/sector-forge/references/map-spec-schema.md)
   ▼
scripts/build_map.py            # CLI orchestrator + exporters
   ├─ scripts/geometry.py       # spec → floor occupancy → walls/doors/line-of-sight
   ├─ scripts/render.py         # floor model → procedural PNG (Pillow)
   ├─ export_uvtt(...)          # → .dd2vtt (image base64 + walls + portals + lights)
   ├─ export_foundry(...)       # → .fvtt.json (Foundry v13/v14 Scene document)
   └─ build_art_prompt(...)     # → .prompt.txt (z-image hybrid prompt)

scripts/repack_image.py         # hybrid: swap procedural PNG for AI art, keep VTT data
```

`geometry.derive(spec)` is the heart of correctness. It:
1. Rasterizes rooms + corridors into a set of floor cells.
2. Marks every cell-edge on the floor/non-floor boundary as a wall unit-edge.
3. Carves door edges out of the wall set (doors become portals).
4. Merges colinear unit-edges into maximal straight wall segments.

## Coordinate conventions (important)

- **Grid units = cells.** Cell `(cx, cy)` occupies `[cx, cx+1] × [cy, cy+1]`.
  Origin top-left; x→right, y→down. Pixels = grid × `grid.cell_px`.
- A **unit edge** is one cell side: `('H', X, Y)` = horizontal `(X,Y)→(X+1,Y)`;
  `('V', X, Y)` = vertical `(X,Y)→(X,Y+1)`.
- UVTT `line_of_sight` / `portals` are in **grid units**; Foundry `walls.c` and
  `lights.x/y` are in **pixels**. Keep that distinction when editing exporters.

## Run / test

Requires **Python 3.9+** and **Pillow** (`pip install Pillow`).

```bash
# build all outputs from a spec
python scripts/build_map.py examples/derelict-station.json --out out

# hybrid: rebuild VTT files around a finished art image (keeps walls/lights)
python scripts/repack_image.py examples/derelict-station.json art.png --out out

# quick variants
python scripts/build_map.py spec.json --out out --no-image      # skip PNG
python scripts/build_map.py spec.json --out out --prompt-only   # only the art prompt
```

There is no formal test suite yet. To sanity-check a change, run the example and
validate the JSON, e.g. confirm the Foundry scene has `environment`/`fog`,
walls have `threshold`, and there are no legacy top-level `globalLight`/
`fogExploration` fields. Generated output lives under `out/` and is gitignored.

## Foundry v13/v14 specifics

`export_foundry` in `scripts/build_map.py` targets the v13/v14 Scene schema:
- Walls: `c` (pixels), `light/move/sight/sound` enums (`0`=none, `20`=normal),
  `dir`, `door` (`0/1/2`), `ds` (`0/1/2`), and the v12+ `threshold` object.
- Lights: the fuller `config` (`negative`, `priority`, `dim`, `bright`, `color`,
  `alpha`, `coloration`, `attenuation`, `animation`, `darkness`…).
- Scene-level lighting uses the `environment` object (`darknessLevel`,
  `globalLight{...}`, `base`, `dark`) and `fog` object — **not** the removed v11
  top-level fields. Foundry cleans unknown fields and fills defaults on import,
  so minor drift is tolerated; `.dd2vtt` is the most version-stable fallback.

When bumping Foundry versions, update only `export_foundry` (and the
`flags.sector-forge.foundryTarget` string) — the UVTT exporter is
version-independent.

## Conventions

- **Deterministic engine.** No `random`, no time/date calls. Procedural texture
  variation uses a coordinate hash (`render._hash`). Same spec → identical map.
- **One dependency:** Pillow. Everything else is stdlib. Keep it that way.
- **BOM-tolerant JSON:** spec files are read with `utf-8-sig` (Windows tooling,
  e.g. PowerShell `Out-File`, emits a UTF-8 BOM that breaks plain `json.load`).
- **Plugin layout** follows Claude Code conventions: `.claude-plugin/plugin.json`
  manifest, `commands/` (the `/dungeon` slash command), `skills/sector-forge/`
  (auto-activating skill + `references/`), `scripts/` (the engine). Use
  `${CLAUDE_PLUGIN_ROOT}` for intra-plugin paths in skill/command docs.
- **kebab-case** for plugin/skill/command/file names.

## Extending

- **New theme:** add a palette entry to `render.THEMES` and document it in
  `skills/sector-forge/references/themes.md`.
- **New prop:** add a branch in `render._draw_prop` and list it in `themes.md`
  and the schema's prop catalog.
- **New floor type:** add a branch in `render._draw_floor_detail` + docs.
- **Schema changes:** update `skills/sector-forge/references/map-spec-schema.md`
  (it is the contract Claude reads when authoring specs).

## Known limitations (v0.2)

- Rooms are rectangles; compose/overlap for L/T/cross shapes.
- Props are decorative (non-collidable); model sight-blockers as tiny rooms.
- Single deck per spec; multi-level stations = one spec per deck.
