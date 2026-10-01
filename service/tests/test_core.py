import numpy as np
import torch

import core


def test_build_layers_on_synthetic_image():
    h, w = 64, 48
    rgb = np.random.default_rng(0).integers(0, 255, (h, w, 3), dtype=np.uint8)
    # three clear depth bands, near at the bottom
    depth = np.repeat(np.linspace(0, 255, h)[:, None], w, axis=1).astype(np.uint8)

    calls = []

    def fake_lama(img, mask):
        calls.append(mask.sum().item())
        return img  # identity "inpainting"

    layers, depths = core.build_layers(fake_lama, rgb, depth, n=3, grow=2, feather=4)

    assert len(layers) == len(depths) == 3
    assert all(layer.shape == (h, w, 4) and layer.dtype == np.uint8 for layer in layers)
    assert (layers[0][..., 3] == 255).all()              # the back layer is fully opaque
    assert depths == sorted(depths)                      # far to near
    assert len(calls) == 2                               # every layer but the nearest is inpainted
    assert layers[-1][..., :3].tolist() == rgb.tolist()  # nearest layer keeps the original pixels


def test_inpaint_pads_to_multiple_of_eight():
    seen = {}

    def fake_lama(img, mask):
        seen["shape"] = tuple(img.shape)
        return img

    out = core.inpaint(fake_lama, np.zeros((10, 13, 3), np.uint8), np.zeros((10, 13), bool))
    assert seen["shape"] == (1, 3, 16, 16) and out.shape == (10, 13, 3)
