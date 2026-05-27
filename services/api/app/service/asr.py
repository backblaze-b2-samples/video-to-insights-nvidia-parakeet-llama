"""NVIDIA Parakeet ASR client via NVIDIA Riva gRPC.

Calls the hosted Riva ASR service at grpc.nvcf.nvidia.com:443 with
function-id authentication. This is the canonical free-tier path for
nvidia/parakeet-tdt-0.6b-v2 — build.nvidia.com does NOT expose an
OpenAI-compatible REST endpoint for Parakeet.

The pipeline calls `transcribe_chunks(chunks)` -> dict with `segments`
and `text`. Per-chunk segment timestamps are shifted by the chunk's
`start_seconds` offset so the stitched transcript reads as if the
audio were processed in one pass.

The Protocol-typed `asr_service` parameter is a seam for tests and for
future provider swaps (Deepgram, AssemblyAI, OpenAI Whisper).
"""

from __future__ import annotations

import logging
import re
from typing import Any, Protocol

from app.config import settings

logger = logging.getLogger(__name__)

# Hosted parakeet-tdt-0.6b-v2 function-id on NVIDIA Cloud Functions.
# Verify against the "Try the API" panel at
# https://build.nvidia.com/nvidia/parakeet-tdt-0_6b-v2 if calls fail.
_PARAKEET_TDT_06B_V2_FUNCTION_ID = "d3fe9151-442b-4204-a70d-5fcc597fd610"
_RIVA_GRPC_URI = "grpc.nvcf.nvidia.com:443"


class AsrError(RuntimeError):
    """Raised when the ASR call cannot complete."""


class AsrService(Protocol):
    """Minimal Riva ASRService surface this module needs."""

    def offline_recognize(self, audio_bytes: bytes, config: Any) -> Any: ...


def _default_asr_service() -> AsrService:
    """Construct a real Riva ASRService bound to hosted Parakeet."""
    # Import locally so environments without the package (tests using a fake
    # service, the graceful-degradation path) don't fail at module import.
    import riva.client  # type: ignore[import-not-found]

    auth = riva.client.Auth(
        uri=_RIVA_GRPC_URI,
        use_ssl=True,
        metadata_args=[
            ["function-id", _PARAKEET_TDT_06B_V2_FUNCTION_ID],
            ["authorization", f"Bearer {settings.nvidia_api_key}"],
        ],
    )
    return riva.client.ASRService(auth)


def _default_config() -> Any:
    import riva.client  # type: ignore[import-not-found]

    return riva.client.RecognitionConfig(
        language_code="en-US",
        max_alternatives=1,
        enable_automatic_punctuation=True,
        enable_word_time_offsets=True,
    )


_SENTENCE_END = re.compile(r"[.!?]")


def _segments_from_words(words: list[Any]) -> list[dict[str, Any]]:
    """Group word-level results into sentence-bounded segments.

    Riva reports word-level timestamps in milliseconds. Downstream
    (insights extraction, manifest, frontend `Insight.start_seconds`)
    expects segments in seconds. We split on sentence-ending punctuation
    and collapse trailing un-punctuated words into a final segment.
    """
    if not words:
        return []

    segments: list[dict[str, Any]] = []
    buf_text: list[str] = []
    buf_start: float | None = None
    buf_end: float = 0.0

    for w in words:
        text = w.word
        start_s = w.start_time / 1000.0
        end_s = w.end_time / 1000.0
        if buf_start is None:
            buf_start = start_s
        buf_text.append(text)
        buf_end = end_s
        if _SENTENCE_END.search(text):
            segments.append(
                {"text": " ".join(buf_text).strip(), "start": buf_start, "end": buf_end}
            )
            buf_text = []
            buf_start = None

    if buf_text:
        segments.append(
            {"text": " ".join(buf_text).strip(), "start": buf_start or 0.0, "end": buf_end}
        )
    return segments


def transcribe_chunks(
    chunks: list[tuple[str, float]],
    *,
    asr_service: AsrService | None = None,
) -> dict[str, Any]:
    """Transcribe `chunks` and return the stitched payload.

    `chunks` is `[(audio_path, start_offset_seconds), ...]` from
    `ffmpeg_audio.chunk_audio`. We add the chunk start offset to every
    returned segment so the stitched timeline is monotonic.

    `asr_service` is exposed for tests and provider swaps — production
    callers leave it None and get the hosted Parakeet service.
    """
    if not settings.nvidia_api_key:
        raise AsrError("NVIDIA_API_KEY is not set")

    service = asr_service or _default_asr_service()
    config = _default_config()

    all_segments: list[dict[str, Any]] = []
    text_parts: list[str] = []

    for path, offset in chunks:
        with open(path, "rb") as f:
            audio = f.read()
        try:
            response = service.offline_recognize(audio, config)
        except AsrError:
            raise
        except Exception as e:
            # gRPC errors surface as RpcError / various transport exceptions.
            # Pipeline catches AsrError and marks analysis_status="failed_asr".
            raise AsrError(f"Riva ASR call failed: {e}") from e

        for result in response.results:
            if not result.alternatives:
                continue
            alt = result.alternatives[0]
            if alt.transcript:
                text_parts.append(alt.transcript)
            for seg in _segments_from_words(list(alt.words)):
                seg["start"] += offset
                seg["end"] += offset
                all_segments.append(seg)

    return {
        "text": " ".join(p.strip() for p in text_parts if p).strip(),
        "segments": all_segments,
        "model": settings.nvidia_asr_model,
    }
