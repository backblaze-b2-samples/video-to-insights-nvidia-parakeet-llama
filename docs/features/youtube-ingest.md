# Feature: YouTube ingest

## Purpose

Accept a YouTube URL, validate it against an allowlist, then download the
source MP4 with `yt-dlp` so the pipeline can upload the same bytes to B2.

## Inputs

- `youtube_url` (string) — passed in the body of `POST /jobs`.
- `segment_seconds` (int, optional) — accepted for forward-compat; ignored.

## Validation

In `app/service/youtube.py::validate_url`:

- Scheme must be `http` or `https`.
- Host must match one of `ALLOWED_VIDEO_HOSTS` (comma-separated, suffix
  match so `m.youtube.com` and `www.youtube.com` are both fine).
- Empty input is rejected.

Reject codes:

| Cause | `error.code` | HTTP |
|---|---|---|
| Empty / non-URL / bad scheme | `invalid_url` | 422 |
| Host not in allowlist | `unsupported_host` | 422 |

## Download

`app/service/downloader.py::default_download` shells out through the API
Python interpreter, so `yt-dlp` must be installed in the backend
environment:

```
python -m yt_dlp --no-playlist --restrict-filenames \
                 -f "mp4/bestvideo*+bestaudio/best" \
                 --merge-output-format mp4 \
                 -o {WORK_DIR}/{video_id}/source.mp4 \
                 {URL}
```

The orchestrator in `app/service/pipeline.py` wraps every invocation in
`await asyncio.to_thread(...)` so the event loop stays responsive.

## Error taxonomy

| Condition | `error.code` |
|---|---|
| Private / sign-in-required | `yt_dlp_private_video` |
| Age-restricted | `yt_dlp_age_restricted` |
| Geo-blocked | `yt_dlp_geo_blocked` |
| Anything else from yt-dlp | `yt_dlp_failed` |
| Duration > `MAX_VIDEO_SECONDS` | `video_too_long` |
| yt-dlp missing from the API Python env | `yt_dlp_failed` (with hint) |
| `ffprobe` failure | `ffprobe_failed` |

Classification lives in `app/service/downloader.py::classify_yt_dlp_error`
— it pattern-matches against the lowercased stderr from yt-dlp. Add new
patterns there; do not classify at the call site.

## Tests

- `tests/test_youtube_validate.py` covers the allowlist, scheme check,
  and empty-input.
- `tests/test_pipeline.py::test_yt_dlp_error_classified_and_fails_fast`
  asserts that a raised `YtDlpError("yt_dlp_private_video", ...)` propagates
  unchanged into `JobStatus.error`.

## Legal

The sample is intended for content the user owns, content under permissive
licenses, or fair-use research. Respect YouTube's Terms of Service.
