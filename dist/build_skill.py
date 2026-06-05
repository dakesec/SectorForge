#!/usr/bin/env python3
"""
build_skill.py — sync the engine into the Agent Skill folder and (re)package it.

Produces dist/sector-forge.skill (a zip with `.skill` extension) for upload to
Claude Desktop / Claude.ai (Settings -> Capabilities -> Skills).

The skill's SKILL.md is hand-maintained (it differs from the plugin's: relative
paths, sandbox pip-install step) and is NOT overwritten. Only the engine scripts,
references, and the example spec are synced from the repo.

Usage:
    python dist/build_skill.py
"""

import pathlib
import shutil
import zipfile

REPO = pathlib.Path(__file__).resolve().parent.parent
SKILL = REPO / "dist" / "skill" / "sector-forge"
OUT = REPO / "dist"
EXCLUDE_PARTS = {"__pycache__", "node_modules", "out"}


def sync():
    (SKILL / "scripts").mkdir(parents=True, exist_ok=True)
    (SKILL / "references").mkdir(parents=True, exist_ok=True)
    (SKILL / "examples").mkdir(parents=True, exist_ok=True)
    for name in ("build_map.py", "geometry.py", "render.py", "repack_image.py"):
        shutil.copyfile(REPO / "scripts" / name, SKILL / "scripts" / name)
    for ref in (REPO / "skills" / "sector-forge" / "references").glob("*.md"):
        shutil.copyfile(ref, SKILL / "references" / ref.name)
    shutil.copyfile(REPO / "examples" / "derelict-station.json",
                    SKILL / "examples" / "derelict-station.json")
    if not (SKILL / "SKILL.md").exists():
        raise SystemExit("ERROR: dist/skill/sector-forge/SKILL.md is missing "
                         "(it is hand-maintained — restore it before packaging).")


def package():
    target = OUT / "sector-forge.skill"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(SKILL.rglob("*")):
            if not f.is_file():
                continue
            rel = f.relative_to(SKILL.parent)
            if any(p in EXCLUDE_PARTS for p in rel.parts) or f.suffix == ".pyc":
                continue
            z.write(f, rel)
    print(f"packaged: {target} ({target.stat().st_size} bytes)")


if __name__ == "__main__":
    sync()
    package()
