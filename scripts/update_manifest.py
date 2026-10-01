#!/usr/bin/env python3
"""Add a release to the Jellyfin plugin repository manifest.

usage: update_manifest.py <version> <zip file> <download url> [changelog]
"""
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

version, zip_path, url = sys.argv[1:4]
changelog = sys.argv[4] if len(sys.argv) > 4 else f"Release {version}"

manifest_path = Path(__file__).resolve().parent.parent / "manifest.json"
manifest = json.loads(manifest_path.read_text())

entry = {
    "version": version,
    "changelog": changelog,
    "targetAbi": "12.1.0.0",
    "sourceUrl": url,
    "checksum": hashlib.md5(Path(zip_path).read_bytes()).hexdigest(),  # Jellyfin expects MD5
    "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
}
versions = [v for v in manifest[0]["versions"] if v["version"] != version]
manifest[0]["versions"] = [entry, *versions]
manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
print(f"manifest updated: {version}")
