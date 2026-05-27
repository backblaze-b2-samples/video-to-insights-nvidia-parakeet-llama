"""B2 (S3-compatible) repo layer. boto3 is only imported here.

Per parent sampleapps/CLAUDE.md every S3 client carries the
`video-to-insights-pipeline/0.1.0 (backblaze-b2-samples)` identity so B2
support can see this sample in their request logs.
"""

import functools
import io
import json
import logging

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.config import settings

APP_SLUG = "video-to-insights-pipeline"
APP_VERSION = "0.1.0"
USER_AGENT_EXTRA = f"{APP_SLUG}/{APP_VERSION} (backblaze-b2-samples)"

logger = logging.getLogger(__name__)


@functools.lru_cache(maxsize=1)
def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.b2_endpoint,
        region_name=settings.b2_region or None,
        aws_access_key_id=settings.b2_key_id,
        aws_secret_access_key=settings.b2_application_key,
        config=Config(
            signature_version="s3v4",
            user_agent_extra=USER_AGENT_EXTRA,
        ),
    )


def check_connectivity() -> bool:
    try:
        client = get_s3_client()
        client.head_bucket(Bucket=settings.b2_bucket_name)
        return True
    except Exception:
        return False


def object_exists(key: str) -> bool:
    """Idempotency helper — used before re-downloading a video."""
    client = get_s3_client()
    try:
        client.head_object(Bucket=settings.b2_bucket_name, Key=key)
        return True
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        if code in ("404", "NoSuchKey", "NotFound"):
            return False
        raise


def list_objects(
    prefix: str, max_keys: int = 100, continuation_token: str | None = None
) -> dict:
    """Wrap s3.list_objects_v2 with a paginated, JSON-friendly shape.

    Returns `{'objects': [...], 'next_token': str|None}`. Each object is a
    dict (not a Pydantic model — the runtime layer owns the API schema):
    `{'key', 'size', 'last_modified' (isoformat), 'etag'}`.
    """
    client = get_s3_client()
    params: dict = {
        "Bucket": settings.b2_bucket_name,
        "Prefix": prefix,
        "MaxKeys": max_keys,
    }
    if continuation_token:
        params["ContinuationToken"] = continuation_token
    try:
        response = client.list_objects_v2(**params)
    except ClientError as e:
        raise RuntimeError(f"B2 list failed for prefix '{prefix}': {e}") from e
    objects = []
    for obj in response.get("Contents", []):
        last_modified = obj.get("LastModified")
        objects.append({
            "key": obj["Key"],
            "size": obj["Size"],
            "last_modified": last_modified.isoformat() if last_modified else None,
            "etag": obj.get("ETag", "").strip('"'),
        })
    next_token = response.get("NextContinuationToken") if response.get("IsTruncated") else None
    return {"objects": objects, "next_token": next_token}


def get_bytes(key: str) -> bytes | None:
    """Wrap s3.get_object. Returns None on NoSuchKey, raises otherwise.

    Used to read the jobs-index sidecar object from B2 without leaking
    boto3 exceptions into the service layer.
    """
    client = get_s3_client()
    try:
        response = client.get_object(Bucket=settings.b2_bucket_name, Key=key)
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        if code in ("404", "NoSuchKey", "NotFound"):
            return None
        raise
    return response["Body"].read()


def put_bytes(key: str, data: bytes, content_type: str) -> None:
    """Upload an in-memory blob (small artifacts: transcript / insights / manifest)."""
    client = get_s3_client()
    try:
        client.put_object(
            Bucket=settings.b2_bucket_name,
            Key=key,
            Body=io.BytesIO(data),
            ContentType=content_type,
        )
    except ClientError as e:
        raise RuntimeError(f"B2 upload failed for '{key}': {e}") from e


def put_json(key: str, payload: dict) -> None:
    """Convenience wrapper for JSON artifacts."""
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    put_bytes(key, body, "application/json")


def put_file(key: str, file_path: str, content_type: str) -> int:
    """Stream a local file to B2 via upload_file (handles multipart for large objects).

    Returns the file size in bytes.
    """
    import os

    client = get_s3_client()
    try:
        client.upload_file(
            Filename=file_path,
            Bucket=settings.b2_bucket_name,
            Key=key,
            ExtraArgs={"ContentType": content_type},
        )
    except ClientError as e:
        raise RuntimeError(f"B2 upload failed for '{key}': {e}") from e
    return os.path.getsize(file_path)


def get_presigned_url(key: str, expires_in: int = 3600) -> str:
    """Mint a short-lived presigned GET URL.

    Used by the runtime layer to 302 the browser straight at B2 for video
    playback and JSON-artifact fetches. State stores raw keys; URLs are
    minted on demand so they never go stale in the state file.
    """
    client = get_s3_client()
    try:
        return client.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.b2_bucket_name, "Key": key},
            ExpiresIn=expires_in,
        )
    except ClientError as e:
        raise RuntimeError(f"B2 presign failed for '{key}': {e}") from e
