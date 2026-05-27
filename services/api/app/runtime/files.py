"""Read-only file browser for the `video-to-insights-pipeline/` prefix.

Same response shape as the starter kit's `/files` so the lifted
FileBrowser component plugs straight in. Scope is tight on purpose:

- The prefix is HARDCODED. Callers cannot list anything else in the
  bucket — the sample's job artifacts are the only things we want
  surfaced through this UI.
- No delete endpoint. The pipeline owns object lifecycle; the dashboard
  is read-only.
"""

import logging
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel

from app.repo import b2_client, get_presigned_url

logger = logging.getLogger(__name__)

# Single source of truth — matches stages.PIPELINE_PREFIX. Kept as a
# module constant rather than imported because runtime/ must not depend
# on service/ (layer ordering).
FILES_PREFIX = "video-to-insights-pipeline/"

FileKind = Literal["source", "transcript", "insights", "manifest", "jobs_index", "other"]


def _derive_kind(key: str) -> FileKind:
    """Classify an object key by its trailing filename.

    Drives icon + preview behavior in the frontend so we don't have to
    re-parse the key in JS. `kind` is a closed enum on purpose — adding
    a new artifact type should be a deliberate, typed change.
    """
    if key == "video-to-insights-pipeline/jobs-index.json":
        return "jobs_index"
    if key.endswith("/source.mp4"):
        return "source"
    if key.endswith("/transcript.json"):
        return "transcript"
    if key.endswith("/insights.json"):
        return "insights"
    if key.endswith("/manifest.json"):
        return "manifest"
    return "other"


class FileObject(BaseModel):
    key: str
    size: int
    last_modified: str | None = None
    etag: str
    kind: FileKind


class FilesPage(BaseModel):
    objects: list[FileObject]
    next_token: str | None = None


router = APIRouter()


@router.get("/files", response_model=FilesPage)
async def list_files(
    continuation_token: str | None = Query(default=None),
    max_keys: int = Query(default=100, ge=1, le=1000),
):
    """Paginated listing of `video-to-insights-pipeline/` objects."""
    try:
        result = b2_client.list_objects(
            prefix=FILES_PREFIX,
            max_keys=max_keys,
            continuation_token=continuation_token,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e)) from None

    objects = [
        FileObject(
            key=obj["key"],
            size=obj["size"],
            last_modified=obj["last_modified"],
            etag=obj["etag"],
            kind=_derive_kind(obj["key"]),
        )
        for obj in result["objects"]
    ]
    return FilesPage(objects=objects, next_token=result["next_token"])


@router.get("/files/preview")
async def preview_file(key: str = Query(...)):
    """Mint a presigned GET for a single object in our prefix.

    The hardcoded prefix check prevents this endpoint from being used as
    a generic presigner for arbitrary keys in the bucket. Use this for
    video/binary previews — for JSON content the browser would block the
    cross-origin fetch, so use `/files/content` instead.
    """
    if not key.startswith(FILES_PREFIX):
        raise HTTPException(status_code=400, detail="key outside allowed prefix")
    try:
        url = get_presigned_url(key, expires_in=3600)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e)) from None
    return {"url": url}


@router.get("/files/content")
async def file_content(key: str = Query(...)):
    """Stream a JSON object's bytes inline through the API.

    Same prefix lock as `/files/preview`. JSON-only — we proxy through the
    API so the browser doesn't make a cross-origin fetch to B2 (which
    would require a CORS rule on the bucket). For video, use
    `/files/preview` to mint a presigned URL — `<video>` handles
    cross-origin media transparently via range requests.
    """
    if not key.startswith(FILES_PREFIX):
        raise HTTPException(status_code=400, detail="key outside allowed prefix")
    if not key.endswith(".json"):
        raise HTTPException(
            status_code=415,
            detail="content endpoint serves JSON only; use /files/preview for other types",
        )
    try:
        body = b2_client.get_bytes(key)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e)) from None
    if body is None:
        raise HTTPException(status_code=404, detail="object not found")
    return Response(content=body, media_type="application/json")
