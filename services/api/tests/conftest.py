"""Shared test fixtures.

Tests must not touch real B2 or NVIDIA. We default-set the required env
vars to harmless values so `Settings()` is happy; individual tests
monkeypatch what they need. Each test gets a private WORK_DIR.
"""

import os
from pathlib import Path

import pytest

os.environ.setdefault("B2_APPLICATION_KEY_ID", "test-key-id")
os.environ.setdefault("B2_REGION", "us-test-001")
os.environ.setdefault("B2_APPLICATION_KEY", "test-app-key")
os.environ.setdefault("B2_BUCKET_NAME", "test-bucket")
os.environ.setdefault("B2_PUBLIC_URL_BASE", "")


@pytest.fixture(autouse=True)
def isolate_work_dir(tmp_path: Path, monkeypatch):
    """Redirect WORK_DIR to a per-test temp dir so job-state files don't bleed."""
    from app.config import settings

    monkeypatch.setattr(settings, "work_dir", str(tmp_path))
    yield


@pytest.fixture
def fake_b2():
    """In-memory B2 stand-in: tracks every uploaded key and its bytes/json."""

    class FakeB2:
        def __init__(self):
            self.objects: dict[str, dict] = {}
            self.files: dict[str, bytes] = {}

        def put_file(self, key: str, path: str, content_type: str) -> int:
            with open(path, "rb") as f:
                data = f.read()
            self.files[key] = data
            self.objects[key] = {"content_type": content_type, "size": len(data)}
            return len(data)

        def put_json(self, key: str, payload: dict) -> None:
            self.objects[key] = {"content_type": "application/json", "json": payload}

    return FakeB2()
