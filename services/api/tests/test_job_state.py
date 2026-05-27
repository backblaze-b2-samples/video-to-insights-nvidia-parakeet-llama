"""Atomic per-job state file (tmp + rename, one file per job)."""

import json
from datetime import UTC, datetime

from app.repo import job_state
from app.types import JobStatus


def _make(job_id: str = "j1") -> JobStatus:
    now = datetime.now(UTC)
    return JobStatus(
        job_id=job_id,
        video_id="v1",
        source_url="https://www.youtube.com/watch?v=x",
        created_at=now,
        updated_at=now,
    )


def test_write_then_read_roundtrip():
    s = _make()
    job_state.write(s)
    out = job_state.read("j1")
    assert out is not None
    assert out.job_id == "j1"
    assert out.video_id == "v1"


def test_read_missing_returns_none():
    assert job_state.read("does-not-exist") is None


def test_request_cancel_sets_flag():
    s = _make()
    job_state.write(s)
    updated = job_state.request_cancel("j1")
    assert updated is not None
    assert updated.cancel_requested is True

    persisted = job_state.read("j1")
    assert persisted is not None
    assert persisted.cancel_requested is True


def test_request_cancel_no_op_on_terminal():
    s = _make()
    s.status = "done"
    job_state.write(s)
    updated = job_state.request_cancel("j1")
    assert updated is not None
    assert updated.cancel_requested is False  # terminal job, no flag flip


def test_write_updates_updated_at(tmp_path):
    s = _make()
    job_state.write(s)
    first = job_state.read("j1").updated_at  # type: ignore[union-attr]
    s.status = "downloading"
    job_state.write(s)
    second = job_state.read("j1").updated_at  # type: ignore[union-attr]
    assert second >= first


def test_torn_write_recovers(tmp_path, monkeypatch):
    """An unrelated .tmp left behind doesn't break read; the canonical file wins."""
    from app.config import settings

    s = _make()
    job_state.write(s)
    # Drop a corrupt stray tmp file in the jobs dir — must be ignored.
    jobs_dir = (tmp_path / "jobs")
    stray = jobs_dir / "j1.json.999.tmp"
    stray.write_text("{not json")
    s2 = job_state.read("j1")
    assert s2 is not None
    assert s2.job_id == "j1"

    # Ensure persisted canonical file is still well-formed JSON.
    with open(jobs_dir / "j1.json") as f:
        json.load(f)
    assert settings.work_dir == str(tmp_path)
