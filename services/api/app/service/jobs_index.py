"""Denormalized job-summary index, persisted as one B2 object.

Replaces N manifest GETs on every dashboard load with a single round
trip. Writes happen once per finished job from the pipeline; reads
happen on every dashboard render.

Concurrency: the API runs single-worker (see AGENTS.md), so there is no
multi-writer race against the index. If that constraint ever changes
this module needs an ETag-conditional write loop.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

from app.repo import get_bytes, put_json
from app.types import JobIndexEntry, JobsIndex

logger = logging.getLogger(__name__)

INDEX_KEY = "video-to-insights-pipeline/jobs-index.json"


def _empty_index() -> JobsIndex:
    return JobsIndex(updated_at=datetime.now(UTC), jobs=[])


def read_index() -> JobsIndex:
    """Fetch the index from B2. Missing object -> empty index, not error."""
    raw = get_bytes(INDEX_KEY)
    if raw is None:
        return _empty_index()
    try:
        payload = json.loads(raw.decode("utf-8"))
        return JobsIndex.model_validate(payload)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as e:
        # A corrupt index would otherwise wedge the dashboard forever.
        # Log loudly and degrade to empty — the next successful job
        # writes a fresh, valid index over the top.
        logger.warning("jobs-index parse failed (%s); starting fresh", e)
        return _empty_index()


def _write_index(index: JobsIndex) -> None:
    payload = json.loads(index.model_dump_json())
    put_json(INDEX_KEY, payload)


def append_to_index(entry: JobIndexEntry) -> None:
    """Read, dedupe by job_id, append, write. One round-trip each way.

    Newest-first ordering is enforced on read (`list_jobs`) rather than
    here, so we never have to re-sort on write.
    """
    index = read_index()
    # Re-submissions of the same job_id replace the prior entry rather
    # than duplicate. job_id is unique per submission so this is a
    # rare path, but cheap insurance against pipeline retries.
    index.jobs = [j for j in index.jobs if j.job_id != entry.job_id]
    index.jobs.append(entry)
    index.updated_at = datetime.now(UTC)
    _write_index(index)


def _sorted_jobs(index: JobsIndex) -> list[JobIndexEntry]:
    """Newest-first by created_at — derives ordering on read so append is O(1)."""
    return sorted(index.jobs, key=lambda j: j.created_at, reverse=True)


def latest() -> JobIndexEntry | None:
    """Most recent successful job, or None if the index is empty."""
    jobs = _sorted_jobs(read_index())
    return jobs[0] if jobs else None


def list_jobs(limit: int = 50, offset: int = 0) -> tuple[list[JobIndexEntry], int]:
    """Newest-first page of jobs plus the unpaginated total."""
    jobs = _sorted_jobs(read_index())
    total = len(jobs)
    page = jobs[offset : offset + limit]
    return page, total
