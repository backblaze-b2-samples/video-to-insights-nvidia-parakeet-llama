"""JobStatus + supporting models used across the pipeline.

The shape is the single source of truth for what the frontend polls; the
TypeScript mirror lives in packages/shared/src/types.ts.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

JobStatusValue = Literal[
    "queued",
    "downloading",
    "uploading_source",
    "extracting_audio",
    "transcribing",
    "generating_insights",
    "writing_manifest",
    "done",
    "done_no_analysis",
    "failed",
    "cancelled",
]

AnalysisStatus = Literal[
    "pending",
    "ok",
    "skipped_no_api_key",
    "failed_asr",
    "failed_insights",
]


class JobProgress(BaseModel):
    stage: str
    current: int = 0
    total: int = 1


class JobResult(BaseModel):
    source_key: str | None = None
    transcript_key: str | None = None
    insights_key: str | None = None
    manifest_key: str | None = None


class JobError(BaseModel):
    code: str
    message: str


class JobStatus(BaseModel):
    job_id: str
    video_id: str
    source_url: str
    status: JobStatusValue = "queued"
    analysis_status: AnalysisStatus = "pending"
    analysis_message: str | None = None
    progress: JobProgress = Field(default_factory=lambda: JobProgress(stage="queued"))
    result: JobResult = Field(default_factory=JobResult)
    error: JobError | None = None
    created_at: datetime
    updated_at: datetime
    cancel_requested: bool = False


class SubmitRequest(BaseModel):
    youtube_url: str
    # Forward-compat — currently unused (no clip slicing in MVP). README
    # documents this so callers know not to depend on it yet.
    segment_seconds: int | None = None


class SubmitResponse(BaseModel):
    job_id: str
    status: JobStatusValue
