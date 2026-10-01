"""Split posters into depth layers and inpaint what each layer hides behind nearer ones.

Writes /output/layers/<poster>_<model>/layer_<k>.webp and records them in
/output/manifest.json (run depth.py first).
"""
import argparse
import json
import time
from pathlib import Path

import numpy as np
from PIL import Image

from core import build_layers, load_lama, save_layer

parser = argparse.ArgumentParser()
parser.add_argument("--depth-model", default="base", choices=["small", "base", "large"])
parser.add_argument("--layers", type=int, default=4)
parser.add_argument("--size", type=int, default=1280, help="max side of the layer images")
parser.add_argument("--grow", type=int, default=8, help="px to grow the inpaint mask (hides colour bleed)")
parser.add_argument("--feather", type=float, default=6, help="alpha softness, in depth units (0-255)")
parser.add_argument("--force", action="store_true")
args = parser.parse_args()

posters_dir, output_dir = Path("/posters"), Path("/output")
manifest_path = output_dir / "manifest.json"
manifest = json.loads(manifest_path.read_text())
lama = None

for entry in manifest:
    depth_file = entry["depths"].get(args.depth_model)
    if not depth_file:
        continue
    out_dir = output_dir / "layers" / f"{entry['name']}_{args.depth_model}"
    if out_dir.exists() and not args.force:
        continue
    lama = lama or load_lama()
    start = time.time()

    image = Image.open(posters_dir / Path(entry["poster"]).name).convert("RGB")
    scale = min(1, args.size / max(image.size))
    if scale < 1:
        image = image.resize((round(image.width * scale), round(image.height * scale)), Image.LANCZOS)
    depth = np.asarray(Image.open(Path("/") / depth_file).convert("L").resize(image.size, Image.BICUBIC))

    layers, depths = build_layers(lama, np.asarray(image), depth, args.layers, args.grow, args.feather)
    out_dir.mkdir(parents=True, exist_ok=True)
    files = []
    for k, layer in enumerate(layers):
        save_layer(layer, out_dir / f"layer_{k}.webp")
        files.append(f"output/layers/{out_dir.name}/layer_{k}.webp")
    entry.setdefault("layers", {})[args.depth_model] = {"files": files, "depths": depths}
    manifest_path.write_text(json.dumps(manifest, indent=2))
    print(f"{entry['name']} [{args.depth_model}] {args.layers} layers, {time.time() - start:.1f}s", flush=True)
