# Themes, Floors, Props & Lighting

## Themes (`theme` field)

Each theme sets the palette for void, floors, panel seams, walls, and accents.

| Theme                 | Feel | Palette summary |
|-----------------------|------|-----------------|
| `clean_ship`          | Functional starship interior | Cool blue-grey panels, bright steel bulkheads, cyan accents. |
| `derelict_industrial` | Abandoned mining/cargo hulk | Dark rusted metal, grime, amber warning accents. |
| `station_lab`         | Sterile research station | Light grey-blue, white bulkheads, teal accents. |
| `military_bunker`     | Hardened military deck | Olive-grey, gun-metal walls, chartreuse accents. |
| `alien_organic`       | Bio-engineered / hive | Purple-teal biotech, organic curves, green glow. |
| `eldritch_void`       | Cosmic-horror carved stone | Dark slate-violet stone, teal + violet bioluminescence. Organic texturing is **on by default** for this theme. |

Choose the theme that matches the mood; you can still recolor lights per-fixture.

## Organic texturing (`texture`)

Set top-level `"texture": true` (on by default for `eldritch_void`) to render
mottled stone instead of flat panels, plus cracks, glowing growth clustered along
walls, scattered spores, and edge vignetting — for ancient/derelict/alien spaces.
For the fully painted, hand-illustrated look (carved reliefs, vines, volumetric
light) use the **hybrid path**: the procedural map carries the layout + walls, and
an image generator paints the background from `<name>.prompt.txt`, then
`repack_image.py` recombines it with the VTT data.

## Floor types (`floor` field on a room)

| Type      | Look | Good for |
|-----------|------|----------|
| `plating` | Smooth panel plates (default) | Corridors, general rooms. |
| `grating` | Horizontal grate lines | Engineering, reactor, catwalks. |
| `tile`    | Cross-scored tiles | Med-bay, labs, bridge, clean rooms. |
| `organic` | Soft curved striations | Alien/biotech spaces. |
| `hazard`  | Diagonal hazard stripes | Airlocks, loading bays, danger zones. |

## Prop catalog (`props[].type`)

| Type       | Drawn as | Use for |
|------------|----------|---------|
| `console`  | Lit panel with screen | Control stations, ops. |
| `terminal` | Upright screen + base | Wall computers, data ports. |
| `reactor`  | Concentric glowing rings | Reactor cores, power plants, warp coils. |
| `crate`    | X-braced box | Cargo, supplies, cover. |
| `bed`/`pod`| Rounded capsule | Bunks, cryo-pods, med-beds. |
| (other)    | Generic round marker | Anything unlisted. |

Props are visual only — they don't block movement or sight. To make something
block line-of-sight, model it as a tiny room (so walls derive around it) or place
a door/wall via a 1-cell room gap.

## Lighting recipes

Lights drive the VTT's dynamic lighting; keep them purposeful.

| Mood | Recipe |
|------|--------|
| Sterile lab | `#dff2ff`, range 5–6, intensity 0.8, no animation. |
| Emergency / alert | `#ff2a2a`, range 5, intensity 1.0, `animation: "pulse"`. |
| Reactor glow | `#ff7a1a` or `#33ff88`, range 7–8, `animation: "torch"` or `"energy"`. |
| Flickering derelict | `#ffcf8f`, range 3–4, intensity 0.6, `animation: "flame"`. |
| Bioluminescent | `#7affc8`, range 4, intensity 0.7, `animation: "pulse"`. |
| Holographic / console wash | `#5ad0ff`, range 2–3, intensity 0.5. |

Place a light roughly every 4–6 cells along lit corridors, plus accents on
reactors, consoles, and hazards. Leave some rooms dark for tension — dynamic
lighting + fog makes unlit rooms genuinely unknown to players.

## Composition tips

- **Readability first.** A VTT map is a tactical tool: clear rooms, obvious
  doors, distinct corridors beat artistic clutter.
- **Vary room sizes.** A big set-piece room (reactor, hangar, bridge) plus
  smaller satellite rooms reads better than uniform boxes.
- **Chokepoints.** Doors and 1–2 wide corridors create tactical decisions.
- **One landmark per map.** A reactor, a downed shuttle, a breached hull — give
  the deck a focal point.
- **Grid budget.** 30×22 cells ≈ a substantial single-deck encounter. Go bigger
  (40×30) for a whole deck, smaller (16×12) for a single-room skirmish.
