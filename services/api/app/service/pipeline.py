"""Pipeline orchestrator — sequences yt-dlp -> B2 upload -> ASR -> insights -> manifest.

Public entry: `run_job(job_id, ...)`. The runtime layer schedules this
as an `asyncio.Task` under a lifespan-managed Semaphore.

Subprocess calls (yt-dlp, ffmpeg, ffprobe) all go through helper
callables. The pipeline wraps them in `asyncio.to_thread` so blocking
work never lands on the event loop. Tests inject lightweight fakes via
the `deps` argument and the subprocess paths never run.

Cancellation: between every stage we re-read the state file and bail
with status="cancelled" if cancel_requested is True. A subprocess
already in flight will run to completion — README documents this.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.config import settings
from app.repo import job_state, put_file, put_json
from app.service import asr as asr_module
from app.service import ffmpeg_audio, jobs_index, stages
from app.service import insights as insights_module
from app.service.downloader import YtDlpError, default_download
from app.types import Insight, JobIndexEntry, JobStatus

logger = logging.getLogger(__name__)

# Re-exported for callers that still import from pipeline.
ASR_CHUNK_SECONDS = stages.ASR_CHUNK_SECONDS


@dataclass
class PipelineDeps:
    """Injection seam — tests pass fakes; main wires real implementations."""

    download_video: Callable[[str, str], dict[str, Any]] = field(default=None)  # type: ignore[assignment]
    probe_duration: Callable[[str], float] = ffmpeg_audio.probe_duration
    extract_audio: Callable[[str, str], None] = ffmpeg_audio.extract_audio
    chunk_audio: Callable[[str, str, int], list[tuple[str, float]]] = ffmpeg_audio.chunk_audio
    transcribe: Callable[[list[tuple[str, float]]], dict[str, Any]] = (
        asr_module.transcribe_chunks
    )
    extract_insights: Callable[[dict[str, Any]], list[Insight]] = (
        insights_module.extract_insights
    )
    put_file_to_b2: Callable[[str, str, str], int] = put_file
    put_json_to_b2: Callable[[str, dict], None] = put_json


def new_job(video_id: str | None, source_url: str) -> JobStatus:
    """Create + persist the initial JobStatus."""
    vid = video_id or uuid.uuid4().hex
    now = stages.now()
    status = JobStatus(
        job_id=uuid.uuid4().hex,
        video_id=vid,
        source_url=source_url,
        created_at=now,
        updated_at=now,
    )
    job_state.write(status)
    return status


async def _download_and_probe(
    status: JobStatus, deps: PipelineDeps, source_path: str
) -> float | None:
    """Download source + probe duration. Returns duration or None on terminal failure."""
    stages.set_stage(status, "downloading", "downloading", 0, 1)
    try:
        await asyncio.to_thread(deps.download_video, status.source_url, source_path)
    except YtDlpError as e:
        stages.fail(status, e.code, e.message)
        return None
    except FileNotFoundError as e:
        stages.fail(status, "yt_dlp_failed", f"download executable unavailable: {e}")
        return None

    try:
        duration = await asyncio.to_thread(deps.probe_duration, source_path)
    except ffmpeg_audio.FfmpegError as e:
        stages.fail(status, "ffprobe_failed", str(e))
        return None
    if duration > settings.max_video_seconds:
        stages.fail(
            status,
            "video_too_long",
            f"Video is {duration:.0f}s, exceeds MAX_VIDEO_SECONDS={settings.max_video_seconds}",
        )
        return None
    return duration


async def _upload_source(
    status: JobStatus, deps: PipelineDeps, source_path: str
) -> int | None:
    """Upload source to B2 and record the key. Returns size or None on failure."""
    stages.set_stage(status, "uploading_source", "uploading_source", 0, 1)
    source_key = stages.key(status.video_id, "source.mp4")
    try:
        size_bytes = await asyncio.to_thread(
            deps.put_file_to_b2, source_key, source_path, "video/mp4"
        )
    except RuntimeError as e:
        stages.fail(status, "b2_upload_failed", str(e))
        return None
    status.result.source_key = source_key
    job_state.write(status)
    return size_bytes


def _record_in_index(
    status: JobStatus, duration: float | None, size_bytes: int | None, insights_count: int
) -> None:
    """Append a summary to the B2-persisted jobs index.

    Called once per job AFTER the manifest lands. Best-effort — a failure
    here must NOT fail the job, since the durable artifacts are already
    in B2 and a stale index just means the dashboard misses one row.
    """
    # Index only "landed in B2" outcomes; failed/cancelled jobs have no
    # source object and would just produce broken rows in the dashboard.
    if status.analysis_status not in ("ok", "skipped_no_api_key", "failed_asr", "failed_insights"):
        return
    if not status.result.manifest_key or not status.result.source_key:
        return
    entry = JobIndexEntry(
        video_id=status.video_id,
        job_id=status.job_id,
        source_url=status.source_url,
        duration_seconds=duration,
        size_bytes=size_bytes,
        insights_count=insights_count,
        analysis_status=status.analysis_status,  # type: ignore[arg-type]
        created_at=status.created_at,
        manifest_key=status.result.manifest_key,
        source_key=status.result.source_key,
    )
    try:
        jobs_index.append_to_index(entry)
    except Exception as e:
        # Intentionally swallow: the manifest already landed; a stale
        # index just means the dashboard misses one row.
        logger.warning("jobs-index append failed for %s: %s", status.job_id, e)


async def run_job(job_id: str, deps: PipelineDeps | None = None) -> None:
    """Drive a single job to a terminal state.

    Never raises — failures are written into the JobStatus file and the
    function returns.
    """
    status = job_state.read(job_id)
    if status is None:
        logger.error("run_job: missing state for %s", job_id)
        return

    deps = deps or PipelineDeps(download_video=default_download)
    if deps.download_video is None:
        deps.download_video = default_download

    work_dir = Path(settings.work_dir) / status.video_id
    work_dir.mkdir(parents=True, exist_ok=True)
    source_path = str(work_dir / "source.mp4")
    audio_path = str(work_dir / "audio.wav")
    chunks_dir = str(work_dir / "chunks")

    try:
        if stages.cancelled(job_id):
            stages.finalize(status, "cancelled")
            return

        duration = await _download_and_probe(status, deps, source_path)
        if duration is None:
            return

        if stages.cancelled(job_id):
            stages.finalize(status, "cancelled")
            return

        size_bytes = await _upload_source(status, deps, source_path)
        if size_bytes is None:
            return

        # Graceful degradation: no key -> source-only.
        if not settings.nvidia_api_key:
            status.analysis_status = "skipped_no_api_key"
            status.analysis_message = "NVIDIA_API_KEY not set; analysis skipped."
            await stages.write_manifest(status, deps, duration, size_bytes, insights=[])
            _record_in_index(status, duration, size_bytes, insights_count=0)
            stages.finalize(status, "done_no_analysis")
            return

        if stages.cancelled(job_id):
            stages.finalize(status, "cancelled")
            return

        stages.set_stage(status, "extracting_audio", "extracting_audio", 0, 1)
        _, insights = await stages.do_analysis(
            status, deps, source_path, audio_path, chunks_dir
        )
        if status.status == "failed":
            return

        if stages.cancelled(job_id):
            stages.finalize(status, "cancelled")
            return

        stages.set_stage(status, "writing_manifest", "writing_manifest", 0, 1)
        if not await stages.write_manifest(
            status, deps, duration, size_bytes, insights=insights
        ):
            return

        _record_in_index(status, duration, size_bytes, insights_count=len(insights))
        stages.finalize(
            status,
            "done" if status.analysis_status == "ok" else "done_no_analysis",
        )

    finally:
        # B2 holds the durable artifacts; the local scratch dir is junk
        # once the manifest is written. Best-effort cleanup.
        shutil.rmtree(work_dir, ignore_errors=True)


__all__ = [
    "ASR_CHUNK_SECONDS",
    "PipelineDeps",
    "YtDlpError",
    "new_job",
    "run_job",
]
