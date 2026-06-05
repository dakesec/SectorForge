# Export Formats & Import Instructions

The engine emits two structured map files plus the image and an art prompt.

## 1. Universal VTT — `<name>.dd2vtt`

The portable, cross-VTT format (same family as `.uvtt` / `.df2vtt`). A JSON
object with the map image embedded as base64 plus collision and lighting data.

Structure produced:
```jsonc
{
  "format": 0.3,
  "resolution": {
    "map_origin": { "x": 0, "y": 0 },
    "map_size":   { "x": <cols>, "y": <rows> },   // in cells
    "pixels_per_grid": <cell_px>
  },
  "line_of_sight": [ [ {"x":..,"y":..}, {"x":..,"y":..} ], ... ],  // walls, grid units
  "objects_line_of_sight": [],
  "portals": [ { "position":{}, "bounds":[{},{}], "rotation":<rad>,
                "closed":true, "freestanding":bool } ],            // doors
  "lights":  [ { "position":{}, "range":<cells>, "intensity":0-1,
                "color":"aarrggbb", "shadows":bool } ],
  "environment": { "baked_lighting": false, "ambient_light": "aarrggbb" },
  "image": "<base64 PNG>"
}
```
Notes:
- Coordinates in `line_of_sight` and `portals` are in **grid units**, not pixels.
- Colors are 8-digit **ARGB** hex (alpha first).
- `baked_lighting` is false so the VTT applies its own dynamic lighting.

### Import
- **Foundry VTT (v11+):** drag the `.dd2vtt` file onto the *Scenes* sidebar. A
  scene is created automatically with walls, doors, and lights. (Older Foundry:
  use the *Universal Battlemap Importer* module.)
- **Roll20:** install the *UniversalVTTImporter* API/mod script, then import the
  `.dd2vtt` — it builds dynamic-lighting walls, doors/windows, and lights.
- **Fantasy Grounds, Arkenforge, AboveVTT, Owlbear Rodeo (via tools):** load the
  `.dd2vtt` per the app's UVTT import flow.

## 2. Foundry scene — `<name>.fvtt.json`

A native Foundry **Scene document** targeting the **v13/v14** data model.

- `walls[]`: each `{ "c":[x1,y1,x2,y2], "light":20, "move":20, "sight":20,
  "sound":20, "dir":0, "door":0, "ds":0, "threshold":{...} }`. Coordinates in
  **pixels**. Enums (stable v10–v14): movement/sense `0`=none `20`=normal;
  `door` `0`=none `1`=door `2`=secret; `ds` (door state) `0`=closed `1`=open
  `2`=locked. `threshold` is the v12+ proximity-wall object (`{light, sight,
  sound, attenuation}`), emitted as nulls/false for normal walls.
- `lights[]`: `{ "x":px, "y":px, "elevation":0, "rotation":0, "walls":true,
  "vision":false, "config":{ "negative":false, "priority":0, "dim":<ft>,
  "bright":<ft>, "color":"#rrggbb", "alpha":.., "coloration":1,
  "attenuation":.., "animation":{...}, "darkness":{...} } }`. `dim` =
  `range × grid.distance`; `bright` = half. The fuller `config` matches the
  v13/v14 AmbientLight schema.
- `grid`: `{ "type":1, "size":<cell_px>, "distance":<ft>, "units":"ft",
  "style":"solidLines", "thickness":1, "color":"#000000", "alpha":0.2 }`.
- `environment` / `fog`: v12+ replaced the old top-level `globalLight`,
  `darkness`, and `fogExploration` fields. SectorForge emits the
  `environment` object (`darknessLevel`, `globalLight{...}`, `base`, `dark`) and
  the `fog` object instead. Spec `darkness` (0–1) drives `environment.darknessLevel`
  and toggles `globalLight.enabled`.
- `background.src` points at `<name>.png` (or your art image after repacking).

### Import
1. In Foundry, create a **new empty scene**.
2. Right-click it in the *Scenes* directory → **Import Data** → select the
   `.fvtt.json`.
3. Ensure the referenced image (`background.src`) is uploaded to your world's
   data folder at the matching path (or edit `background.src` to where you put
   the PNG).

> Version note: Foundry's scene schema evolves between major versions. This
> targets **v13/v14**; on import Foundry cleans unknown fields and fills missing
> ones with defaults, so minor drift is tolerated. If a field is rejected on a
> much older/newer build, prefer the `.dd2vtt` import path, which is the most
> version-stable.

## 3. Image — `<name>.png`

The procedural top-down battlemap. Evenly lit and grid-aligned (no baked
shadows) so the VTT's dynamic lighting reads correctly. Dimensions are
`size.w × cell_px` by `size.h × cell_px`.

## 4. Art prompt — `<name>.prompt.txt`

A ready-to-use prompt for ComfyUI z-image turbo describing the deck for the
**hybrid** path. Generate art from it (optionally img2img-conditioned on the
procedural PNG for alignment), then run `repack_image.py` to rebuild the
`.dd2vtt` and `.fvtt.json` around the new art while keeping all walls and lights.

## Choosing a path
- **Fastest / most reliable:** ship the `.dd2vtt`. One file, walls + lights, works
  across VTTs.
- **Deep Foundry control:** import the `.fvtt.json` (lets you tweak the scene
  document directly).
- **Best looks:** hybrid — AI art background repacked with the derived VTT data.
