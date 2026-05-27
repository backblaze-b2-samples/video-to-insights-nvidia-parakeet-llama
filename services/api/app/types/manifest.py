"""Manifest v1 — schema-versioned summary of one processed video.

The manifest is written to B2 at the end of the pipeline and is the document
the frontend (or downstream consumers) reads to render a finished result.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

ManifestAnalysisStatus = Literal[
    "ok",
    "skipped_no_api_key",
    "failed_asr",
    "failed_insights",
]


class Insight(BaseModel):
    index: int
    title: str
    summary: str
    start_seconds: float
    end_seconds: float
    key_quotes: list[str] = []


class ManifestSource(BaseModel):
    b2_key: str
    duration_seconds: float | None = None
    size_bytes: int | None = None


class ManifestModels(BaseModel):
    asr: str
    insights: str


class ManifestV1(BaseModel):
    schema_version: Literal[1] = 1
    video_id: str
    source_url: str
    source: ManifestSource
    analysis_status: ManifestAnalysisStatus
    transcript_key: str | None = None
    insights: list[Insight] = []
    insights_key: str | None = None
    models: ManifestModels
    bucket: str
    region: str
    created_at: datetime
