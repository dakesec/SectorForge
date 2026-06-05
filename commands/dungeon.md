---
name: dungeon
description: Generate a sci-fi VTT battlemap (Foundry/UVTT) from a description.
argument-hint: <describe the location, e.g. "derelict mining station, reactor + 3 crew quarters + med-bay, emergency lighting">
---

Use the **sector-forge** skill to create a VTT-ready sci-fi battlemap from
the user's direction below.

User direction: $ARGUMENTS

Steps:
1. Load the `sector-forge` skill (read its SKILL.md and the
   `map-spec-schema.md` / `themes.md` references).
2. If the direction is thin, infer sensible defaults (theme, ~30×22 grid, 5 ft
   cells) rather than over-asking — surface assumptions in one line.
3. Design the deck layout and write a map-spec JSON to `out/<name>.json`.
4. Run:
   `python ${CLAUDE_PLUGIN_ROOT}/scripts/build_map.py out/<name>.json --out out`
   (install Pillow with `pip install Pillow` if needed).
5. Show the generated PNG, then report the output files:
   - `out/<name>.dd2vtt` — Universal VTT (drag into Foundry v11+, or Roll20 via
     UniversalVTTImporter)
   - `out/<name>.fvtt.json` — native Foundry scene (Import Data into a new scene)
6. Offer to iterate (edit the spec + re-run) or to do the **hybrid** AI-art pass
   (z-image prompt is in `out/<name>.prompt.txt`; repack with
   `scripts/repack_image.py`).
