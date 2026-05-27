"""GET /files — hardcoded prefix + kind derivation.

The endpoint must never accept a user-supplied prefix and must classify
each artifact key into the closed enum the frontend depends on.
"""

import pytest
from fastapi.testclient import TestClient

from app.runtime import files as files_runtime


@pytest.fixture
def client(monkeypatch):
    """Bypass the lifespan B2-creds check by mounting the router on a
    bare FastAPI app — this isolates the route logic from settings."""
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(files_runtime.router)
    return TestClient(app)


def _stub_list_objects(monkeypatch, *, captured: dict):
    """Capture the args that runtime.files passes to repo.b2_client."""

    def fake_list_objects(prefix, max_keys=100, continuation_token=None):
        captured["prefix"] = prefix
        captured["max_keys"] = max_keys
        captured["continuation_token"] = continuation_token
        return {
            "objects": [
                {
                    "key": "video-to-insights-pipeline/v1/source.mp4",
                    "size": 1024,
                    "last_modified": "2026-01-01T00:00:00+00:00",
                    "etag": "abc",
                },
                {
                    "key": "video-to-insights-pipeline/v1/transcript.json",
                    "size": 256,
                    "last_modified": "2026-01-01T00:00:01+00:00",
                    "etag": "def",
                },
                {
                    "key": "video-to-insights-pipeline/v1/insights.json",
                    "size": 128,
                    "last_modified": "2026-01-01T00:00:02+00:00",
                    "etag": "ghi",
                },
                {
                    "key": "video-to-insights-pipeline/v1/manifest.json",
                    "size": 64,
                    "last_modified": "2026-01-01T00:00:03+00:00",
                    "etag": "jkl",
                },
                {
                    "key": "video-to-insights-pipeline/jobs-index.json",
                    "size": 512,
                    "last_modified": "2026-01-01T00:00:04+00:00",
                    "etag": "mno",
                },
                {
                    "key": "video-to-insights-pipeline/v1/extra.bin",
                    "size": 8,
                    "last_modified": "2026-01-01T00:00:05+00:00",
                    "etag": "pqr",
                },
            ],
            "next_token": "page2",
        }

    monkeypatch.setattr(files_runtime.b2_client, "list_objects", fake_list_objects)


def test_files_endpoint_hardcodes_prefix(monkeypatch, client):
    captured: dict = {}
    _stub_list_objects(monkeypatch, captured=captured)

    # Even if a `prefix` query is supplied, the runtime ignores it.
    res = client.get("/files", params={"prefix": "anywhere-else/"})
    assert res.status_code == 200
    assert captured["prefix"] == "video-to-insights-pipeline/"


def test_files_endpoint_kind_derivation(monkeypatch, client):
    captured: dict = {}
    _stub_list_objects(monkeypatch, captured=captured)

    res = client.get("/files")
    body = res.json()
    by_key = {obj["key"]: obj["kind"] for obj in body["objects"]}
    assert by_key["video-to-insights-pipeline/v1/source.mp4"] == "source"
    assert by_key["video-to-insights-pipeline/v1/transcript.json"] == "transcript"
    assert by_key["video-to-insights-pipeline/v1/insights.json"] == "insights"
    assert by_key["video-to-insights-pipeline/v1/manifest.json"] == "manifest"
    assert by_key["video-to-insights-pipeline/jobs-index.json"] == "jobs_index"
    assert by_key["video-to-insights-pipeline/v1/extra.bin"] == "other"
    assert body["next_token"] == "page2"


def test_files_endpoint_passes_pagination(monkeypatch, client):
    captured: dict = {}
    _stub_list_objects(monkeypatch, captured=captured)

    client.get("/files", params={"continuation_token": "abc", "max_keys": 50})
    assert captured["continuation_token"] == "abc"
    assert captured["max_keys"] == 50


def test_files_preview_rejects_keys_outside_prefix(monkeypatch, client):
    res = client.get("/files/preview", params={"key": "evil-prefix/secret.txt"})
    assert res.status_code == 400


def test_files_content_proxies_json_inline(monkeypatch, client):
    """Bytes come through with content-type application/json so the
    browser doesn't have to fetch cross-origin from B2."""
    payload = b'{"hello": "world"}'

    def fake_get_bytes(key):
        assert key == "video-to-insights-pipeline/v1/insights.json"
        return payload

    monkeypatch.setattr(files_runtime.b2_client, "get_bytes", fake_get_bytes)
    res = client.get(
        "/files/content",
        params={"key": "video-to-insights-pipeline/v1/insights.json"},
    )
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/json"
    assert res.content == payload


def test_files_content_rejects_non_json(monkeypatch, client):
    """The proxy is JSON-only — video should be served via the presigned
    URL endpoint, not streamed through the API."""
    res = client.get(
        "/files/content",
        params={"key": "video-to-insights-pipeline/v1/source.mp4"},
    )
    assert res.status_code == 415


def test_files_content_rejects_keys_outside_prefix(monkeypatch, client):
    res = client.get("/files/content", params={"key": "evil-prefix/x.json"})
    assert res.status_code == 400
