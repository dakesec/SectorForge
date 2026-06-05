# Auto-Generated Hybrid Art via Local ComfyUI

Run the whole hybrid path in one command: SectorForge renders the layout, ComfyUI
paints it from the tuned prompt, and the painted art is repacked with the derived
VTT walls/lights. Requires a **local ComfyUI** running on this machine.

`scripts/comfyui_submit.py` talks to ComfyUI over its HTTP API (stdlib only). It
patches *your* exported workflow by node title, so it works with any model
(Z-Image, SDXL, Flux) and any technique (txt2img, img2img, ControlNet).

> The script must run where it can reach the ComfyUI server (i.e. locally via the
> Claude Code plugin / CLI). It will **not** work from the cloud sandbox of an
> uploaded Agent Skill, which can't reach your localhost.

---

## Part 1 — Install ComfyUI (Windows, NVIDIA RTX 3090)

**Option A — Portable (best for API/automation):**
1. Download `ComfyUI_windows_portable_nvidia.7z` from the releases page:
   https://github.com/comfyanonymous/ComfyUI/releases
2. Extract it (e.g. to `C:\ComfyUI_windows_portable`).
3. Double-click **`run_nvidia_gpu.bat`**. When it prints
   `To see the GUI go to: http://127.0.0.1:8188`, the API is live on port **8188**.

**Option B — ComfyUI Desktop (one-click app):** https://www.comfy.org/download
Note the API port it reports (often `http://127.0.0.1:8000`) and pass it via
`--server` below.

Your RTX 3090 (24 GB) runs Z-Image Turbo comfortably.

## Part 2 — Install the Z-Image Turbo model

Follow the official guide for exact, current download links:
https://docs.comfy.org/tutorials/image/z-image/z-image-turbo

You need three files, placed under your ComfyUI `models/` folder:

| File | Folder |
|------|--------|
| `qwen_3_4b.safetensors` (text encoder) | `ComfyUI/models/text_encoders/` |
| `z_image_turbo_bf16.safetensors` (diffusion model) | `ComfyUI/models/diffusion_models/` |
| `ae.safetensors` (VAE) | `ComfyUI/models/vae/` |

Restart ComfyUI after adding models.

## Part 3 — Build & export the workflow

1. In ComfyUI: **Workflow → Browse Templates → Z-Image** (or drag the template
   from the docs page). Click **Run** once to confirm it generates an image.
2. **Title two nodes** (right-click a node → *Title*):
   - the **positive** prompt node (a `CLIPTextEncode`) → `SECTORFORGE_PROMPT`
   - *(optional, for alignment)* a `LoadImage` node feeding an img2img/ControlNet
     branch → `SECTORFORGE_INIT`
3. Set the output resolution to match your map's aspect (e.g. 1280×1024 for a
   46×36 grid; the repacker rescales pixels-per-grid automatically).
4. **Save (API Format)** → e.g. `zimage_api.json`. (This is different from a
   normal save — it must be the API format.)

### Layout alignment (recommended)
Plain text-to-image won't place rooms where your walls are. To make the painting
match the derived VTT walls, use the procedural PNG as structure:
- **img2img:** `Load Image (SECTORFORGE_INIT) → VAE Encode → KSampler.latent_image`,
  denoise ~0.6–0.75.
- **or ControlNet** (depth/canny) conditioned on the same image.
The script auto-uploads `<name>.png` into the `SECTORFORGE_INIT` node.

## Part 4 — Run it (one command)

```bash
python scripts/comfyui_submit.py examples/eldritch-warren.json \
    --workflow zimage_api.json --out out
```
Options: `--server http://127.0.0.1:8188` (change port for Desktop),
`--timeout 300`, `--no-img2img` (pure text-to-image, skip the init image).

It will: render the layout + prompt → upload the init image → queue on ComfyUI →
wait → download the painting → repack. Final files:
- `out/<name>.art.png` — the painted background
- `out/<name>.dd2vtt` / `out/<name>.fvtt.json` — painted bg + all walls/lights

Import the `.dd2vtt` into Foundry/Roll20 as usual.

## Troubleshooting
- **`cannot reach ComfyUI`** — ComfyUI isn't running, or the port is wrong (use
  `--server`). Confirm the GUI loads in a browser first.
- **`no positive prompt node found`** — title a `CLIPTextEncode` node
  `SECTORFORGE_PROMPT` and re-export in **API Format**.
- **`produced no images`** — your workflow needs a `SaveImage` node.
- **Art ignores the layout** — you're running txt2img; add the `SECTORFORGE_INIT`
  img2img/ControlNet branch (Part 3) so walls line up.
- **Out of memory** — Z-Image Turbo is light; lower the resolution or close other
  GPU apps. The 3090 should handle 1280×1024 easily.
