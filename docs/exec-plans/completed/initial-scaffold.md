# Plan — video-to-insights-pipeline

> Scaffold a new B2 sample from `vibe-coding-starter-kit`. Internal user pastes a YouTube URL → backend downloads with yt-dlp → uploads source to B2 → runs free NVIDIA NIM ASR + LLM for timestamped insights → frontend plays the B2-hosted video with seekable insight cards. Gracefully degrades to "video playback only" when no NVIDIA key is set.

Plan locked through conversation iteration with the user; red-teamed by `feature-dev:code-reviewer` sub-agent; free-tier model availability verified via WebSearch.

Historical note: this plan records the initial scaffold. The current
implementation later added the B2-backed jobs index exposed by
`GET /jobs` and `GET /jobs/latest`; use `AGENTS.md` and
`ARCHITECTURE.md` for current architecture rules.

---

## 1. Purpose

`video-to-insights-pipeline` is an internal reference sample for Backblaze employees and prospects evaluating how to build an AI-on-video pipeline whose source-of-truth is B2 object storage. A user pastes a YouTube URL; the backend downloads the video, uploads it to B2, transcribes it with NVIDIA Parakeet (free hosted NIM endpoint, segment + word timestamps), extracts a small list of "insight" sections via NVIDIA Llama-3.3-70B-Instruct (free), and stores both sidecar JSON artifacts alongside a manifest in B2. The frontend streams the B2 source over HTTP-range requests inside a native `<video>` element; clicking an insight card sets `currentTime` to jump to that section.

The sample demonstrates: (a) B2 as the system of record for large media + AI-derived metadata, (b) presigned URLs for direct browser playback of B2-hosted MP4s, (c) graceful degradation so the B2 half of the pipeline is testable with zero AI credentials.

---

## 2. Architecture delta from vibe-coding-starter-kit

| Keep (as-is) | Trim (remove from starter) | Add (new for this sample) |
|---|---|---|
| Monorepo layout (`apps/web` + `services/api` + `packages/shared`) | Generic file-upload UI (dashboard, upload page, files page) | Single `/` page: paste-URL form + result card with video player + insight cards |
| Next.js 16 App Router, Tailwind v4, shadcn/ui, TanStack Query | `dashboard/`, `files/`, `settings/`, `design/` route trees | `/jobs/{id}` is the status resource; UI polls it via TanStack Query |
| FastAPI layering: types → config → repo → service → runtime, structural test enforced | `app/runtime/upload.py`, `app/service/upload.py`, `app/service/metadata.py` (multipart file upload) | `app/service/youtube.py` (yt-dlp), `app/service/ffmpeg_audio.py` (extract + chunk audio), `app/service/asr.py` (NVIDIA Parakeet), `app/service/insights.py` (NVIDIA Llama-3.3), `app/service/pipeline.py` (orchestrator), `app/runtime/jobs.py` |
| `app/repo/b2_client.py` (boto3 S3 with custom user-agent — pattern only) | The `b2ai-oss-start` user-agent string and the `B2_S3_ENDPOINT` / `B2_APPLICATION_KEY_ID` env-var names (these drift from parent CLAUDE.md and must be replaced) | `app/repo/b2_client.py` with user-agent `video-to-insights-pipeline/0.1.0 (backblaze-b2-samples)`; env vars `B2_ENDPOINT` / `B2_REGION` / `B2_KEY_ID` / `B2_APPLICATION_KEY` / `B2_BUCKET_NAME` per parent CLAUDE.md |
| Structured JSON logging, CORS, lifespan setup pattern from `main.py` | The placeholder file metadata extraction (PIL EXIF, PDF page count) | `app/repo/job_state.py` — atomic file-per-job state (`work_dir/jobs/{job_id}.json` via tmp+rename); no in-memory dict, no asyncio.Lock |
| pytest + ruff + structural test (`tests/test_structure.py`) | All `tests/test_upload_*`, `test_delete*`, `test_download_*`, `test_metadata*` | `tests/test_youtube_validate.py`, `tests/test_ffmpeg_audio.py`, `tests/test_asr_client.py` (with fake NIM client), `tests/test_insights_client.py`, `tests/test_pipeline.py` (faked downloader + fake S3 + fake NIM), `tests/test_job_state.py` |
| `pnpm dev` / `pnpm dev:api` / `pnpm dev:web` workflow | `infra/railway/` deploy config (out of scope) | `scripts/doctor.mjs` (checks ffmpeg + yt-dlp on PATH, warns if NVIDIA_API_KEY missing) wired to `pnpm doctor` |
| LICENSE (Apache 2.0), pre-commit hooks, pnpm workspace | Vibe starter README content | New README covering pipeline diagram, env setup (brew/apt for ffmpeg, pip install for yt-dlp), graceful-degradation behavior, free-tier model notes, YouTube ToS disclaimer |
| Frontend `apiFetch` + TanStack `qk` query-key conventions | Dashboard panels (`StatsCards`, `RecentUploadsTable`, `UploadChart`) | Job detail components plus B2-index-backed dashboard components (`RecentVideosTable`, `StatsCards`, `ActivityChart`, `LastProcessedCard`) |
| `packages/shared` for TS↔Python type mirror | — | New shared types: `SubmitRequest`, `JobStatus`, `ManifestV1`, `Insight` |
| | | **No Docker.** Explicit user decision — keep dev simple, devs use local Python + Node. |

---

## 3. B2 surface (S3-only, per parent CLAUDE.md)

Per the parent CLAUDE.md, the sample uses the S3-compatible API exclusively via `boto3`. No b2-native API usage.

S3 operations exercised:
- `PutObject` — upload `source.mp4`, `transcript.json`, `insights.json`, `manifest.json`
- `HeadObject` — idempotency check on resubmit (does `source.mp4` for this `video_id` already exist?)
- `GeneratePresignedUrl` (GET) — minted on demand for source playback, manifest fetch, transcript fetch, insights fetch (1h expiry)
- `DeleteObject` — used only by tests' cleanup helper, never in production paths

All operations through `app/repo/b2_client.py`. Structural test asserts no `boto3` imports outside `app/repo/`.

Object layout in B2:
```
b2://{B2_BUCKET_NAME}/video-to-insights-pipeline/{video_id}/
  source.mp4
  transcript.json     # Parakeet segments with timestamps + assembled full text
  insights.json       # LLM-extracted sections: title, summary, start_seconds, end_seconds, key_quotes
  manifest.json       # Schema-versioned, points at all three above
```

`video_id` = `uuid4`. Single sample-scoped top-level prefix (`video-to-insights-pipeline/`) so the bucket can be shared cleanly with other samples in the repo.

---

## 4. Key features

1. **Paste-and-play.** Single form labeled "Video URL (YouTube)" + segment-length input (kept though clips are dropped — the field is removed from the UI). One-click submission returns a `job_id` immediately.
2. **B2 is the system of record for video + AI metadata.** Source MP4, AI-derived JSON artifacts (transcript, insights, manifest), and the dashboard jobs index live in B2.
3. **Seekable insight cards.** Clicking an insight card in the right column calls `videoRef.current.currentTime = insight.start_seconds`. Player streams the B2 source over HTTP range requests via a 1-hour presigned URL.
4. **Graceful degradation without NVIDIA_API_KEY.** Missing or invalid key → pipeline still downloads + uploads source, sets `analysis_status: "skipped_no_api_key"`, returns `status: "done_no_analysis"`. UI renders the video player normally and shows a muted notice instead of the insights panel. The B2 half of the sample is fully usable with B2 credentials alone.
5. **Cooperative cancellation.** `DELETE /jobs/{id}` sets a `cancel_requested` flag in the state file; pipeline checks it between stages. README documents that a stuck subprocess won't die immediately.
6. **Free-tier AI only.** Defaults to `nvidia/parakeet-tdt-0.6b-v2` (24-min ASR window, segment timestamps built in) and `meta/llama-3.3-70b-instruct` (unambiguously free). Both override-able via env. ffmpeg audio-chunking kicks in only for videos > ~22 minutes.

---

## 5. Doc transforms

Rewrite (keep filename, replace contents to match new architecture):
- `README.md` — new pipeline diagram, env setup (no Docker), free-tier model notes, graceful-degradation behavior, YouTube ToS disclaimer, "for content you own / CC content / fair-use research" notice.
- `AGENTS.md` — same control-surface header, but doc-read order points at the new feature files; commands section reflects the new layout (`pnpm doctor`, smoke test recipe).
- `ARCHITECTURE.md` — replace the upload/download diagram with the new pipeline; layer table unchanged; structural-test contract unchanged.
- `CLAUDE.md` — top-of-tree onboarding doc; doc-read order, test commands, diff discipline. Slug + scope updated.
- `.env.example` — parent-CLAUDE.md mandated names (`B2_ENDPOINT`, `B2_REGION`, `B2_KEY_ID`, `B2_APPLICATION_KEY`, `B2_BUCKET_NAME`) + sample-specific `NVIDIA_API_KEY`, `NVIDIA_ASR_MODEL`, `NVIDIA_INSIGHTS_MODEL`, `WORK_DIR`, `MAX_VIDEO_SECONDS`, `MAX_CONCURRENT_JOBS`, `ALLOWED_VIDEO_HOSTS`.
- `CODE_REVIEW.md` — keep the structure; rules updated to ban `subprocess.run` outside `app/service/` and to require `asyncio.to_thread` wrapping in `app/service/pipeline.py`.
- `package.json` (root + apps/web + services/api as relevant) — name field switches to `video-to-insights-pipeline`. Scripts gain `doctor`.
- `pyproject.toml` — name, description, dependencies (drop file-upload-only deps if any; add `yt-dlp`, `pydub` only if necessary — prefer pure ffmpeg, `httpx` for NIM calls).

Stub new feature docs:
- `docs/features/youtube-ingest.md` — yt-dlp invocation, host allowlist, duration cap, error taxonomy.
- `docs/features/ai-analysis.md` — Parakeet call shape, 24-min window, audio chunking strategy; Llama insights prompt + JSON-mode schema; graceful-degradation behavior.
- `docs/features/video-playback.md` — presigned URLs, HTML5 range-request streaming, insight-card seek behavior.
- `docs/app-workflows.md` — submit → poll → done flow; cancel flow.
- `docs/SECURITY.md` — URL host allowlist, duration cap, subprocess hygiene, presigned URL expiry, .env discipline.
- `docs/RELIABILITY.md` — single-worker constraint, atomic state file, partial-success surfacing in `result.clip_keys`/`result.transcript_key`.

Delete (not relevant to this sample):
- Any starter doc that's purely about the file-upload-dashboard demo (e.g., `docs/features/file-upload.md` if present), `infra/railway/`.

Move:
- This plan, on finalize, → `docs/exec-plans/completed/initial-scaffold.md`.

---

## 6. Rename table

| Identifier kind | From (starter) | To (this sample) |
|---|---|---|
| Directory / repo slug (kebab) | `vibe-coding-starter-kit` | `video-to-insights-pipeline` |
| Python package name (snake) | `vibe_coding_starter_kit` (where used) | `video_to_insights_pipeline` |
| Title Case (docs, README headings) | `Vibe Coding Starter Kit` | `Video to Insights Pipeline` |
| `package.json` `name` (root) | `vibe-coding-starter-kit` | `video-to-insights-pipeline` |
| `package.json` `name` (apps/web) | `@vibe-coding-starter-kit/web` (or starter's exact form) | `@video-to-insights-pipeline/web` |
| `pyproject.toml` `name` | `vibe-coding-starter-kit-api` (or starter's exact form) | `video-to-insights-pipeline-api` |
| Custom S3 user-agent string | `b2ai-oss-start` (used as `user_agent_extra`) | `video-to-insights-pipeline/0.1.0 (backblaze-b2-samples)` |
| B2 env var: endpoint | `B2_S3_ENDPOINT` | `B2_ENDPOINT` |
| B2 env var: key id | `B2_APPLICATION_KEY_ID` | `B2_KEY_ID` |
| B2 env var: region | (absent in starter) | `B2_REGION` (added) |
| B2 env var: application key | `B2_APPLICATION_KEY` | `B2_APPLICATION_KEY` (unchanged) |
| B2 env var: bucket | `B2_BUCKET_NAME` | `B2_BUCKET_NAME` (unchanged) |
| Frontend API base env | `NEXT_PUBLIC_API_URL` | `NEXT_PUBLIC_API_URL` (unchanged) |
| Top-level B2 object prefix | `b2ai-oss-start/` (if any) | `video-to-insights-pipeline/` |
| Image / docker tag references | any `vibe-coding-starter-kit:*` | n/a — Docker dropped |
| GitHub workflow slug references | any `vibe-coding-starter-kit-*` | `video-to-insights-pipeline-*` |
| UTM `content` tag (if README links go anywhere with UTM) | `vibe-coding-starter-kit` | `video-to-insights-pipeline` |
| LICENSE attribution | (unchanged Apache 2.0; copyright line if any) | preserve Apache 2.0; update copyright header only if starter has one bearing the old slug |
| `.cache/` dir name (if any) | whatever starter uses | `.cache/video-to-insights/` |

---

## 7. Implementation details locked through conversation

These are commitments the builder must honor; the reviewer will assert against them.

**Layering & concurrency:**
- `boto3` lives ONLY in `app/repo/b2_client.py`. Enforced by `tests/test_structure.py` copied from starter.
- All `subprocess.run` calls (yt-dlp, ffmpeg, ffprobe) are wrapped in `await asyncio.to_thread(...)` inside `app/service/pipeline.py`. They never run directly on the event loop.
- One lifespan-managed `asyncio.Semaphore(MAX_CONCURRENT_JOBS)`. Default `MAX_CONCURRENT_JOBS=1`.
- Job state: one `work_dir/jobs/{job_id}.json` file per job. Writes via tmp-then-rename. No in-memory dict, no `asyncio.Lock`.

**API surface (only these endpoints):**
- `POST /jobs` `{youtube_url, segment_seconds?}` → `{job_id, status: "queued"}`
  - Note: `segment_seconds` is accepted for forward-compat but currently unused (no ffmpeg clip slicing in this MVP). README documents this.
- `GET /jobs?limit=&offset=` → paginated B2-backed jobs index
- `GET /jobs/latest` → most recent indexed job, or null
- `GET /jobs/{id}` → full `JobStatus`
- `GET /jobs/{id}/source` → 302 to presigned source.mp4 URL (1h)
- `GET /jobs/{id}/manifest` → 302 to presigned manifest.json URL (1h)
- `GET /jobs/{id}/transcript` → 302 to presigned transcript.json URL (1h)
- `GET /jobs/{id}/insights` → 302 to presigned insights.json URL (1h)
- `DELETE /jobs/{id}` → sets cancel flag; returns updated JobStatus
- Dashboard job summaries are read through the B2-backed jobs index.

**`JobStatus` shape:**
```jsonc
{
  "job_id": "uuid",
  "video_id": "uuid",
  "source_url": "https://www.youtube.com/watch?v=...",
  "status": "queued|downloading|uploading_source|extracting_audio|transcribing|generating_insights|writing_manifest|done|done_no_analysis|failed|cancelled",
  "analysis_status": "pending|ok|skipped_no_api_key|failed_asr|failed_insights",
  "analysis_message": "string|null",
  "progress": { "stage": "string", "current": 1, "total": 3 },
  "result": {
    "source_key": "string|null",
    "transcript_key": "string|null",
    "insights_key": "string|null",
    "manifest_key": "string|null"
  },
  "error": { "code": "string", "message": "string" } | null,
  "created_at": "ISO-8601",
  "updated_at": "ISO-8601",
  "cancel_requested": false
}
```

**Manifest v1 shape:**
```jsonc
{
  "schema_version": 1,
  "video_id": "uuid",
  "source_url": "https://www.youtube.com/watch?v=...",
  "source": { "b2_key": "...", "duration_seconds": 1843.2, "size_bytes": 248320192 },
  "analysis_status": "ok|skipped_no_api_key|failed_asr|failed_insights",
  "transcript_key": "video-to-insights-pipeline/{video_id}/transcript.json|null",
  "insights": [
    { "index": 0, "title": "...", "summary": "...",
      "start_seconds": 154.2, "end_seconds": 312.8,
      "key_quotes": ["...", "..."] }
  ],
  "insights_key": "video-to-insights-pipeline/{video_id}/insights.json|null",
  "models": { "asr": "nvidia/parakeet-tdt-0.6b-v2",
              "insights": "meta/llama-3.3-70b-instruct" },
  "bucket": "string", "region": "string", "created_at": "ISO-8601"
}
```

**Error taxonomy (yt-dlp + pipeline):**
| Condition | `error.code` | HTTP from runtime |
|---|---|---|
| Host not in `ALLOWED_VIDEO_HOSTS` | `unsupported_host` | 422 |
| Private / members-only video | `yt_dlp_private_video` | 422 |
| Age-restricted | `yt_dlp_age_restricted` | 422 |
| Geo-blocked | `yt_dlp_geo_blocked` | 422 |
| Duration > `MAX_VIDEO_SECONDS` | `video_too_long` | 422 |
| yt-dlp extractor / generic non-zero | `yt_dlp_failed` | 502 |
| B2 upload failed mid-pipeline | `b2_upload_failed` (result lists what landed) | 500 |
| Parakeet call failed (any cause) | `failed_asr` | logged; pipeline continues to `done_no_analysis` |
| Llama call failed (any cause) | `failed_insights` | logged; pipeline continues to `done_no_analysis` with transcript saved |

**Frontend single-page layout (replaces vibe dashboard):**
```
Idle:
  ┌────────────────────────────────────────┐
  │ Video to Insights Pipeline             │
  │ [ Video URL (YouTube) ............ ]   │
  │ [ Run ▶ ]                              │
  │ Recent videos (GET /jobs):             │
  │  · f3b4… https://youtube.com/…  done   │
  └────────────────────────────────────────┘

Running:
  Status pill (current stage) + progress + [ Cancel ]

Done:
  ┌──────────────────────────────┐ ┌────────────────┐
  │  <video controls src=signed> │ │ Insights       │
  │  ref=videoRef                │ │ ▸ 00:00 Intro  │
  │                              │ │ ▸ 02:34 Setup  │
  │  ↗ View source video         │ │ ▸ 08:12 Demo   │
  └──────────────────────────────┘ └────────────────┘

Done (no analysis):
  Same player on left; right column is a muted notice card:
  "Analysis unavailable — NVIDIA_API_KEY not set."
```

`↗ View source video` is `<Button variant="link">` with muted-foreground text — subtle, not a hero CTA. Opens presigned URL in new tab.

**Tests required (pytest + ruff clean):**
- `tests/test_structure.py` — copied; asserts boto3 only in `app/repo/`, file-size cap, layer imports.
- `tests/test_youtube_validate.py` — host allowlist, http/https variants, m./www. subdomain handling.
- `tests/test_ffmpeg_audio.py` — uses checked-in sparse-keyframe 30s fixture (generated with `-g 60`); asserts audio extraction works and chunking produces ≥ 2 pieces with correct cumulative duration when `chunk_seconds=15`.
- `tests/test_asr_client.py` — fake NIM client returns a canned response; asserts segment parsing + offset math when stitching chunks.
- `tests/test_insights_client.py` — fake NIM client returns a JSON-mode response; asserts schema-validation of insights.
- `tests/test_pipeline.py` — full pipeline with injected fake downloader + fake S3 + fake NIM. Asserts:
  - Happy path (key present): all 4 B2 objects land, manifest matches.
  - Missing API key: pipeline still uploads source, `analysis_status: "skipped_no_api_key"`, `status: "done_no_analysis"`.
  - ASR failure: source uploaded, `analysis_status: "failed_asr"`, no insights generated.
  - Llama failure after successful ASR: source + transcript uploaded, `analysis_status: "failed_insights"`.
  - Cancel during transcribing: status `cancelled`, no manifest written, `result.source_key` populated.
  - Injected exception mid-stage: `work_dir/{job_id}/` dir cleaned in finally.
- `tests/test_job_state.py` — atomic rename, concurrent read during write, partial-write recovery on startup.

**Smoke-test fixture:**
`tests/fixtures/sparse_keyframes_30s.mp4` generated with:
```
ffmpeg -f lavfi -i testsrc=duration=30:size=320x240:rate=30 \
       -f lavfi -i sine=frequency=440:duration=30 \
       -g 60 -keyint_min 60 -sc_threshold 0 \
       -c:v libx264 -pix_fmt yuv420p -c:a aac \
       tests/fixtures/sparse_keyframes_30s.mp4
```
Builder may either generate this at scaffold time (if ffmpeg is on PATH) or check in a small fixture; either way, the test must `skipif` when ffmpeg is missing.

---

## 8. Build sequence (for the builder agent)

1. Clone `vibe-coding-starter-kit` → `./video-to-insights-pipeline`; strip git history; preserve LICENSE.
2. Apply the rename table across all files (replace identifiers, env var names, user-agent string).
3. **Realign env vars to parent CLAUDE.md** in `services/api/app/config/settings.py`, `.env.example`, README, `main.py` startup validators, and any test that asserts on env names.
4. Update `app/repo/b2_client.py` user-agent → `video-to-insights-pipeline/0.1.0 (backblaze-b2-samples)`.
5. Delete starter-only routes/components/tests per §2 "trim" column.
6. Add new types: `app/types/job.py`, `app/types/manifest.py`, plus the TypeScript mirror in `packages/shared/`.
7. Add `app/repo/job_state.py` (atomic file-per-job) and its tests.
8. Add `app/service/youtube.py`, `app/service/ffmpeg_audio.py`, `app/service/asr.py`, `app/service/insights.py`, `app/service/pipeline.py` with their tests.
9. Add `app/runtime/jobs.py`; wire into `main.py` with the lifespan semaphore.
10. Replace frontend dashboard with the single-page layout in §7; add `components/jobs/*`; wire TanStack polling that stops on terminal states.
11. Add `scripts/doctor.mjs` and the `pnpm doctor` script.
12. Rewrite `README.md`, `AGENTS.md`, `ARCHITECTURE.md`, `CLAUDE.md`, `CODE_REVIEW.md`; stub new docs under `docs/features/`.
13. Run `pnpm install`, `pnpm lint`, `pnpm test:api` (where reachable without B2/NVIDIA creds). Builder reports results.
14. **Do not commit.** Leave the working tree dirty for user review. (Per global CLAUDE.md.)

---

## 9. Risks & open notes

- **yt-dlp drift:** YouTube periodically breaks extractors. Pin yt-dlp in `pyproject.toml`; README links to upgrade procedure.
- **Free-tier rate:** 40 req/min and ~1000 starting credits. README documents this. Pipeline is sequential per job, so a single user won't hit it.
- **Single-worker constraint:** State file is per-process; multi-worker uvicorn would race. README pins `--workers 1`.
- **Long videos:** > 22-min audio gets chunked for Parakeet. Stitch logic in `app/service/asr.py` adds chunk-start offsets to returned segment timestamps. Test covers this.
- **Legal:** README must include a "for content you own / CC / fair-use research" notice and link YouTube ToS. The sample is not a downloader product.
- **Presigned URL hostname:** `B2_ENDPOINT` must be canonical `s3.<region>.backblazeb2.com`. README warns against CDN aliases.

---

## 10. Future-extension seams (not built, but documented)

- Persistent job store → swap `app/repo/job_state.py` for a Redis/Postgres impl behind the same 3-function interface.
- Multi-worker scale-out → only after state moves off-process.
- Provider abstraction → `app/service/asr.py` and `app/service/insights.py` are deliberately structured so an OpenAI / Anthropic / other-provider variant slots in behind a Protocol without touching `pipeline.py`.
- Transcript search / chaptering UI → all data already in B2; future frontend just fetches `insights.json` via the presigned endpoint.

---

_Plan approved by user 2026-05-26 after iteration + red-team. Free-tier model availability verified via WebSearch._
