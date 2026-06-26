# Code Review Rules

This file collects the project-specific review rules the structural tests
and lints don't (yet) catch. Reviewers should run this list against
every PR.

## Hard rules (blocker)

1. **No `subprocess.run` outside `app/service/downloader.py` and
   `app/service/ffmpeg_audio.py`.** Tests should fake the subprocess
   path via dependency injection on `PipelineDeps`.
2. **Every `subprocess.run` for yt-dlp / ffmpeg / ffprobe must be wrapped
   in `await asyncio.to_thread(...)` at the call site in
   `app/service/pipeline.py`.** Direct calls on the event loop block every
   other request.
3. **No `boto3` or `botocore` imports outside `app/repo/`.** Enforced by
   `tests/test_structure.py::test_boto3_only_in_repo` — if the test is
   green, this rule is satisfied.
4. **No new env-var aliases.** The keys are `B2_APPLICATION_KEY_ID`,
   `B2_APPLICATION_KEY`, `B2_BUCKET_NAME`, `B2_REGION`, and optional
   `B2_PUBLIC_URL_BASE` per the current B2 sample standard. Do not add
   provider-specific aliases or rename these per sample. The temporary
   `B2_KEY_ID` fallback is tracked for removal after 2026-07-31 in
   `docs/exec-plans/tech-debt-tracker.md`.
5. **Custom S3 user-agent string is fixed.**
   `user_agent_extra = "video-to-insights-pipeline/0.1.0 (backblaze-b2-samples)"`
   in `app/repo/b2_client.py`. Don't change the slug.
6. **State writes go through `app/repo/job_state.write` only.** It does
   tmp + `os.replace`; ad-hoc `open(...).write(...)` will corrupt the
   reader during partial writes.
7. **`get_presigned_url` is the only path that returns a B2 URL to the
   browser.** No raw B2 keys in API responses except inside the manifest.

## Strong preferences

8. Files stay under 300 lines — enforced by structural test.
9. Service-layer modules expose plain functions; the pipeline composes
   them via `PipelineDeps`. New providers (other ASR / LLM vendors) slot
   in by swapping the corresponding dep, not by editing `pipeline.py`'s
   structure.
10. Error taxonomy lives in `app/service/downloader.py::classify_yt_dlp_error`
    (yt-dlp stderr → stable code) and in `pipeline.py` (codes recorded into
    `JobError.code`). New conditions extend the same dict; don't sprinkle
    ad-hoc codes through callers.

## Frontend rules

11. All API calls go through `apps/web/src/lib/api-client.ts` and are
    consumed via TanStack hooks in `lib/queries.ts`. No bare `fetch` in
    components.
12. Dashboard recent/previous videos use the B2-backed jobs index exposed
    by `GET /jobs` and `GET /jobs/latest`. Keep
    `app/service/jobs_index.py`, `app/runtime/jobs.py`, and
    `apps/web/src/lib/queries.ts` in sync when changing that flow.
13. Insight cards seek the player via `videoRef.current.currentTime`.
    Do not regenerate signed URLs per click — the source URL is set
    once at mount.

## Tests required

- Pipeline: happy path, no API key, ASR failure, insights failure, cancel
  during transcribing, yt-dlp error classification, scratch-dir cleanup.
- Job state: round-trip, missing file, cancel flag, torn write recovery.
- ASR: chunk offset math, missing-key error.
- Insights: schema validation, malformed-item drop, missing-key error.
- YouTube: host allowlist (positives + negatives), invalid scheme, empty.
- ffmpeg: behind `pytest.skipif` when binaries are missing.
