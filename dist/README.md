# Distribution builds

SectorForge ships in two forms, for two different Claude surfaces.

## 1. Claude Code plugin (this repo root)
For **Claude Code** (CLI) and the **Cowork / Code** view in Claude Desktop.
Install via marketplace — see the top-level [README](../README.md):
```
/plugin marketplace add dakesec/SectorForge
/plugin install sector-forge@sectorforge
```

## 2. Agent Skill — `sector-forge.skill`
For **regular Claude Desktop / Claude.ai chat threads**, which can't load Claude
Code plugins but *can* load uploaded Agent Skills that run in the code-execution
sandbox.

- **`skill/sector-forge/`** — the skill source (SKILL.md + scripts + references +
  example). This is the same engine, with paths made relative to the skill folder
  and a Pillow-install step for the sandbox.
- **`sector-forge.skill`** — the packaged, uploadable file (a zip with a `.skill`
  extension; `sector-forge/` at its root).

### Install in Claude Desktop / Claude.ai
1. Open **Settings → Capabilities → Skills** (custom-skill upload requires a plan
   that supports it, e.g. Pro/Max/Team/Enterprise).
2. Choose **Upload skill** and select `sector-forge.skill`.
3. Start a new chat and ask for a map ("make me a sci-fi battlemap of …"). The
   skill runs `scripts/build_map.py` in the sandbox and returns the `.dd2vtt` /
   Foundry JSON / PNG for download.

### Rebuild the package after engine changes
```bash
# from the repo root, refresh the skill copy of the engine, then:
python dist/build_skill.py        # (or re-zip dist/skill/sector-forge into dist/sector-forge.skill)
```
