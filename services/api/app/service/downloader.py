"""yt-dlp downloader + error classification.

Kept separate from `pipeline.py` so the orchestrator file stays small
and so a swap-in alternative (e.g. a stub for offline tests) can be a
single-line change to `PipelineDeps.download_video`.
"""

import subprocess
import sys
from typing import Any


class YtDlpError(RuntimeError):
    """Raised by the default downloader on a non-zero exit code."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


YTDLP_MISSING_HINT = (
    "yt-dlp is not installed in the API Python environment. "
    "Run `cd services/api && .venv/bin/pip install -r requirements.txt`."
)


def classify_yt_dlp_error(stderr_lower: str) -> str:
    """Map yt-dlp's stderr to a stable error code the README documents."""
    if "private" in stderr_lower or "sign in to confirm" in stderr_lower:
        return "yt_dlp_private_video"
    if "age" in stderr_lower and "restrict" in stderr_lower:
        return "yt_dlp_age_restricted"
    if "geo" in stderr_lower or "not available in your country" in stderr_lower:
        return "yt_dlp_geo_blocked"
    return "yt_dlp_failed"


def _yt_dlp_failure_message(stderr: str) -> str:
    if "no module named" in stderr.lower() and "yt_dlp" in stderr.lower():
        return YTDLP_MISSING_HINT
    return stderr.splitlines()[-1] if stderr else "yt-dlp exited non-zero"


def default_download(url: str, out_path: str) -> dict[str, Any]:
    """Shell out to yt-dlp and write the merged MP4 to `out_path`.

    Raises `YtDlpError` on non-zero exit. The pipeline wraps the call in
    `asyncio.to_thread` so this blocking call doesn't reach the event loop.
    """
    # Invoke yt-dlp as a Python module rather than a PATH binary so the
    # call works whether or not the venv's bin/ is on PATH — the canonical
    # foot-gun when uvicorn is launched as `.venv/bin/uvicorn` without an
    # `activate` step.
    cmd = [
        sys.executable, "-m", "yt_dlp",
        "--no-playlist",
        "--restrict-filenames",
        "-f", "mp4/bestvideo*+bestaudio/best",
        "--merge-output-format", "mp4",
        "-o", out_path,
        url,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        msg = _yt_dlp_failure_message(stderr)
        raise YtDlpError(classify_yt_dlp_error(stderr.lower()), msg)
    return {"path": out_path}
