"""ASR client wiring + chunk offset stitching.

We don't talk to real Riva here. We inject a fake `AsrService` that
returns a canned Riva-shaped response and verify the timestamp-shift
math + word-to-segment grouping.
"""

import os
import tempfile

import pytest

from app.service import asr as asr_module

# --- Fakes that mirror Riva's response surface --------------------------------
# Only the attributes asr.py reads from the response are modeled.


class _Word:
    def __init__(self, word: str, start_ms: int, end_ms: int):
        self.word = word
        self.start_time = start_ms  # Riva: milliseconds
        self.end_time = end_ms


class _Alt:
    def __init__(self, transcript: str, words: list[_Word]):
        self.transcript = transcript
        self.words = words


class _Result:
    def __init__(self, alternatives: list[_Alt]):
        self.alternatives = alternatives


class _Response:
    def __init__(self, results: list[_Result]):
        self.results = results


def _canned_response() -> _Response:
    """Two sentences spanning 0.0 to 2.5s of audio (in 'chunk-local' time)."""
    return _Response(
        results=[
            _Result(
                alternatives=[
                    _Alt(
                        transcript="Hello world. This is a test.",
                        words=[
                            _Word("Hello", 0, 500),
                            _Word("world.", 600, 1200),
                            _Word("This", 1400, 1700),
                            _Word("is", 1800, 1900),
                            _Word("a", 2000, 2100),
                            _Word("test.", 2200, 2500),
                        ],
                    )
                ]
            )
        ]
    )


class FakeAsrService:
    """Stand-in for `riva.client.ASRService`."""

    def __init__(self, response: _Response, *, raise_exc: Exception | None = None):
        self._response = response
        self._raise = raise_exc

    def offline_recognize(self, audio_bytes: bytes, config) -> _Response:
        if self._raise is not None:
            raise self._raise
        return self._response


# --- Test helpers -------------------------------------------------------------


def _tiny_wav(path: str) -> None:
    # 44-byte WAV header is enough — we never actually decode it in tests.
    with open(path, "wb") as f:
        f.write(b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00")
        f.write(b"\x40\x1f\x00\x00\x80\x3e\x00\x00\x02\x00\x10\x00data\x00\x00\x00\x00")


# --- Tests --------------------------------------------------------------------


def test_transcribe_single_chunk_no_offset(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "nvidia_api_key", "test-token")

    with tempfile.TemporaryDirectory() as d:
        wav = os.path.join(d, "a.wav")
        _tiny_wav(wav)
        result = asr_module.transcribe_chunks(
            [(wav, 0.0)], asr_service=FakeAsrService(_canned_response())
        )

    assert result["text"]
    # Two sentence-bounded segments from one canned response.
    assert len(result["segments"]) == 2
    assert result["segments"][0]["start"] == 0.0
    assert result["segments"][0]["end"] == pytest.approx(1.2)
    assert result["segments"][1]["start"] == pytest.approx(1.4)
    assert result["segments"][1]["end"] == pytest.approx(2.5)


def test_transcribe_multiple_chunks_offsets_applied(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "nvidia_api_key", "test-token")

    with tempfile.TemporaryDirectory() as d:
        a = os.path.join(d, "a.wav")
        b = os.path.join(d, "b.wav")
        _tiny_wav(a)
        _tiny_wav(b)
        # Second chunk starts at 100s — every returned segment must be shifted.
        result = asr_module.transcribe_chunks(
            [(a, 0.0), (b, 100.0)],
            asr_service=FakeAsrService(_canned_response()),
        )

    assert len(result["segments"]) == 4
    # Sanity: original CANNED has end=2.5; chunk-2 segment ends should be 102.5.
    last = result["segments"][-1]
    assert last["start"] == pytest.approx(101.4)
    assert last["end"] == pytest.approx(102.5)


def test_transcribe_raises_without_api_key(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "nvidia_api_key", "")
    with pytest.raises(asr_module.AsrError):
        asr_module.transcribe_chunks([("/tmp/x.wav", 0.0)])


def test_transcribe_wraps_riva_errors_as_asrerror(monkeypatch):
    """gRPC failures should surface as AsrError so the pipeline can mark
    analysis_status=failed_asr rather than crashing the whole job."""
    from app.config import settings

    monkeypatch.setattr(settings, "nvidia_api_key", "test-token")

    class _RpcLikeError(Exception):
        pass

    with tempfile.TemporaryDirectory() as d:
        wav = os.path.join(d, "a.wav")
        _tiny_wav(wav)
        with pytest.raises(asr_module.AsrError):
            asr_module.transcribe_chunks(
                [(wav, 0.0)],
                asr_service=FakeAsrService(
                    _canned_response(), raise_exc=_RpcLikeError("network down")
                ),
            )


def test_segments_from_words_handles_trailing_unpunctuated():
    """If the last word has no sentence-end punctuation, the trailing
    buffer must still be flushed into a final segment."""
    words = [
        _Word("hello", 0, 500),
        _Word("there", 600, 1200),  # no terminal punctuation
    ]
    segs = asr_module._segments_from_words(words)
    assert len(segs) == 1
    assert segs[0]["text"] == "hello there"
    assert segs[0]["start"] == 0.0
    assert segs[0]["end"] == pytest.approx(1.2)
