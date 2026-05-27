"""jobs_index service: round-trip, dedupe, ordering, pagination.

Uses a monkeypatched repo so we exercise the JSON-on-B2 contract without
any boto3. The single-worker constraint means we don't need to test
concurrent writes.
"""

from datetime import UTC, datetime, timedelta

import pytest

from app.service import jobs_index
from app.types import JobIndexEntry


@pytest.fixture
def fake_repo(monkeypatch):
    """In-memory stand-in for repo.get_bytes / repo.put_json."""

    store: dict[str, bytes] = {}

    def fake_get_bytes(key: str) -> bytes | None:
        return store.get(key)

    def fake_put_json(key: str, payload: dict) -> None:
        import json

        store[key] = json.dumps(payload, separators=(",", ":")).encode("utf-8")

    monkeypatch.setattr(jobs_index, "get_bytes", fake_get_bytes)
    monkeypatch.setattr(jobs_index, "put_json", fake_put_json)
    return store


def _entry(job_id: str, *, created_at: datetime | None = None, **kwargs) -> JobIndexEntry:
    defaults = dict(
        video_id=f"v-{job_id}",
        job_id=job_id,
        source_url=f"https://www.youtube.com/watch?v={job_id}",
        duration_seconds=120.0,
        size_bytes=1024,
        insights_count=3,
        analysis_status="ok",
        created_at=created_at or datetime.now(UTC),
        manifest_key=f"video-to-insights-pipeline/v-{job_id}/manifest.json",
        source_key=f"video-to-insights-pipeline/v-{job_id}/source.mp4",
    )
    defaults.update(kwargs)
    return JobIndexEntry(**defaults)


def test_read_missing_returns_empty(fake_repo):
    """B2 has no index object yet — read_index must NOT raise."""
    index = jobs_index.read_index()
    assert index.jobs == []
    assert index.schema_version == 1


def test_append_and_read_round_trip(fake_repo):
    jobs_index.append_to_index(_entry("a"))
    jobs_index.append_to_index(_entry("b"))

    index = jobs_index.read_index()
    assert {j.job_id for j in index.jobs} == {"a", "b"}


def test_dedupe_by_job_id_on_re_append(fake_repo):
    """A pipeline retry of the same job_id must replace, not duplicate."""
    jobs_index.append_to_index(_entry("a", insights_count=3))
    jobs_index.append_to_index(_entry("a", insights_count=7))

    index = jobs_index.read_index()
    assert len(index.jobs) == 1
    assert index.jobs[0].insights_count == 7


def test_list_jobs_sorted_newest_first(fake_repo):
    now = datetime.now(UTC)
    jobs_index.append_to_index(_entry("old", created_at=now - timedelta(hours=2)))
    jobs_index.append_to_index(_entry("new", created_at=now))
    jobs_index.append_to_index(_entry("mid", created_at=now - timedelta(hours=1)))

    page, total = jobs_index.list_jobs(limit=10, offset=0)
    assert [j.job_id for j in page] == ["new", "mid", "old"]
    assert total == 3


def test_list_jobs_pagination(fake_repo):
    now = datetime.now(UTC)
    for i in range(5):
        jobs_index.append_to_index(
            _entry(f"j{i}", created_at=now - timedelta(seconds=i))
        )

    first, total1 = jobs_index.list_jobs(limit=2, offset=0)
    second, total2 = jobs_index.list_jobs(limit=2, offset=2)

    assert total1 == total2 == 5
    assert [j.job_id for j in first] == ["j0", "j1"]
    assert [j.job_id for j in second] == ["j2", "j3"]


def test_latest_empty_and_populated(fake_repo):
    assert jobs_index.latest() is None

    now = datetime.now(UTC)
    jobs_index.append_to_index(_entry("old", created_at=now - timedelta(hours=1)))
    jobs_index.append_to_index(_entry("new", created_at=now))

    latest = jobs_index.latest()
    assert latest is not None
    assert latest.job_id == "new"


def test_corrupt_index_falls_back_to_empty(fake_repo, caplog):
    """A torn or wrong-shape index file must not wedge the dashboard."""
    fake_repo[jobs_index.INDEX_KEY] = b"{not json"

    index = jobs_index.read_index()
    assert index.jobs == []
