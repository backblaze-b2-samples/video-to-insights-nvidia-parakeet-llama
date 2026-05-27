"""Audio extraction + chunking helpers used by the pipeline.

Two public callables:

* `extract_audio(video_path, audio_path)` — single ffmpeg invocation
  that writes a mono 16kHz WAV next to the source. We pick WAV because
  Parakeet's hosted endpoint accepts it directly and we don't want to
  pull in pydub.

* `chunk_audio(audio_path, out_dir, chunk_seconds)` — splits long audio
  into `chunk_seconds`-sized pieces using `ffmpeg -f segment`. Returns
  the list of `(chunk_path, start_seconds)` pairs in temporal order so
  the ASR client can offset each segment's timestamps when stitching.

The actual subprocess calls happen here, but the pipeline wraps every
call to these functions in `asyncio.to_thread(...)` so they never block
the event loop.
"""

import os
import subprocess
from pathlib import Path


class FfmpegError(RuntimeError):
    """Raised when an ffmpeg/ffprobe invocation fails."""


def probe_duration(video_path: str) -> float:
    """Return the source's duration in seconds via ffprobe."""
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        video_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise FfmpegError(f"ffprobe failed: {result.stderr.strip()}")
    try:
        return float(result.stdout.strip())
    except ValueError as e:
        raise FfmpegError(f"ffprobe produced non-numeric duration: {result.stdout!r}") from e


def extract_audio(video_path: str, audio_path: str) -> None:
    """Extract mono 16kHz WAV from `video_path` into `audio_path`."""
    cmd = [
        "ffmpeg",
        "-y",                         # overwrite
        "-i", video_path,
        "-vn",                        # no video stream
        "-ac", "1",                   # mono
        "-ar", "16000",               # 16kHz — Parakeet input rate
        "-f", "wav",
        audio_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise FfmpegError(f"ffmpeg audio extract failed: {result.stderr.strip()[-400:]}")


def chunk_audio(
    audio_path: str, out_dir: str, chunk_seconds: int
) -> list[tuple[str, float]]:
    """Split `audio_path` into ~chunk_seconds chunks under `out_dir`.

    Returns the chunk paths paired with their start-offset in seconds,
    sorted by time. Falls back to `[(audio_path, 0.0)]` when the audio
    is shorter than `chunk_seconds` (avoids a useless re-encode).
    """
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    total = probe_duration(audio_path)
    if total <= chunk_seconds:
        return [(audio_path, 0.0)]

    pattern = os.path.join(out_dir, "chunk_%04d.wav")
    cmd = [
        "ffmpeg",
        "-y",
        "-i", audio_path,
        "-f", "segment",
        "-segment_time", str(chunk_seconds),
        "-c", "copy",
        pattern,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise FfmpegError(f"ffmpeg segment failed: {result.stderr.strip()[-400:]}")

    chunks = sorted(Path(out_dir).glob("chunk_*.wav"))
    return [(str(p), i * float(chunk_seconds)) for i, p in enumerate(chunks)]
