# Map-Spec Schema

The map-spec is a single JSON object. All coordinates are in **grid units
(cells)**. Cell `(cx, cy)` occupies the square `[cx, cx+1] × [cy, cy+1]`. The
top-left of the map is `(0, 0)`; x increases right, y increases down. Pixels =
grid × `grid.cell_px`.

## Top-level fields

| Field       | Type   | Required | Default          | Notes |
|-------------|--------|----------|------------------|-------|
| `name`      | string | yes      | —                | Used for output filenames and the Foundry scene name. |
| `theme`     | string | no       | `clean_ship`     | One of the palettes in `themes.md`. |
| `ambient`   | string | no       | `#222230`        | Ambient/scene background color (hex). |
| `darkness`  | number | no       | `0`              | Foundry scene darkness 0–1. `0` = fully lit; `1` = dark, only placed `lights` illuminate (great for derelicts/power-out). Sets `environment.darknessLevel` and toggles global light. |
| `grid`      | object | no       | see below        | Grid configuration. |
| `size`      | object | yes      | `{w:20,h:20}`    | Map size **in cells**: `{ "w": <cols>, "h": <rows> }`. |
| `rooms`     | array  | yes      | —                | At least one room (the floor). |
| `corridors` | array  | no       | `[]`             | Connections between rooms. |
| `doors`     | array  | no       | `[]`             | Doors/airlocks (become portals). |
| `lights`    | array  | no       | `[]`             | Dynamic light sources. |
| `props`     | array  | no       | `[]`             | Decorative objects for readability. |

### `grid`
```json
{ "cell_px": 140, "distance": 5, "units": "ft", "overlay": true }
```
- `cell_px` — pixels per cell in the rendered PNG (100–160 is a good range; 140
  gives crisp Foundry maps). Larger = sharper but bigger files.
- `distance` — in-world distance per cell (Foundry "grid distance"). 5 ft is D&D
  standard; many sci-fi systems use 1 m or 1.5 m.
- `units` — label for `distance` (`ft`, `m`, etc.).
- `overlay` — draw a faint grid on the PNG (true) or leave it clean (false).
  Turn **off** if your VTT draws its own grid.

## `rooms[]`
Floor areas of any shape. The union of all rooms + corridors is the walkable
floor; walls are auto-derived around its outer boundary, so **any shape works** —
the engine rasterizes the room to grid cells and walls/line-of-sight follow the
cell boundary.
```json
{ "id": "reactor", "x": 18, "y": 8, "w": 9, "h": 9,
  "label": "Reactor Chamber", "floor": "grating", "shape": "circle" }
```
| Field    | Req | Notes |
|----------|-----|-------|
| `id`     | rec | Unique; referenced by corridors and `{from,to}` doors. Auto-assigned if omitted. |
| `x,y`    | yes | Top-left cell of the room's **bounding box**. |
| `w,h`    | yes | Bounding-box width/height in cells. |
| `shape`  | no  | `rect` (default), `circle`/`ellipse`, `diamond`, `octagon`, or `poly`. |
| `label`  | no  | Human name (used in the art prompt). |
| `floor`  | no  | Visual floor type: `plating` (default), `grating`, `tile`, `organic`, `hazard`. |
| `corner` | no  | Octagon only: corner chamfer size in cells (default ≈ 30% of the short side). |
| `points` | poly | Polygon only: list of `[x, y]` vertices in grid units (e.g. `[[2,2],[10,2],[6,9]]`). |

**Shapes**
- `rect` — axis-aligned rectangle (the default).
- `circle` / `ellipse` — inscribed in the `w×h` box (use `w == h` for a circle).
  Rendered as a grid-aligned (stair-stepped) round room, which is what the VTT's
  cell-based walls and line-of-sight expect.
- `diamond` — rhombus inscribed in the box.
- `octagon` — rectangle with chamfered corners (tune with `corner`).
- `poly` — arbitrary polygon from `points`; cells whose center is inside are floor.

Tips: overlap rooms (any shapes) to compose L/T/cross/lobed spaces. Keep a
≥1-cell margin from the map edge so the bulkhead isn't clipped.

## `corridors[]`
Two forms:

**Auto L-route (preferred):**
```json
{ "from": "junction", "to": "reactor", "width": 3 }
```
Carves an L-shaped corridor between the two room centers. `width` in cells
(2 is a typical hallway, 3 a main thoroughfare).

**Explicit rectangle:**
```json
{ "x": 6, "y": 8, "w": 2, "h": 6 }
```
or `{ "rect": [6, 8, 2, 6] }`.

## `doors[]`
A door becomes a portal (UVTT) / door wall (Foundry). There are two ways to place
one. **Prefer the connection form** — it guarantees the door lines up with the
actual opening.

### Connection form (recommended)
Name the two rooms the door connects; the engine finds the opening between them
(directly, or via the corridor that joins them) and places **one door spanning
the full width** of that entrance. Doors always match the passage.
```json
{ "from": "reactor", "to": "junction", "type": "blast", "state": "closed" }
```
| Field     | Req | Notes |
|-----------|-----|-------|
| `from`    | yes | Room id the door sits on (the door is placed on this room's boundary). |
| `to`      | yes | Destination room id. May be directly adjacent or reachable through a corridor. |
| `type`    | no  | `door` (default), `blast`, `secret`, `airlock`. |
| `state`   | no  | `closed` (default), `open`, `locked`. |
| `all`     | no  | `true` → door **every** opening between the two regions (default: just the widest). |
| `perCell` | no  | `true` → one 1-cell door per cell instead of a single spanning door. |

### Explicit form (manual)
A door on one **side** of a specific cell. If the edge isn't exactly on a wall or
opening, the engine **snaps it to the nearest one** (within ~1 cell) and prints a
warning; if nothing is close it's placed as-is with a warning. Use this for
breaching a solid wall or other special cases.
```json
{ "x": 20, "y": 10, "side": "w", "type": "blast", "state": "closed" }
```
| Field   | Req | Notes |
|---------|-----|-------|
| `x,y`   | yes | The cell the door is attached to. |
| `side`  | yes | `n` (top), `s` (bottom), `e` (right), `w` (left). |
| `type`  | no  | `door` (default), `blast`, `secret`, `airlock`. |
| `state` | no  | `closed` (default), `open`, `locked`. |

### `autoDoors` (top-level option)
Set top-level `"autoDoors": true` (or a type string like `"autoDoors": "blast"`)
to automatically place a door across **every room↔corridor opening**. Explicit
`doors[]` still apply on top. Great for quickly sealing a whole deck.

## `lights[]`
Dynamic lights (the VTT renders the actual illumination; the PNG only shows a
small fixture icon, keeping the map neutral for dynamic lighting).
```json
{ "x": 24, "y": 11, "range": 7, "color": "#ff7a1a",
  "intensity": 1.0, "animation": "torch", "shadows": true }
```
| Field       | Req | Notes |
|-------------|-----|-------|
| `x,y`       | yes | Position in grid units (use `cx+0.5` for a cell center). |
| `range`     | no  | Radius in **cells** (default 4). Foundry `dim` = range×distance; `bright` = half. |
| `color`     | no  | Hex `#rrggbb` (default white). |
| `intensity` | no  | 0–1 (default 1). Maps to Foundry light alpha. |
| `animation` | no  | Foundry animation type: `torch`, `pulse`, `flame`, `energy`, `ghost`, etc. (empty = none). |
| `shadows`   | no  | UVTT shadow flag (default true). |

## `props[]`
Decorative top-down icons drawn on the floor (not collidable).
```json
{ "type": "reactor", "x": 23, "y": 10 }
```
Types: `console`, `terminal`, `reactor`, `crate`, `bed`/`pod`, plus a generic
marker for anything else. `x,y` is the cell. See `themes.md` for the catalog.

## Minimal valid spec
```json
{
  "name": "Test Bay",
  "size": { "w": 12, "h": 10 },
  "rooms": [ { "id": "bay", "x": 2, "y": 2, "w": 8, "h": 6 } ]
}
```
