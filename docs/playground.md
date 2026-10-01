# Playground

Try the effect on your own images, without Jellyfin, and compare models.

```bash
mkdir -p posters output                    # put .png/.jpg/.webp images in posters/
docker compose --profile tools run --rm depth-cli                 # depth maps (small + base)
docker compose --profile tools run --rm depth-cli --models large  # another model
docker compose --profile tools run --rm layers-cli --depth-model base  # inpainted layers
docker compose --profile tools up -d playground
```

Open http://localhost:8765. Pick a poster and model, switch between *Depth map* and *Layers* mode, and adjust strength, focus plane, smoothing and tilt. The *Automatic loop* option makes the poster move on its own.

Results are written to `./output` (git-ignored). Both CLIs skip images that are already done; pass `--force` to redo them.

`layers-cli` options: `--layers N`, `--size PX`, `--grow PX` (how much the inpaint mask is grown to hide colour bleed), `--feather` (alpha softness).

The playground is a development aid for tuning the rendering; the service and plugin do not use it.
