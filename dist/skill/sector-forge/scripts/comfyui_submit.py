#!/usr/bin/env python3
"""
comfyui_submit.py — one-command hybrid: render the layout, paint it in ComfyUI,
and repack the painted art with the derived VTT walls/lights.

Pipeline:
  1. build_map.py  -> procedural PNG + tuned art prompt (+ base VTT files)
  2. patch your ComfyUI API workflow with the prompt (and, for img2img/ControlNet,
     the procedural PNG as the init/structure image)
  3. queue it on the local ComfyUI server, wait, download the painted result
  4. repack_image.py -> final .dd2vtt / .fvtt.json with the painted background and
     ALL the original walls/doors/lights intact

The workflow is model-agnostic: you export an *API-format* workflow from ComfyUI
(Save -> API Format) and title two nodes so this script knows what to patch:
  * the positive prompt node (a CLIPTextEncode)  -> title it  SECTORFORGE_PROMPT
  * (optional, for alignment) a LoadImage node    -> title it  SECTORFORGE_INIT
Right-click a node -> "Title" to set these. If no SECTORFORGE_PROMPT title is
found, the script falls back to the first non-negative CLIPTextEncode.

Usage:
  python scripts/comfyui_submit.py SPEC.json --workflow workflow_api.json [--out out]
      [--server http://127.0.0.1:8188] [--timeout 300] [--no-img2img]

Stdlib only (urllib) — no extra dependencies. See references/comfyui-hybrid.md.
"""

import argparse
import json
import os
import sys
import time
import uuid
import urllib.error
import urllib.parse
import urllib.request

import build_map
import geometry

PROMPT_TITLE = "SECTORFORGE_PROMPT"
INIT_TITLE = "SECTORFORGE_INIT"


# --- ComfyUI HTTP API (stdlib) ----------------------------------------------

def _get_json(url):
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.load(r)


def upload_image(server, path):
    """POST an image to ComfyUI's input folder; return the reference name."""
    boundary = "----sectorforge" + uuid.uuid4().hex
    fname = os.path.basename(path)
    with open(path, "rb") as f:
        data = f.read()
    parts = []

    def field(name, value):
        parts.append(("--" + boundary).encode())
        parts.append(('Content-Disposition: form-data; name="%s"' % name).encode())
        parts.append(b"")
        parts.append(value if isinstance(value, bytes) else value.encode())

    parts.append(("--" + boundary).encode())
    parts.append(('Content-Disposition: form-data; name="image"; filename="%s"' % fname).encode())
    parts.append(b"Content-Type: image/png")
    parts.append(b"")
    parts.append(data)
    field("type", "input")
    field("overwrite", "true")
    parts.append(("--" + boundary + "--").encode())
    parts.append(b"")
    body = b"\r\n".join(parts)

    req = urllib.request.Request(
        server + "/upload/image", data=body,
        headers={"Content-Type": "multipart/form-data; boundary=" + boundary})
    with urllib.request.urlopen(req, timeout=60) as r:
        info = json.load(r)
    sub = info.get("subfolder", "")
    return (sub + "/" + info["name"]) if sub else info["name"]


def queue_prompt(server, workflow, client_id):
    body = json.dumps({"prompt": workflow, "client_id": client_id}).encode()
    req = urllib.request.Request(server + "/prompt", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)["prompt_id"]


def wait_for_output(server, prompt_id, timeout):
    start = time.time()
    while time.time() - start < timeout:
        hist = _get_json(server + "/history/" + prompt_id)
        if prompt_id in hist and hist[prompt_id].get("outputs"):
            return hist[prompt_id]["outputs"]
        time.sleep(1.5)
    raise TimeoutError(f"ComfyUI did not finish within {timeout}s")


def fetch_first_image(server, outputs):
    for node_out in outputs.values():
        for img in node_out.get("images", []):
            q = urllib.parse.urlencode({
                "filename": img["filename"],
                "subfolder": img.get("subfolder", ""),
                "type": img.get("type", "output"),
            })
            with urllib.request.urlopen(server + "/view?" + q, timeout=60) as r:
                return r.read()
    raise RuntimeError("ComfyUI run produced no images (check the workflow's SaveImage node)")


# --- workflow patching -------------------------------------------------------

def patch_workflow(wf, prompt_text, init_name):
    """Inject the prompt (and optional init image) into an API-format workflow."""
    patched_prompt = False
    patched_init = False
    for node in wf.values():
        title = node.get("_meta", {}).get("title", "")
        inputs = node.get("inputs", {})
        if title == PROMPT_TITLE and "text" in inputs:
            inputs["text"] = prompt_text
            patched_prompt = True
        if init_name and title == INIT_TITLE and node.get("class_type") == "LoadImage":
            inputs["image"] = init_name
            patched_init = True

    if not patched_prompt:  # fallback: first non-negative CLIPTextEncode
        for node in wf.values():
            if node.get("class_type") == "CLIPTextEncode" and "text" in node.get("inputs", {}):
                if "negative" not in node.get("_meta", {}).get("title", "").lower():
                    node["inputs"]["text"] = prompt_text
                    patched_prompt = True
                    break

    return patched_prompt, patched_init


# --- main --------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(description="Render + paint (ComfyUI) + repack in one step.")
    ap.add_argument("spec")
    ap.add_argument("--workflow", required=True, help="ComfyUI API-format workflow JSON")
    ap.add_argument("--out", default="out")
    ap.add_argument("--server", default="http://127.0.0.1:8188")
    ap.add_argument("--timeout", type=float, default=300.0)
    ap.add_argument("--no-img2img", action="store_true",
                    help="do not upload the procedural PNG as the init image")
    args = ap.parse_args(argv)
    server = args.server.rstrip("/")

    with open(args.spec, "r", encoding="utf-8-sig") as f:
        spec = json.load(f)
    spec.setdefault("grid", {}).setdefault("cell_px", 140)
    spec["grid"].setdefault("distance", 5)
    spec.setdefault("size", {"w": 20, "h": 20})
    name = build_map._slug(spec.get("name", "map"))

    with open(args.workflow, "r", encoding="utf-8-sig") as f:
        workflow = json.load(f)

    # 1. procedural render + tuned prompt (also writes the base VTT files)
    print("[1/4] rendering layout + prompt ...")
    if build_map.main([args.spec, "--out", args.out]) != 0:
        return 1
    png_path = os.path.join(args.out, f"{name}.png")
    with open(os.path.join(args.out, f"{name}.prompt.txt"), "r", encoding="utf-8") as f:
        prompt_text = f.read().strip()

    # 2. patch workflow
    init_name = None
    if not args.no_img2img and os.path.exists(png_path):
        try:
            init_name = upload_image(server, png_path)
            print(f"[2/4] uploaded init image -> {init_name}")
        except urllib.error.URLError as e:
            print(f"ERROR: cannot reach ComfyUI at {server} ({e}). Is it running?",
                  file=sys.stderr)
            return 2
    pp, pi = patch_workflow(workflow, prompt_text, init_name)
    if not pp:
        print(f"ERROR: no positive prompt node found. Title one node "
              f"'{PROMPT_TITLE}' in ComfyUI and re-export (API Format).", file=sys.stderr)
        return 3
    if init_name and not pi:
        print(f"NOTE: '{INIT_TITLE}' LoadImage node not found — running text-to-image "
              f"(layout may not align). Title a LoadImage node '{INIT_TITLE}' for img2img.",
              file=sys.stderr)

    # 3. queue + wait + download
    print("[3/4] queuing on ComfyUI ...")
    try:
        cid = uuid.uuid4().hex
        pid = queue_prompt(server, workflow, cid)
        outputs = wait_for_output(server, pid, args.timeout)
        art_bytes = fetch_first_image(server, outputs)
    except urllib.error.URLError as e:
        print(f"ERROR: ComfyUI request failed ({e}). Is the server up at {server}?",
              file=sys.stderr)
        return 2
    art_path = os.path.join(args.out, f"{name}.art.png")
    with open(art_path, "wb") as f:
        f.write(art_bytes)
    print(f"      painted art -> {art_path}")

    # 4. repack art with the derived VTT data
    print("[4/4] repacking VTT files with painted background ...")
    rc = __import__("repack_image").main([args.spec, art_path, "--out", args.out])
    if rc == 0:
        print("done. Import the .dd2vtt into your VTT.")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
