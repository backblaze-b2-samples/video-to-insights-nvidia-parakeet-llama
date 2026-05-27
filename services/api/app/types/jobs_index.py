"""Jobs-index schema — denormalized summary of every successful job.

Persisted as a single B2 object so the dashboard renders in one
round-trip instead of N manifest GETs. The mirror TS type lives in
`packages/shared/src/types.ts`; keep them in lockstep.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.types.manifest import ManifestAnalysisStatus


class JobIndexEntry(BaseModel):
    video_id: str
    job_id: str
    source_url: str
    duration_seconds: float | None = None
    size_bytes: int | None = None
    insights_count: int = 0
    analysis_status: ManifestAnalysisStatus
    created_at: datetime
    manifest_key: str
    source_key: str


class JobsIndex(BaseModel):
    schema_version: Literal[1] = 1
    updated_at: datetime
    jobs: list[JobIndexEntry] = Field(default_factory=list)
