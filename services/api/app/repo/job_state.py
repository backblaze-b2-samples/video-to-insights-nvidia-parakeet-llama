"""Atomic per-job state files.

One JSON file per job at `${WORK_DIR}/jobs/{job_id}.json`. Writes go via
tmp+os.replace so a reader is always seeing a fully-formed document — no
in-memory dict, no asyncio.Lock, no Redis. The pipeline writes; the
runtime reads. POSIX rename is atomic on the same filesystem; that's the
only invariant we depend on.

A stray `.tmp.*` left over from a process kill is harmless: it'll be
cleaned up the next time `write` runs in the same directory, and `read`
ignores everything that isn't `{uuid}.json`.
"""

import contextlib
import json
import os
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path

from app.config import settings
from app.types import JobStatus


def _jobs_dir() -> Path:
    d = Path(settings.work_dir) / "jobs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _safe_job_id(job_id: str) -> str:
    try:
        parsed = uuid.UUID(hex=job_id)
    except ValueError as e:
        raise ValueError("invalid job_id") from e
    return parsed.hex


def _path_for(job_id: str) -> Path:
    jobs_dir = _jobs_dir().resolve()
    path = (jobs_dir / f"{_safe_job_id(job_id)}.json").resolve()
    if path.parent != jobs_dir:
        raise ValueError("invalid job path")
    return path


def write(status: JobStatus) -> None:
    """Atomically persist a JobStatus. Updates `updated_at` to now().

    `cancel_requested` is the only field a user can set out-of-band
    (via DELETE /jobs/{id}). The pipeline holds an in-memory copy of
    status that doesn't know about that mutation, so we merge the flag
    from disk forward — once the user asks to cancel, no subsequent
    pipeline write can erase the request.
    """
    status.updated_at = datetime.now(UTC)
    path = _path_for(status.job_id)
    existing = _read_path(path)
    if existing is not None and existing.cancel_requested:
        status.cancel_requested = True
    payload = status.model_dump(mode="json")
    fd, tmp = tempfile.mkstemp(
        dir=path.parent, prefix=f"{path.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(payload, f, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


def _read_path(path: Path) -> JobStatus | None:
    try:
        with open(path) as f:
            return JobStatus.model_validate_json(f.read())
    except (FileNotFoundError, json.JSONDecodeError, ValueError):
        return None


def read(job_id: str) -> JobStatus | None:
    """Return the JobStatus, or None if the file is missing or unreadable.

    A partial/torn file (mid-write) is impossible because writers go
    through tmp+rename, but if a JSON decode does fail we return None
    rather than blowing up the runtime — the caller surfaces 404.
    """
    try:
        path = _path_for(job_id)
    except ValueError:
        return None
    return _read_path(path)


def request_cancel(job_id: str) -> JobStatus | None:
    """Set the cancel flag on an existing job. Returns the updated status, or None."""
    status = read(job_id)
    if status is None:
        return None
    if status.status in ("done", "done_no_analysis", "failed", "cancelled"):
        return status  # nothing to cancel; return as-is
    status.cancel_requested = True
    write(status)
    return status
