<!-- last_verified: 2026-05-26 -->
# Dev workflows

## Running

```bash
pnpm dev            # both web + api with auto port-pick
pnpm dev:web        # frontend only
pnpm dev:api        # backend only (uvicorn --workers 1)
```

`pnpm dev` runs `pnpm doctor` first to catch the usual environment
issues (wrong Node / Python, missing `ffmpeg` or backend `yt-dlp`
module, placeholder `.env`, busy port 3000).

## Testing

```bash
pnpm test:api               # full pytest run
pnpm check:structure        # just the boundary tests
pnpm lint:api               # ruff
pnpm lint                   # eslint (frontend)
pnpm build                  # frontend typecheck + build
```

Tests must not touch real B2 or NVIDIA. Patterns:

- B2 — inject a `FakeB2` (see `tests/conftest.py::fake_b2`) into
  `PipelineDeps.put_file_to_b2` / `put_json_to_b2`. No `moto`, no
  `botocore.stub`.
- NVIDIA — mount an `httpx.MockTransport` and pass it via the
  `transport=` parameter on `asr.transcribe_chunks` /
  `insights.extract_insights`.
- yt-dlp module / ffmpeg / ffprobe — `tests/test_pipeline.py` swaps them out
  via `PipelineDeps`. `tests/test_ffmpeg_audio.py` exercises the real
  binaries but is `pytest.skipif`-gated on their presence.

## Adding an endpoint

Three files touched, in this order:
1. `services/api/app/runtime/jobs.py` (or a new router) — declare the
   route + Pydantic response model.
2. `apps/web/src/lib/api-client.ts` — typed `apiFetch` wrapper.
3. `apps/web/src/lib/queries.ts` — TanStack hook.

Add a test in `services/api/tests/` and update the relevant doc in
`docs/features/`.
