"""HTTP surface for jobs: submit, poll, redirect to B2 artifacts, cancel.

The pipeline runs on the FastAPI event loop as an `asyncio.Task` guarded
by a lifespan-managed Semaphore (see main.py). State persists in
`work_dir/jobs/{job_id}.json` so a server restart leaves finished jobs
intact (in-flight jobs are abandoned — README documents the
single-worker constraint).
"""

import asyncio
import logging

from fastapi import APIRouter, HTTPException, Query, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from app.repo import b2_client, get_presigned_url, job_state
from app.service import jobs_index, youtube
from app.service.pipeline import new_job, run_job
from app.service.youtube import YouTubeValidationError
from app.types import JobIndexEntry, JobStatus, SubmitRequest, SubmitResponse


class JobsIndexPage(BaseModel):
    """List response — keeps the (rows, total) split for paginated UIs."""

    jobs: list[JobIndexEntry]
    total: int

logger = logging.getLogger(__name__)

router = APIRouter()


async def _run_under_semaphore(app, job_id: str) -> None:
    sem: asyncio.Semaphore = app.state.job_semaphore
    async with sem:
        await run_job(job_id)


@router.post("/jobs", response_model=SubmitResponse)
async def submit_job(request: Request, body: SubmitRequest):
    try:
        normalized = youtube.validate_url(body.youtube_url)
    except YouTubeValidationError as e:
        raise HTTPException(status_code=422, detail={"code": e.code, "message": e.message}) from None

    status = new_job(video_id=None, source_url=normalized)
    # Fire-and-forget; the task wrapper enforces concurrency via the
    # lifespan-managed semaphore. We don't await it.
    task = asyncio.create_task(_run_under_semaphore(request.app, status.job_id))
    request.app.state.background_tasks.add(task)
    task.add_done_callback(request.app.state.background_tasks.discard)
    logger.info("job_submitted job_id=%s url=%s", status.job_id, normalized)
    return SubmitResponse(job_id=status.job_id, status=status.status)


@router.get("/jobs", response_model=JobsIndexPage)
async def list_jobs_endpoint(
    limit: int = Query(default=50, ge=1, le=10000),
    offset: int = Query(default=0, ge=0),
):
    """Paginated jobs index — backs the dashboard's previous-videos table.

    Reads the denormalized index in B2 (one round trip) rather than
    fanning out across every manifest.
    """
    page, total = jobs_index.list_jobs(limit=limit, offset=offset)
    return JobsIndexPage(jobs=page, total=total)


# IMPORTANT: declare BEFORE `/jobs/{job_id}` so FastAPI doesn't route
# "latest" into the path parameter.
@router.get("/jobs/latest", response_model=JobIndexEntry | None)
async def latest_job_endpoint():
    return jobs_index.latest()


@router.get("/jobs/{job_id}", response_model=JobStatus)
async def get_job(job_id: str):
    status = job_state.read(job_id)
    if status is None:
        raise HTTPException(status_code=404, detail="job not found")
    return status


def _artifact_key(job_id: str, attr: str) -> str:
    status = job_state.read(job_id)
    if status is None:
        raise HTTPException(status_code=404, detail="job not found")
    key = getattr(status.result, attr)
    if not key:
        raise HTTPException(status_code=404, detail=f"{attr} not available yet")
    return key


def _redirect_to_artifact(job_id: str, attr: str) -> RedirectResponse:
    key = _artifact_key(job_id, attr)
    url = get_presigned_url(key, expires_in=3600)
    return RedirectResponse(url=url, status_code=302)


def _proxy_json_artifact(job_id: str, attr: str) -> Response:
    """Stream JSON artifact bytes inline rather than 302-ing to a presigned
    B2 URL. Avoids a cross-origin fetch from the browser (which would need
    a CORS rule on the bucket). The source video stays a redirect because
    <video> handles cross-origin media via range requests transparently
    and proxying 250+ MB through the API would be wasteful."""
    key = _artifact_key(job_id, attr)
    body = b2_client.get_bytes(key)
    if body is None:
        raise HTTPException(status_code=404, detail=f"{attr} not in B2")
    return Response(content=body, media_type="application/json")


@router.get("/jobs/{job_id}/source")
async def get_source(job_id: str):
    return _redirect_to_artifact(job_id, "source_key")


@router.get("/jobs/{job_id}/manifest")
async def get_manifest(job_id: str):
    return _proxy_json_artifact(job_id, "manifest_key")


@router.get("/jobs/{job_id}/transcript")
async def get_transcript(job_id: str):
    return _proxy_json_artifact(job_id, "transcript_key")


@router.get("/jobs/{job_id}/insights")
async def get_insights(job_id: str):
    return _proxy_json_artifact(job_id, "insights_key")


@router.delete("/jobs/{job_id}", response_model=JobStatus)
async def cancel_job(job_id: str):
    status = job_state.request_cancel(job_id)
    if status is None:
        raise HTTPException(status_code=404, detail="job not found")
    return status
