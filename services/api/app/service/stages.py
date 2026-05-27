"""Per-stage helpers for the pipeline orchestrator.

Split out of `pipeline.py` to keep that file under the 300-line cap and
to make each stage independently readable. The orchestrator owns the
top-level cancel/finalize sequencing; this module owns the "what does
each step do" detail.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from app.config import settings
from app.repo import job_state
from app.service import ffmpeg_audio
from app.types import (
    Insight,
    JobError,
    JobProgress,
    JobStatus,
    JobStatusValue,
    ManifestModels,
    ManifestSource,
    ManifestV1,
)

if TYPE_CHECKING:
    from app.service.pipeline import PipelineDeps

logger = logging.getLogger(__name__)

PIPELINE_PREFIX = "video-to-insights-pipeline"
# Parakeet's hosted endpoint accepts ~24min of audio per call.
ASR_CHUNK_SECONDS = 22 * 60


def now() -> datetime:
    return datetime.now(UTC)


def key(video_id: str, name: str) -> str:
    return f"{PIPELINE_PREFIX}/{video_id}/{name}"


def set_stage(status: JobStatus, new_status: JobStatusValue, stage: str, current: int, total: int) -> None:
    status.status = new_status
    status.progress = JobProgress(stage=stage, current=current, total=total)
    job_state.write(status)


def fail(status: JobStatus, code: str, message: str) -> None:
    status.status = "failed"
    status.error = JobError(code=code, message=message)
    job_state.write(status)


def finalize(status: JobStatus, final: JobStatusValue) -> None:
    status.status = final
    job_state.write(status)


def cancelled(job_id: str) -> bool:
    s = job_state.read(job_id)
    return bool(s and s.cancel_requested)


async def write_manifest(
    status: JobStatus,
    deps: PipelineDeps,
    duration: float,
    size_bytes: int,
    insights: list[Insight],
) -> bool:
    """Build, upload, and record the manifest. Returns True on success."""
    analysis = status.analysis_status
    final_analysis = "ok" if analysis == "pending" else analysis

    manifest = ManifestV1(
        video_id=status.video_id,
        source_url=status.source_url,
        source=ManifestSource(
            b2_key=status.result.source_key or "",
            duration_seconds=duration,
            size_bytes=size_bytes,
        ),
        analysis_status=final_analysis,  # type: ignore[arg-type]
        transcript_key=status.result.transcript_key,
        insights=insights,
        insights_key=status.result.insights_key,
        models=ManifestModels(
            asr=settings.nvidia_asr_model,
            insights=settings.nvidia_insights_model,
        ),
        bucket=settings.b2_bucket_name,
        region=settings.b2_region,
        created_at=now(),
    )
    manifest_key = key(status.video_id, "manifest.json")
    payload = json.loads(manifest.model_dump_json())
    try:
        await asyncio.to_thread(deps.put_json_to_b2, manifest_key, payload)
    except RuntimeError as e:
        fail(status, "b2_upload_failed", f"manifest upload failed: {e}")
        return False
    status.result.manifest_key = manifest_key
    job_state.write(status)
    return True


async def do_analysis(
    status: JobStatus,
    deps: PipelineDeps,
    source_path: str,
    audio_path: str,
    chunks_dir: str,
) -> tuple[dict[str, Any] | None, list[Insight]]:
    """Run audio extract + ASR + insights.

    Any failure path sets `status.analysis_status` and returns partial
    data; the caller still writes the manifest and finalizes the job.
    """
    try:
        await asyncio.to_thread(deps.extract_audio, source_path, audio_path)
        chunks = await asyncio.to_thread(
            deps.chunk_audio, audio_path, chunks_dir, ASR_CHUNK_SECONDS
        )
    except ffmpeg_audio.FfmpegError as e:
        status.analysis_status = "failed_asr"
        status.analysis_message = f"audio extraction failed: {e}"
        return None, []

    if cancelled(status.job_id):
        return None, []

    set_stage(status, "transcribing", "transcribing", 0, len(chunks))
    try:
        transcript = await asyncio.to_thread(deps.transcribe, chunks)
    except Exception as e:
        logger.warning("ASR failed for %s: %s", status.job_id, e)
        status.analysis_status = "failed_asr"
        status.analysis_message = f"transcription failed: {e}"
        return None, []

    transcript_key = key(status.video_id, "transcript.json")
    try:
        await asyncio.to_thread(deps.put_json_to_b2, transcript_key, transcript)
    except RuntimeError as e:
        fail(status, "b2_upload_failed", f"transcript upload failed: {e}")
        return transcript, []
    status.result.transcript_key = transcript_key
    job_state.write(status)

    if cancelled(status.job_id):
        return transcript, []

    set_stage(status, "generating_insights", "generating_insights", 0, 1)
    try:
        insights = await asyncio.to_thread(deps.extract_insights, transcript)
    except Exception as e:
        logger.warning("Insights failed for %s: %s", status.job_id, e)
        status.analysis_status = "failed_insights"
        status.analysis_message = f"insights generation failed: {e}"
        return transcript, []

    insights_key = key(status.video_id, "insights.json")
    try:
        await asyncio.to_thread(
            deps.put_json_to_b2,
            insights_key,
            {"insights": [i.model_dump(mode="json") for i in insights]},
        )
    except RuntimeError as e:
        fail(status, "b2_upload_failed", f"insights upload failed: {e}")
        return transcript, insights
    status.result.insights_key = insights_key
    status.analysis_status = "ok"
    job_state.write(status)
    return transcript, insights
