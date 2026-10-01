# Jellyfin plugin

The plugin does three things:

1. **Injects** `<script src="/DepthPosters/script.js">` into the web UI's `index.html`, using the [File Transformation](https://github.com/IAmParadox27/jellyfin-plugin-file-transformation) plugin. No Jellyfin files are modified.
2. **Serves** the script and the configuration (`/DepthPosters/script.js`, `/DepthPosters/config.json`).
3. **Proxies** `/DepthPosters/{itemId}/…` to the depth service, so the browser only talks to Jellyfin (same origin, no CORS or mixed-content problems, and the service never has to be published).

The endpoints are anonymous, like Jellyfin's own image endpoints. They expose only poster-derived images.

## Requirements

- Jellyfin **12.1** (built against `Jellyfin.Controller` 12.1.0, .NET 10)
- The **File Transformation** plugin, version 3.0 or newer

## Install from the plugin repository

*Dashboard → Plugins → Repositories → Add*:

```
https://raw.githubusercontent.com/maxbengtzen/jellyfin-depth-posters/main/manifest.json
```

Install **Depth Posters** from the catalogue and restart Jellyfin.

## Install manually

Download `jellyfin-depth-posters_<version>.zip` from the [releases page](https://github.com/maxbengtzen/jellyfin-depth-posters/releases), unzip it into a new folder named `Depth Posters_<version>` inside Jellyfin's `plugins` directory (`/config/plugins` in the official image), and restart Jellyfin.

## Settings

*Dashboard → Plugins → Depth Posters*:

| Setting | Default | Description |
|---|---|---|
| Service URL | `http://jellyfin-depth-posters:8000` | Where the Jellyfin server reaches the depth service |
| Use inpainted layers | on | Use layers when the service generated them, otherwise the depth map |
| Parallax strength | 0.04 | How far the layers move; 0.08 is strong |
| Tilt | 6° | Card tilt |
| Focus depth | 0.45 | The depth (0 far, 1 near) that stays still |

Reload the web UI (Ctrl+Shift+R) after saving.

## Building

```bash
cd plugin
dotnet publish -c Release -o dist     # .NET 10 SDK
cp meta.json dist/
```

Or with Docker: `docker run --rm -v "$PWD:/src" -w /src mcr.microsoft.com/dotnet/sdk:10.0 dotnet publish -c Release -o dist`.

### Iterating on the script

Place a file called `script.override.js` next to the plugin's configuration file, in Jellyfin's `plugins/configurations` folder (`/config/plugins/configurations/` in the official image). If present, it is served instead of the built-in script, so you can edit it and reload the page without rebuilding or restarting Jellyfin.

## How cards are detected

On `pointerover` the script finds the hovered `.card`, looks for an `/Items/<id>/Images/Primary` URL in its markup, and only continues if the depth service has data for that item. Cards showing other image types (thumbs, backdrops) are ignored.
