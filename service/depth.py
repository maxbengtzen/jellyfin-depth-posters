"""Generate depth maps for every poster in /posters with Depth Anything V2.

Writes /output/<poster>_<model>.png (8-bit grayscale, white = near) and
/output/manifest.json, which the viewer uses to list posters and depth maps.
"""
import argparse
import json
import time
from pathlib import Path

from PIL import Image

from core import MODELS, depth_map, load_depth_model

EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}

parser = argparse.ArgumentParser()
parser.add_argument("--models", nargs="+", default=["small", "base"], choices=MODELS)
parser.add_argument("--force", action="store_true", help="regenerate existing depth maps")
args = parser.parse_args()

posters_dir, output_dir = Path("/posters"), Path("/output")
posters = sorted(p for p in posters_dir.iterdir() if p.suffix.lower() in EXTENSIONS)
manifest = {p.stem: {"poster": f"posters/{p.name}", "depths": {}} for p in posters}

for model in args.models:
    pipe = load_depth_model(model)
    for poster in posters:
        out = output_dir / f"{poster.stem}_{model}.png"
        if args.force or not out.exists():
            start = time.time()
            image = Image.open(poster).convert("RGB")
            Image.fromarray(depth_map(pipe, image), "L").save(out)
            print(f"{poster.name} [{model}] {time.time() - start:.1f}s", flush=True)
        manifest[poster.stem]["depths"][model] = f"output/{out.name}"

# Keep entries for models generated in earlier runs.
for stem, entry in manifest.items():
    for model in MODELS:
        f = output_dir / f"{stem}_{model}.png"
        if f.exists():
            entry["depths"][model] = f"output/{f.name}"

# Layers are written by layers.py; carry them over.
manifest_path = output_dir / "manifest.json"
old = {e["name"]: e for e in json.loads(manifest_path.read_text())} if manifest_path.exists() else {}
entries = []
for stem, entry in manifest.items():
    if "layers" in old.get(stem, {}):
        entry["layers"] = old[stem]["layers"]
    entries.append({"name": stem, **entry})
manifest_path.write_text(json.dumps(entries, indent=2))
