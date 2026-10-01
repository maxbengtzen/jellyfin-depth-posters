"""Shared depth/layer logic used by the CLI scripts and the service."""
import urllib.request
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image
from scipy import ndimage
from skimage.filters import threshold_multiotsu
from transformers import pipeline

MODELS = {
    "small": "depth-anything/Depth-Anything-V2-Small-hf",
    "base": "depth-anything/Depth-Anything-V2-Base-hf",
    "large": "depth-anything/Depth-Anything-V2-Large-hf",
}
LAMA_URL = "https://github.com/enesmsahin/simple-lama-inpainting/releases/download/v0.1.0/big-lama.pt"
LAMA_PATH = Path("/cache/big-lama.pt")


def load_depth_model(model):
    return pipeline("depth-estimation", model=MODELS[model], device="cpu")


def depth_map(pipe, image):
    """Return an 8-bit depth map (white = near) at the size of `image`."""
    depth = pipe(image)["predicted_depth"]
    depth = F.interpolate(
        depth.reshape(1, 1, *depth.shape[-2:]).float(), size=image.size[::-1], mode="bicubic", align_corners=False
    )[0, 0].numpy()
    depth = (depth - depth.min()) / (depth.max() - depth.min())
    return (depth * 255).astype(np.uint8)


def load_lama():
    if not LAMA_PATH.exists():
        tmp = LAMA_PATH.with_suffix(".part")
        urllib.request.urlretrieve(LAMA_URL, tmp)
        tmp.rename(LAMA_PATH)
    return torch.jit.load(LAMA_PATH, map_location="cpu").eval()


def inpaint(model, rgb, mask):
    """rgb: HxWx3 uint8, mask: HxW bool (True = fill). LaMa wants sides divisible by 8."""
    h, w = mask.shape
    pad = (0, -w % 8, 0, -h % 8)
    img = F.pad(torch.from_numpy(rgb).permute(2, 0, 1)[None].float() / 255, pad, mode="reflect")
    m = F.pad(torch.from_numpy(mask)[None, None].float(), pad, mode="reflect")
    with torch.no_grad():
        out = model(img, m)
    out = out[0].permute(1, 2, 0)[:h, :w].clamp(0, 1).numpy()
    return (out * 255).astype(np.uint8)


def smoothstep(x):
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


def build_layers(lama, rgb, depth, n=4, grow=8, feather=6):
    """Cut `rgb` into `n` RGBA layers (far to near) using the depth map.

    Layer k keeps every pixel at least as near as its band; nearer content is
    inpainted away. Returns (list of HxWx4 uint8 arrays, list of layer depths 0..1).
    """
    depth = depth.astype(np.float32)
    edges = [0, *threshold_multiotsu(depth.astype(np.uint8), classes=n), 256]
    layers, depths = [], []
    for k in range(n):
        lo, hi = edges[k], edges[k + 1]
        alpha = np.ones(depth.shape, np.float32) if k == 0 else smoothstep((depth - (lo - feather)) / (2 * feather))
        if k < n - 1:
            near_grown = ndimage.distance_transform_edt(~(depth >= hi)) <= grow
            layer_rgb = inpaint(lama, rgb, near_grown)
        else:
            layer_rgb = rgb
        band = (depth >= lo) & (depth < hi)
        depths.append(round(float(depth[band].mean()) / 255, 4) if band.any() else round(lo / 255, 4))
        layers.append(np.dstack([layer_rgb, (alpha * 255).astype(np.uint8)]))
    return layers, depths


def save_layer(layer, path):
    Image.fromarray(layer, "RGBA").save(path, quality=92, method=4)
