# Troubleshooting

**Nothing happens on hover**
- Reload the web UI with Ctrl+Shift+R.
- Check that `/DepthPosters/script.js` loads (open it in the browser). A 404 means the plugin is not loaded; look for `Depth Posters registered its index.html transformation` in Jellyfin's log.
- If the log says *needs the File Transformation plugin*, install it and restart Jellyfin.
- Open the browser console and look for errors.
- Only items the service has finished have the effect. Check progress in the service logs or `/api/status`.

**The service logs `401 Unauthorized`**
Jellyfin 12 expects the API key in the `Authorization: MediaBrowser Token="…"` header; `X-Emby-Token` and `?api_key=` are rejected. The service already sends the right header, so a 401 means the key is wrong or was revoked. Create a new one in *Dashboard → Advanced → API Keys*.

**The service logs `Connection refused` or can't resolve `jellyfin`**
The service and Jellyfin are not on the same Docker network. Set `JELLYFIN_NETWORK` to the network Jellyfin uses (`docker inspect jellyfin` shows it) and `JELLYFIN_URL` to Jellyfin's container name and port. Items that failed while Jellyfin was down are retried on the next scan.

**The plugin returns 502 for depth data**
Jellyfin can't reach the service. Check the plugin's *Service URL* and that both containers share a network (`docker exec jellyfin curl http://jellyfin-depth-posters:8000/api/status`).

**`permission denied` writing `/data` or `/cache`**
Set `PUID`/`PGID` in `.env` to the owner of `./data` and `./.cache`.

**Everything is slow**
Depth estimation runs on the CPU. See the [timings](how-it-works.md#performance) and consider `DEPTH_MODEL=small` and `ENABLE_LAYERS=false`.

**The effect looks wrong on some cards**
Open an issue with the browser, Jellyfin version, and which view (library, home, search) it happens in.
