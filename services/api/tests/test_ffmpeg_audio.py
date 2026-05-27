"""ffmpeg integration tests — skipped when ffmpeg/ffprobe are missing.

These exercise the real subprocess paths because the failure modes
(wrong codec args, missing -f, etc.) are not testable with fakes.
"""

import os
import shutil
import subprocess
import tempfile

import pytest

from app.service import ffmpeg_audio

FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")
needs_ffmpeg = pytest.mark.skipif(
    not (FFMPEG and FFPROBE), reason="ffmpeg/ffprobe not installed"
)


def _make_test_video(path: str, seconds: int = 4) -> None:
    """Generate a tiny test clip via lavfi (audio + video, sparse keyframes)."""
    cmd = [
        "ffmpeg",
        "-y",
        "-f", "lavfi", "-i", f"testsrc=duration={seconds}:size=128x96:rate=15",
        "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}",
        "-g", "30", "-keyint_min", "30", "-sc_threshold", "0",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
        path,
    ]
    result = subprocess.run(cmd, capture_output=True, check=False)
    if result.returncode != 0:
        pytest.skip(f"ffmpeg failed to build fixture: {result.stderr[-200:]!r}")


@needs_ffmpeg
def test_probe_duration_returns_seconds():
    with tempfile.TemporaryDirectory() as d:
        video = os.path.join(d, "v.mp4")
        _make_test_video(video, seconds=3)
        dur = ffmpeg_audio.probe_duration(video)
    assert 2.5 <= dur <= 4.0


@needs_ffmpeg
def test_extract_audio_writes_wav():
    with tempfile.TemporaryDirectory() as d:
        video = os.path.join(d, "v.mp4")
        audio = os.path.join(d, "v.wav")
        _make_test_video(video, seconds=3)
        ffmpeg_audio.extract_audio(video, audio)
        assert os.path.getsize(audio) > 0


@needs_ffmpeg
def test_chunk_audio_skips_if_under_chunk_size():
    """A short clip returns a single-item list with the same path + offset 0."""
    with tempfile.TemporaryDirectory() as d:
        video = os.path.join(d, "v.mp4")
        audio = os.path.join(d, "v.wav")
        _make_test_video(video, seconds=3)
        ffmpeg_audio.extract_audio(video, audio)
        chunks = ffmpeg_audio.chunk_audio(audio, os.path.join(d, "chunks"), chunk_seconds=60)
    assert chunks == [(audio, 0.0)]
