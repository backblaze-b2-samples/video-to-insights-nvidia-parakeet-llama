<!-- last_verified: 2026-05-26 -->
# Architecture

## Components

- **apps/web/** — Next.js 16 frontend (App Router, Tailwind v4, shadcn/ui).
  Dashboard and job routes: submit form, status card, video player,
  insights panel, files browser, and B2-backed jobs index. TanStack Query
  polls active jobs until they hit a terminal state.
- **services/api/** — FastAPI backend, layered.
  - REST surface for submit / poll / artifact-redirect / cancel.
  - Pipeline orchestrator runs as an asyncio Task guarded by a
    lifespan-managed Semaphore.
  - boto3 (S3-compatible B2) calls only from `app/repo/b2_client.py`.
  - Subprocess calls (yt-dlp, ffmpeg, ffprobe) only from
    `app/service/downloader.py` and `app/service/ffmpeg_audio.py`; the
    orchestrator wraps every invocation in `asyncio.to_thread` from
    `app/service/pipeline.py`.
- **packages/shared/** — TypeScript mirror of the Pydantic models
  (`JobStatus`, `SubmitRequest`, `Insight`, `ManifestV1`).

## Backend Layering

```
types/      Pydantic models — no logic, no imports from other layers
  |
config/     pydantic-settings — depends only on types
  |
repo/       Data access — B2 (boto3) + atomic job-state files
  |
service/    Business logic — youtube, ffmpeg_audio, asr, insights, pipeline
  |
runtime/    FastAPI routes — calls service, never repo directly
```

Lower-numbered layers must not import from higher-numbered layers, enforced
by `tests/test_structure.py::test_no_backward_imports`.

### Directory Structure

```
services/api/
  main.py                     App entrypoint, lifespan, semaphore
  app/
    types/
      job.py                  JobStatus, SubmitRequest, etc.
      manifest.py             ManifestV1
    config/
      settings.py             B2 + NVIDIA + pipeline knobs
    repo/
      b2_client.py            S3 client (boto3) — only file allowed to import boto3
      job_state.py            Atomic file-per-job state
    service/
      youtube.py              URL validation + host allowlist
      ffmpeg_audio.py         probe / extract / chunk
      asr.py                  NVIDIA Parakeet client (httpx)
      insights.py             NVIDIA Llama-3.3 client (httpx)
      pipeline.py             Orchestrator — wraps all subprocess work in to_thread
    runtime/
      health.py               /health
      jobs.py                 POST /jobs, GET /jobs[/latest|/{id}/...], DELETE /jobs/{id}
  tests/
    test_structure.py         Boundary + size lints
    test_youtube_validate.py  Host allowlist
    test_ffmpeg_audio.py      Real ffmpeg, skipif missing
    test_asr_client.py        httpx MockTransport + offset stitching
    test_insights_client.py   httpx MockTransport + JSON schema
    test_pipeline.py          End-to-end with injected fakes
    test_job_state.py         Atomic rename, missing files, cancel
```

## Boundary Invariants

- `boto3` and `botocore` only in `app/repo/`.
- `subprocess` only in `app/service/downloader.py` and `app/service/ffmpeg_audio.py`,
  always invoked from `app/service/pipeline.py` through `asyncio.to_thread`.
- All data crossing layer boundaries uses Pydantic models.
- Configuration is read-only after init.

## Data Flow

1. **Submit.** `POST /jobs` validates the URL against the host allowlist,
   writes an initial `JobStatus` file, and schedules
   `_run_under_semaphore(job_id)` as a background task.
2. **Download.** Pipeline shells `yt-dlp` into `${WORK_DIR}/{video_id}/source.mp4`.
3. **Upload source.** `put_file` -> B2 key
   `video-to-insights-pipeline/{video_id}/source.mp4`. `JobStatus.result.source_key`
   is recorded.
4. **(Optional) ASR + insights.** With `NVIDIA_API_KEY`:
   ffmpeg extracts mono 16k WAV, splits into ≤22-min chunks; Parakeet
   transcribes each chunk; the client shifts segment timestamps by the
   chunk's start offset. Transcript and insights JSON are uploaded to B2.
5. **Manifest.** A `ManifestV1` JSON describing all the above is written
   to `video-to-insights-pipeline/{video_id}/manifest.json`.
6. **Cleanup.** `${WORK_DIR}/{video_id}/` is removed in `finally`.

If `NVIDIA_API_KEY` is missing: source uploads, manifest writes
`analysis_status: "skipped_no_api_key"`, terminal status is
`done_no_analysis`. If ASR fails: terminal `done_no_analysis` with
`analysis_status: "failed_asr"`. If insights fail after ASR: transcript
is still uploaded; terminal `done_no_analysis` with
`analysis_status: "failed_insights"`.

## B2 Object Layout

```
b2://{B2_BUCKET_NAME}/video-to-insights-pipeline/{video_id}/
  source.mp4
  transcript.json    # Parakeet segments + assembled text
  insights.json      # LLM-extracted sections
  manifest.json      # schema_version=1, points at the three above
```

`video_id` is a UUID4. The single top-level prefix lets this sample share
a bucket cleanly with other samples in the repo.

## S3 client identity

Per `../CLAUDE.md`, the boto3 client carries:

```
customUserAgent / user_agent_extra = "video-to-insights-pipeline/0.1.0 (backblaze-b2-samples)"
```

Set once in `app/repo/b2_client.py`.

## Trust Boundaries

- **Frontend → API.** CORS-restricted to configured origins.
- **API → B2.** Authenticated via application key, signature v4.
- **Browser → B2.** Presigned URLs (1h) for source playback and JSON
  artifact fetch. Never long-lived links in the state file — the API
  mints them on demand.

## Deployment

- **Local dev.** `pnpm dev` -> `concurrently` runs Next.js and uvicorn.
- **Production.** Run uvicorn with `--workers 1`. State is per-process;
  scaling out requires swapping `repo/job_state.py` for a shared store
  first.

## Canonical Files

- Pipeline orchestrator: `services/api/app/service/pipeline.py`
- B2 repo (boto3): `services/api/app/repo/b2_client.py`
- Job state: `services/api/app/repo/job_state.py`
- HTTP surface: `services/api/app/runtime/jobs.py`
- Pydantic models: `services/api/app/types/job.py` + `manifest.py`
- Config: `services/api/app/config/settings.py`
- Structural tests: `services/api/tests/test_structure.py`
- Frontend page: `apps/web/src/app/page.tsx`
- Frontend API client: `apps/web/src/lib/api-client.ts`
- Shared TS types: `packages/shared/src/types.ts`
