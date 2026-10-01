# How it works

## Pipeline

For each movie and series in Jellyfin the service:

1. Reads the item's `ImageTags.Primary` and checks whether `data/<itemId>/<tag>/manifest.json` exists. If it does (and has layers when `ENABLE_LAYERS` is on), the item is done.
2. Downloads the poster from `/Items/{id}/Images/Primary`, scaled to `MAX_SIZE`.
3. Runs [Depth Anything V2](https://github.com/DepthAnything/Depth-Anything-V2) on the CPU and stores an 8-bit grey depth map (`depth.png`, white = near).
4. With `ENABLE_LAYERS`: splits the depth map into four bands with multi-Otsu thresholding on its histogram. Layer *k* keeps every pixel at least as near as its band; everything nearer is removed and filled in with [LaMa](https://github.com/advimman/lama) inpainting. Stacked back to front, the layers reproduce the poster, but each one can move on its own without exposing holes. Layers are stored as RGBA WebP.
5. Writes `manifest.json` last, so a folder with a manifest is always complete.

Items are processed one at a time. Jobs that fail because Jellyfin is unreachable or returns a 5xx error are retried on the next scan; other failures are skipped until the service restarts.

## File layout

```
data/
  <itemId>/
    <posterTag>/
      manifest.json
      depth.png
      layer_0.webp … layer_3.webp   (with ENABLE_LAYERS)
```

The poster tag changes when the poster changes, so a new poster gets a new folder and the old one is removed. Folders of items that no longer exist in Jellyfin are removed on scan (unless Jellyfin returns no items at all, which is treated as a glitch).

`manifest.json`:

```json
{
  "itemId": "…", "tag": "…", "model": "small", "width": 480, "height": 720,
  "depth": "depth.png",
  "layers": { "files": ["layer_0.webp", "…"], "depths": [0.14, 0.35, 0.55, 0.84] }
}
```

`layers` is absent when layers are not generated.

## Rendering

The front-end script draws into a WebGL canvas laid over the hovered card.

- **Depth map mode:** a short ray march through the depth map shifts each pixel by its depth relative to a focus plane, following the pointer.
- **Layer mode:** each layer is shifted by its own mean depth and the layers are composited back to front.

Both add a slight tilt and a highlight that follows the pointer, and ease in and out when you enter and leave a card.

## Performance

Measured on an 8-core CPU without GPU.

| Step | Time per poster |
|---|---|
| Depth Anything V2 Small | 1.2–1.4 s |
| Depth Anything V2 Base | 2.9–4.0 s |
| Depth Anything V2 Large | 9–10 s |
| Whole job, Base, 720 px, no layers (incl. download) | ~3.3 s |
| Whole job, Base, 720 px, with layers | 14–19 s |

A library of 700 posters takes about 40 minutes with Base and no layers, or about three hours with layers. This is a one-off cost; afterwards only new or changed posters are processed.
