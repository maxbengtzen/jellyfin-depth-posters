# Configuration

The service is configured with environment variables, normally through `.env` (copy `.env.example`). Docker Compose passes them to the container.

| Variable | Default | Description |
|---|---|---|
| `JELLYFIN_API_KEY` | *(required)* | Jellyfin API key (*Dashboard → Advanced → API Keys*). Only read access is used. |
| `JELLYFIN_NETWORK` | `jellyfin_default` | Name of the Docker network Jellyfin runs on. The service joins it. |
| `JELLYFIN_URL` | `http://jellyfin:8096` | Jellyfin's address on that network. |
| `DEPTH_MODEL` | `small` | `small`, `base` or `large`. `base` and `large` are CC-BY-NC-4.0 (non-commercial). |
| `ENABLE_LAYERS` | `false` | Also generate four inpainted layers per poster. About five times slower. |
| `MAX_SIZE` | `720` | Longest side, in pixels, of the poster the service works on and of the generated files. |
| `SCAN_INTERVAL_MIN` | `30` | Minutes between library scans. |
| `ITEM_TYPES` | `Movie,Series` | Comma-separated Jellyfin item types to process. |
| `PUID` / `PGID` | `1000` | User and group the container runs as; they must be able to write `./data` and `./.cache`. |

Changing `DEPTH_MODEL` does not regenerate existing items. Delete `./data` (or the item folders) to start over. Turning `ENABLE_LAYERS` on *does* regenerate items that have no layers yet; turning it off keeps the layers you already have.

## Volumes

| Path | Purpose |
|---|---|
| `./data` → `/data` | Generated depth maps and layers, one folder per item and poster tag |
| `./.cache` → `/cache` | Downloaded model weights (Hugging Face cache and the LaMa weights) |

## Networking

The service does not publish a port. It joins the Docker network Jellyfin is on (`JELLYFIN_NETWORK`), where Jellyfin can reach it as `http://jellyfin-depth-posters:8000` (the plugin's default service URL) and it can reach Jellyfin by container name.

If Jellyfin is not in Docker, or you want to run the service elsewhere, put `JELLYFIN_URL` to a reachable address, publish a port (below), and set the plugin's *Service URL* accordingly.

### Publishing a port (optional)

Create `compose.override.yaml` (git-ignored, merged automatically):

```yaml
services:
  jellyfin-depth-posters:
    ports:
      - "127.0.0.1:8000:8000"
```

Then `curl http://localhost:8000/api/status` shows progress.

> The API has no authentication. Bind it to localhost or a trusted network; never expose it to the internet.

## HTTP API

Used by the plugin; documented for debugging.

| Endpoint | Description |
|---|---|
| `GET /depth/{itemId}/manifest.json` | Manifest for the item's current poster, or 404 if not generated yet |
| `GET /depth/{itemId}/{tag}/{file}` | `depth.png`, `layer_N.webp`; cacheable forever, the poster tag is in the path |
| `GET /api/status` | `{total, done, queued, failed, current, scanning, last_scan, model, layers}` |
| `POST /api/scan` | Start a library scan now |

## Image tags

`compose.yaml` pulls `ghcr.io/maxbengtzen/jellyfin-depth-posters:latest`. Each release is also tagged `X.Y.Z`, `X.Y` and `X`; pin one of those if you prefer to update on your own schedule. Images are built for `linux/amd64` and `linux/arm64`, with an SBOM and build provenance attached.

## Building from source

To build the image locally instead, add to `compose.override.yaml`:

```yaml
services:
  jellyfin-depth-posters:
    build: ./service
    image: jellyfin-depth-posters:local
```
