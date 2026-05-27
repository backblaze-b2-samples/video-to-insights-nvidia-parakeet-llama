<!-- last_verified: 2026-05-26 -->
# App Workflows

## Submit a video

1. User pastes a YouTube URL into the `/` form.
2. Frontend calls `POST /jobs`. API:
   - Validates the URL against `ALLOWED_VIDEO_HOSTS`.
   - Creates an initial `JobStatus` (`status: "queued"`).
   - Schedules `_run_under_semaphore(job_id)` as an asyncio Task guarded
     by the lifespan semaphore.
   - Returns `{job_id, status: "queued"}`.
3. Frontend stores `{job_id, source_url, submitted_at}` in localStorage
   and starts polling `GET /jobs/{job_id}` every 1.5s via TanStack Query.

## Poll until terminal

`useJob` keeps refetching while `status` is not one of:
`done`, `done_no_analysis`, `failed`, `cancelled`.

Progress card shows the current stage label
(`downloading`, `uploading_source`, `extracting_audio`, `transcribing`,
`generating_insights`, `writing_manifest`).

## Done — render player + insights

When `status === "done"`:
- Left: `<VideoPlayer>` with `src = {API}/jobs/{id}/source`. The API 302s
  to a presigned B2 URL; the browser follows and starts HTTP Range
  streaming.
- Right: `<InsightsPanel>` fetches `{API}/jobs/{id}/insights` (302 to
  `insights.json`) and renders one button per insight. Click to seek.

When `status === "done_no_analysis"`:
- Same player on the left.
- Right column shows a muted notice — `NVIDIA_API_KEY not set` /
  `transcription failed` / `insight extraction failed` per
  `analysis_status`.

## Cancel

`Cancel` button on the status card calls `DELETE /jobs/{id}`. The API
flips `cancel_requested` in the state file; the pipeline checks the flag
between stages and exits with `status: "cancelled"`. A subprocess
already in flight (yt-dlp, ffmpeg) will run to completion before the
check fires — the README and CODE_REVIEW document that.

## Recent jobs

`<RecentJobsList>` reads `v2i.recent_jobs` from localStorage (max 5
entries, newest first) and lets the user re-open a previous job's view.
There is no API list endpoint by design — every job is owned by the
browser that submitted it.
