from fastapi import APIRouter

from app.config import settings
from app.repo import check_connectivity

router = APIRouter()


@router.get("/health")
async def health():
    """Top-level health probe.

    `b2_connected` exercises the configured creds against `head_bucket`.
    `nvidia_configured` is a soft signal — graceful degradation means
    the app is still healthy without it, but the frontend uses this
    flag to set expectations.
    """
    b2_ok = check_connectivity()
    return {
        "status": "healthy" if b2_ok else "degraded",
        "b2_connected": b2_ok,
        "nvidia_configured": bool(settings.nvidia_api_key),
    }
