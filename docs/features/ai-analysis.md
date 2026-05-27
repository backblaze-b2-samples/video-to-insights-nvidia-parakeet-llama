# Feature: AI analysis (ASR + Insights)

The pipeline asks two NVIDIA-hosted models, in order:

1. **`nvidia/parakeet-tdt-0.6b-v2`** — transcribes audio with segment-level
   timestamps.
2. **`meta/llama-3.3-70b-instruct`** — extracts 3-6 topical sections from
   the transcript and aligns them to the original timeline.

Both are on NVIDIA's free NIM tier (~40 req/min, ~1000 starting credits).

## Audio prep

`app/service/ffmpeg_audio.py` extracts mono 16kHz WAV with `ffmpeg`:

```
ffmpeg -y -i source.mp4 -vn -ac 1 -ar 16000 -f wav audio.wav
```

Parakeet's hosted endpoint accepts ~24min per request. We chunk a little
under that (`ASR_CHUNK_SECONDS = 22 * 60`) using `ffmpeg -f segment` so
a slow ramp doesn't trip the boundary.

`chunk_audio` returns `[(chunk_path, start_offset_seconds), ...]`. For
files shorter than the chunk size it short-circuits and returns the
original audio with offset `0.0`, avoiding an unnecessary re-encode.

## ASR call

`app/service/asr.py::transcribe_chunks` posts each chunk to
`/audio/transcriptions` with the configured `nvidia_asr_model`. Each
returned segment has its `start`/`end` shifted by the chunk's start
offset so the stitched timeline reads as if the audio were processed in
one pass.

A `transport=` parameter accepts an `httpx.BaseTransport` — tests inject
`httpx.MockTransport` to return canned responses without hitting the
network.

Failure modes:
- Missing `NVIDIA_API_KEY` → `AsrError`. The pipeline catches this and
  records `analysis_status: "failed_asr"`.
- HTTP 4xx/5xx → `AsrError` with the status code and a truncated body.
  Pipeline catches it the same way.

## Insights call

`app/service/insights.py::extract_insights` calls
`/chat/completions` (OpenAI-compatible) with `response_format: json_object`.
The system prompt asks the model to return:

```json
{
  "insights": [
    { "title": "...", "summary": "...",
      "start_seconds": 0.0, "end_seconds": 30.0,
      "key_quotes": ["...", "..."] }
  ]
}
```

The client validates each item into a Pydantic `Insight`; items that
fail validation are dropped with a warning rather than failing the whole
call.

## Graceful degradation

This is the load-bearing UX guarantee — and a tested invariant.

If `NVIDIA_API_KEY` is empty when `run_job` reaches the analysis phase,
the pipeline:

1. Sets `analysis_status = "skipped_no_api_key"`.
2. Writes a manifest pointing at the source only (no transcript, no insights).
3. Marks the final status as `done_no_analysis`.
4. Returns normally so the frontend renders the player.

The same path triggers on ASR or insights failure, with
`analysis_status` set to `failed_asr` / `failed_insights` respectively.

Tests:
- `tests/test_pipeline.py::test_no_api_key_falls_back_to_done_no_analysis`
- `tests/test_pipeline.py::test_asr_failure_keeps_source_only`
- `tests/test_pipeline.py::test_insights_failure_keeps_transcript`

## Provider seam

`PipelineDeps` exposes `transcribe` and `extract_insights` as plain
callables. A future OpenAI / Anthropic / other-provider variant slots
into the same shape; `pipeline.py` doesn't change.
