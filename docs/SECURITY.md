<!-- last_verified: 2026-05-26 -->
# Security

## URL host allowlist

`POST /jobs` rejects any URL whose hostname is not in
`ALLOWED_VIDEO_HOSTS`. Default: YouTube hosts only. Adding a new host
should be a deliberate config change, not a default.

## Duration cap

`MAX_VIDEO_SECONDS` is enforced after yt-dlp finishes downloading (using
ffprobe). YouTube metadata can be wrong; the post-download check is the
authoritative gate.

## Subprocess hygiene

All `subprocess.run` calls live in `app/service/downloader.py` (yt-dlp)
or `app/service/ffmpeg_audio.py` (ffmpeg / ffprobe). The orchestrator in
`app/service/pipeline.py` wraps every call in `asyncio.to_thread`. They:

- Pass arguments as a list (no shell interpolation).
- Set `check=False` and inspect `returncode` explicitly so we can
  classify error codes and avoid leaking subprocess tracebacks.
- Wrap the call site in `asyncio.to_thread` so a blocking subprocess
  doesn't starve the event loop.

The user-supplied URL is the only piece of untrusted data that ever
reaches `subprocess`, and it lands as a separate `argv` entry to
`yt-dlp` — never concatenated into a shell string.

## Presigned URL expiry

All presigned URLs use `ExpiresIn=3600` (1h). State files never store
URLs — only B2 keys. URLs are minted on demand by `/jobs/{id}/source`
(or `/manifest|/transcript|/insights`) and returned via `302` redirect.

## .env discipline

- `.env` is gitignored.
- `.env.example` ships placeholders that the startup check rejects so a
  copy-paste-and-forget never reaches B2 with bad creds.
- Required keys (`B2_ENDPOINT`, `B2_REGION`, `B2_KEY_ID`,
  `B2_APPLICATION_KEY`, `B2_BUCKET_NAME`) match the parent
  `sampleapps/CLAUDE.md` exactly. No aliases.

## CORS

Default origins: `http://localhost:3000,http://localhost:3001`. Production
deploys MUST override with the exact frontend origin. The
`API_CORS_ORIGIN_REGEX` escape hatch is wired by `scripts/dev.sh` for
dev only — never set it in production.

## What's intentionally out of scope

- **Auth.** This is an internal-tool sample. There is no user model and
  no per-user job isolation. Add real auth before deploying outside a
  trusted network.
- **Rate limiting.** A single-worker uvicorn with `MAX_CONCURRENT_JOBS=1`
  is the natural throttle for the MVP.
