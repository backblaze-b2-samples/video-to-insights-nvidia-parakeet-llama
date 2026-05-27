"""YouTube URL validation + thin yt-dlp wrapper.

The real subprocess call lives in `pipeline.py` (wrapped in
`asyncio.to_thread`) — this module is intentionally side-effect-free so
it stays trivial to unit-test without ffmpeg/yt-dlp on PATH.
"""

from urllib.parse import urlparse

from app.config import settings


class YouTubeValidationError(Exception):
    """Raised when the submitted URL fails pre-flight validation."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


def validate_url(raw: str) -> str:
    """Return a normalized URL or raise YouTubeValidationError.

    We allowlist hosts by suffix match against settings.allowed_hosts so
    `www.youtube.com`, `m.youtube.com`, and `youtu.be` all flow through
    one configurable entry. Scheme must be http/https.
    """
    if not raw or not raw.strip():
        raise YouTubeValidationError("invalid_url", "URL must not be empty")
    parsed = urlparse(raw.strip())
    if parsed.scheme not in ("http", "https"):
        raise YouTubeValidationError(
            "invalid_url", f"URL scheme must be http or https, got {parsed.scheme!r}"
        )
    host = (parsed.hostname or "").lower()
    if not host:
        raise YouTubeValidationError("invalid_url", "URL is missing a host")

    allowed = settings.allowed_hosts
    if not any(host == h or host.endswith("." + h) for h in allowed):
        raise YouTubeValidationError(
            "unsupported_host",
            f"Host {host!r} is not in ALLOWED_VIDEO_HOSTS",
        )
    return parsed.geturl()
