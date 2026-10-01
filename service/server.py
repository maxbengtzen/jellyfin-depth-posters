"""Depth service: keeps depth maps (and optionally layers) for Jellyfin posters in sync.

Background: scan Jellyfin -> queue items whose current Primary image has no (complete)
output yet -> generate one at a time. A finished item lives in /data/<itemId>/<imageTag>/
with a manifest.json; a changed poster gets a new tag and is therefore regenerated.
"""
import io
import json
import logging
import os
import queue
import re
import shutil
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from PIL import Image

import core

JELLYFIN_URL = os.environ.get("JELLYFIN_URL", "http://jellyfin:8096").rstrip("/")
API_KEY = os.environ.get("JELLYFIN_API_KEY", "")
DEPTH_MODEL = os.environ.get("DEPTH_MODEL", "small")
ENABLE_LAYERS = os.environ.get("ENABLE_LAYERS", "false").lower() == "true"
MAX_SIZE = int(os.environ.get("MAX_SIZE", "720"))
SCAN_INTERVAL = int(os.environ.get("SCAN_INTERVAL_MIN", "30")) * 60
ITEM_TYPES = os.environ.get("ITEM_TYPES", "Movie,Series")
DATA = Path("/data")

if DEPTH_MODEL not in core.MODELS:
    raise SystemExit(f"DEPTH_MODEL must be one of {', '.join(core.MODELS)}, got {DEPTH_MODEL!r}")

ID_RE = re.compile(r"^[0-9a-fA-F-]{32,36}$")
NAME_RE = re.compile(r"^[\w.-]+$")

log = logging.getLogger("depth")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

jobs: "queue.Queue[tuple[str, str]]" = queue.Queue()
queued: set[tuple[str, str]] = set()
failed: set[tuple[str, str]] = set()
state = {"total": 0, "done": 0, "current": None, "last_scan": None, "scanning": False}
lock = threading.Lock()
scan_now = threading.Event()


def jf(path, **params):
    r = httpx.get(f"{JELLYFIN_URL}{path}", params=params, headers={"Authorization": f'MediaBrowser Token="{API_KEY}"'}, timeout=60)
    r.raise_for_status()
    return r


def is_done(item_id, tag):
    """Output exists, and includes layers when layers are enabled."""
    path = DATA / item_id / tag / "manifest.json"
    if not path.exists():
        return False
    return not ENABLE_LAYERS or "layers" in json.loads(path.read_text())


def scan():
    """Queue every item whose current poster has no output yet; drop outputs for vanished items."""
    with lock:
        state["scanning"] = True
    try:
        items = jf("/Items", Recursive="true", IncludeItemTypes=ITEM_TYPES, Fields="ImageTags",
                   EnableImageTypes="Primary").json()["Items"]
        wanted = {i["Id"]: i["ImageTags"]["Primary"] for i in items if i.get("ImageTags", {}).get("Primary")}
        done = 0
        for item_id, tag in wanted.items():
            if is_done(item_id, tag):
                done += 1
            elif (item_id, tag) not in queued and (item_id, tag) not in failed:
                queued.add((item_id, tag))
                jobs.put((item_id, tag))
        # Only clean up when Jellyfin actually returned items (an empty reply may be a glitch).
        if wanted:
            for d in DATA.iterdir():
                if d.is_dir() and ID_RE.match(d.name) and d.name not in wanted:
                    shutil.rmtree(d, ignore_errors=True)
        with lock:
            state.update(total=len(wanted), done=done, last_scan=int(time.time()))
        log.info("scan: %d items, %d done, %d queued", len(wanted), done, jobs.qsize())
    finally:
        with lock:
            state["scanning"] = False


def process(item_id, tag, models):
    r = jf(f"/Items/{item_id}/Images/Primary", tag=tag, maxWidth=MAX_SIZE, maxHeight=MAX_SIZE, quality=95)
    image = Image.open(io.BytesIO(r.content)).convert("RGB")
    if max(image.size) > MAX_SIZE:
        k = MAX_SIZE / max(image.size)
        image = image.resize((round(image.width * k), round(image.height * k)), Image.LANCZOS)

    depth = core.depth_map(models["depth"], image)
    tmp = DATA / item_id / f"{tag}.tmp"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    Image.fromarray(depth, "L").save(tmp / "depth.png")
    manifest = {"itemId": item_id, "tag": tag, "model": DEPTH_MODEL, "width": image.width,
                "height": image.height, "depth": "depth.png"}

    if ENABLE_LAYERS:
        layers, depths = core.build_layers(models["lama"], np.asarray(image), depth)
        for k, layer in enumerate(layers):
            core.save_layer(layer, tmp / f"layer_{k}.webp")
        manifest["layers"] = {"files": [f"layer_{k}.webp" for k in range(len(layers))], "depths": depths}

    (tmp / "manifest.json").write_text(json.dumps(manifest))
    final = DATA / item_id / tag
    shutil.rmtree(final, ignore_errors=True)
    tmp.rename(final)
    # A new poster replaces the old one.
    for old in (DATA / item_id).iterdir():
        if old.name != tag:
            shutil.rmtree(old, ignore_errors=True)


def worker():
    models = {}
    while True:
        item_id, tag = jobs.get()
        with lock:
            state["current"] = item_id
        start = time.time()
        try:
            if "depth" not in models:
                models["depth"] = core.load_depth_model(DEPTH_MODEL)
            if ENABLE_LAYERS and "lama" not in models:
                models["lama"] = core.load_lama()
            process(item_id, tag, models)
            with lock:
                state["done"] += 1
            log.info("%s done in %.1fs", item_id, time.time() - start)
        except (httpx.TransportError, httpx.HTTPStatusError) as e:
            # Jellyfin unreachable or erroring (e.g. restarting): not the item's fault.
            # Leave it unmarked so the next scan retries, and back off a little.
            transient = isinstance(e, httpx.TransportError) or e.response.status_code >= 500
            if not transient:
                failed.add((item_id, tag))
            log.warning("%s failed (%s)%s", item_id, e, "; will retry on next scan" if transient else "")
            time.sleep(5 if transient else 0)
        except Exception:
            log.exception("%s failed", item_id)
            failed.add((item_id, tag))
        finally:
            queued.discard((item_id, tag))
            with lock:
                state["current"] = None


def scanner():
    while True:
        try:
            if API_KEY:
                scan()
            else:
                log.warning("JELLYFIN_API_KEY is not set; not scanning")
        except Exception:
            log.exception("scan failed")
        scan_now.wait(SCAN_INTERVAL)
        scan_now.clear()


@asynccontextmanager
async def lifespan(_app):
    DATA.mkdir(exist_ok=True)
    threading.Thread(target=worker, daemon=True).start()
    threading.Thread(target=scanner, daemon=True).start()
    log.info("model=%s layers=%s max_size=%d jellyfin=%s", DEPTH_MODEL, ENABLE_LAYERS, MAX_SIZE, JELLYFIN_URL)
    yield


app = FastAPI(title="jellyfin-depth-posters", lifespan=lifespan)


def item_dir(item_id):
    if not ID_RE.match(item_id):
        raise HTTPException(400, "bad item id")
    return DATA / item_id


@app.get("/depth/{item_id}/manifest.json")
def manifest(item_id: str):
    d = item_dir(item_id)
    ready = sorted(d.glob("*/manifest.json"), key=lambda p: p.stat().st_mtime, reverse=True) if d.exists() else []
    if not ready:
        raise HTTPException(404, "not generated yet")
    return JSONResponse(json.loads(ready[0].read_text()), headers={"Cache-Control": "public, max-age=60"})


@app.get("/depth/{item_id}/{tag}/{name}")
def file(item_id: str, tag: str, name: str):
    if not (NAME_RE.match(tag) and NAME_RE.match(name)):
        raise HTTPException(400, "bad path")
    path = item_dir(item_id) / tag / name
    if not path.is_file():
        raise HTTPException(404)
    return FileResponse(path, headers={"Cache-Control": "public, max-age=31536000, immutable"})


@app.get("/api/status")
def status():
    with lock:
        return {**state, "queued": jobs.qsize(), "failed": len(failed), "model": DEPTH_MODEL, "layers": ENABLE_LAYERS}


@app.post("/api/scan")
def trigger_scan():
    scan_now.set()
    return {"ok": True}
