import json

import pytest
from fastapi.testclient import TestClient

import server

ITEM = "0123456789abcdef0123456789abcdef"


@pytest.fixture
def data(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "DATA", tmp_path)
    monkeypatch.setattr(server, "ENABLE_LAYERS", False)
    server.queued.clear()
    server.failed.clear()
    while not server.jobs.empty():
        server.jobs.get_nowait()
    return tmp_path


def make_output(root, item, tag, **extra):
    d = root / item / tag
    d.mkdir(parents=True)
    (d / "manifest.json").write_text(json.dumps({"itemId": item, "tag": tag, "depth": "depth.png", **extra}))
    (d / "depth.png").write_bytes(b"png")
    return d


def test_is_done_requires_manifest(data):
    assert not server.is_done(ITEM, "t1")
    make_output(data, ITEM, "t1")
    assert server.is_done(ITEM, "t1")


def test_is_done_requires_layers_when_enabled(data, monkeypatch):
    make_output(data, ITEM, "t1")
    monkeypatch.setattr(server, "ENABLE_LAYERS", True)
    assert not server.is_done(ITEM, "t1")
    (data / ITEM / "t1" / "manifest.json").write_text(json.dumps({"layers": {"files": [], "depths": []}}))
    assert server.is_done(ITEM, "t1")


def fake_jellyfin(monkeypatch, items):
    class Reply:
        def json(self):
            return {"Items": items}

    monkeypatch.setattr(server, "jf", lambda path, **params: Reply())


def test_scan_queues_only_missing_and_cleans_vanished(data, monkeypatch):
    other = "f" * 32
    make_output(data, ITEM, "t1")            # already done
    make_output(data, "a" * 32, "old")       # item no longer in Jellyfin
    fake_jellyfin(monkeypatch, [
        {"Id": ITEM, "ImageTags": {"Primary": "t1"}},
        {"Id": other, "ImageTags": {"Primary": "t9"}},
        {"Id": "b" * 32, "ImageTags": {}},   # no poster
    ])
    server.scan()
    assert server.jobs.get_nowait() == (other, "t9")
    assert server.jobs.empty()
    assert not (data / ("a" * 32)).exists()
    assert (data / ITEM).exists()
    assert server.state["total"] == 2 and server.state["done"] == 1


def test_scan_keeps_data_when_jellyfin_returns_nothing(data, monkeypatch):
    make_output(data, ITEM, "t1")
    fake_jellyfin(monkeypatch, [])
    server.scan()
    assert (data / ITEM / "t1").exists()


def test_manifest_endpoint(data):
    client = TestClient(server.app)
    assert client.get(f"/depth/{ITEM}/manifest.json").status_code == 404
    make_output(data, ITEM, "t1")
    reply = client.get(f"/depth/{ITEM}/manifest.json")
    assert reply.status_code == 200 and reply.json()["tag"] == "t1"


def test_file_endpoint_and_validation(data):
    make_output(data, ITEM, "t1")
    client = TestClient(server.app)
    ok = client.get(f"/depth/{ITEM}/t1/depth.png")
    assert ok.status_code == 200 and "immutable" in ok.headers["cache-control"]
    assert client.get(f"/depth/{ITEM}/t1/missing.png").status_code == 404
    assert client.get("/depth/not-an-id/manifest.json").status_code == 400
    assert client.get(f"/depth/{ITEM}/bad tag/depth.png").status_code == 400
    assert client.get(f"/depth/{ITEM}/t1/..%2Fx").status_code in (400, 404)
