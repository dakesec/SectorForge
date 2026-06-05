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
Rectangular floor areas. The union of all rooms + corridors is the walkable
floor; walls are auto-derived around its outer boundary.
```json
{ "id": "reactor", "x": 20, "y": 7, "w": 8, "h": 8,
  "label": "Reactor Core", "floor": "grating" }
```
| Field   | Req | Notes |
|---------|-----|-------|
| `id`    | rec | Unique; referenced by corridors. Auto-assigned if omitted. |
| `x,y`   | yes | Top-left cell of the room. |
| `w,h`   | yes | Width/height in cells. |
| `label` | no  | Human name (used in the art prompt). |
| `floor` | no  | Visual floor type: `plating` (default), `grating`, `tile`, `organic`, `hazard`. |

Tips: overlap rooms to make L/T/cross shapes. Keep a ≥1-cell margin from the map
edge so the bulkhead isn't clipped.

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
A door sits on one **side** of a cell and carves a portal out of the wall there.
Put the door on the cell **just inside a room**, on the side facing the corridor.
```json
{ "x": 20, "y": 10, "side": "w", "type": "blast", "state": "closed" }
```
| Field   | Req | Notes |
|---------|-----|-------|
| `x,y`   | yes | The cell the door is attached to. |
| `side`  | yes | `n` (top), `s` (bottom), `e` (right), `w` (left). |
| `type`  | no  | `door` (default), `blast`, `secret`, `airlock`. Affects color + Foundry door type (`secret` → secret door). |
| `state` | no  | `closed` (default), `open`, `locked`. |

A door is one cell wide. For a 2-cell doorway, add two adjacent doors.

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
