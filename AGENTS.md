# AGENTS.md

Authoritative control surface for all coding agents. Read this first.

## 1. Repository Map

```
apps/web/           Next.js 16 frontend (App Router, Tailwind v4, shadcn/ui)
services/api/       FastAPI backend (layered: types/config/repo/service/runtime)
packages/shared/    Shared TypeScript types — mirrors Pydantic models
docs/               System of record (features, workflows, security, reliability)
docs/exec-plans/    Execution plans and tech debt
scripts/            doctor.mjs, dev.sh, pick-port.mjs
```

## 2. Architectural Invariants

**Backend layering**: `types` -> `config` -> `repo` -> `service` -> `runtime`

- No backward imports across layers.
- `boto3` only inside `app/repo/`. Enforced by `tests/test_structure.py`.
- No business logic in `runtime/` handlers — they call `service/`.
- Every `subprocess.run` for yt-dlp / ffmpeg / ffprobe is wrapped in
  `await asyncio.to_thread(...)` inside `app/service/pipeline.py`. They
  never run directly on the event loop.
- Job state is one file per job at `${WORK_DIR}/jobs/{job_id}.json`,
  written via tmp + `os.replace`. No in-memory dict, no `asyncio.Lock`,
  no Redis.
- Concurrency is bounded by a lifespan-managed `asyncio.Semaphore`
  sized from `MAX_CONCURRENT_JOBS` (default 1).
- All boundary data is Pydantic-validated.

**Frontend**:
- shadcn/ui components in `src/components/ui/` are generated — never modify them.
- Every API call flows through TanStack Query hooks in `apps/web/src/lib/queries.ts`.
- Dashboard job summaries come from the B2-backed jobs index exposed by
  `GET /jobs` and `GET /jobs/latest`; the frontend consumes them through
  `useJobsIndex` and `useLatestJob` in `apps/web/src/lib/queries.ts`.

## 3. Quality Expectations

- DRY — extract shared code only when used in 2+ places.
- Structured JSON logging only — no `print()`.
- Files stay under 300 lines (enforced by structural test).
- Tests added or updated for every behavior change.
- Docs updated in the same PR as code.
- Lint clean before merge.

## 4. Mechanical Enforcement

| Rule | Enforced by |
|------|-------------|
| No backward imports | `tests/test_structure.py::test_no_backward_imports` |
| No boto3 outside `repo/` | `tests/test_structure.py::test_boto3_only_in_repo` |
| File size < 300 lines | `tests/test_structure.py::test_file_size_limits` |
| All layers exist | `tests/test_structure.py::test_all_layers_exist` |
| No bare `print()` | ruff rule T20 |
| Import ordering | ruff rule I001 |
| Frontend strict equality | eslint `eqeqeq` |

## 5. Commands

```bash
# Run
pnpm dev               # start both web + api (after `pnpm doctor`)
pnpm dev:web           # frontend only
pnpm dev:api           # backend only (uvicorn --workers 1)

# Quality
pnpm lint              # frontend (eslint)
pnpm build             # frontend typecheck + build
pnpm lint:api          # backend (ruff)
pnpm test:api          # backend (pytest)
pnpm check:structure   # structural boundary tests
pnpm doctor            # preflight environment check
```

## 6. Agent Workflow

1. Read this file first.
2. For non-trivial changes, drop a plan into `docs/exec-plans/active/`.
3. Implement the smallest coherent change.
4. Run: `pnpm lint && pnpm lint:api && pnpm test:api && pnpm check:structure`.
5. Update docs in the same PR.
6. Move completed plans into `docs/exec-plans/completed/`.

## 7. Doc Update Mapping

| Change Type | Update Location |
|---|---|
| Feature logic, inputs, outputs, tests | `docs/features/<feature>.md` |
| User journeys | `docs/app-workflows.md` |
| System layout, deployments | `ARCHITECTURE.md` |
| Setup or scope changes | `README.md` |
| Security changes | `docs/SECURITY.md` |
| Reliability changes | `docs/RELIABILITY.md` |
| Active work plans | `docs/exec-plans/active/` |
| Known tech debt | `docs/exec-plans/tech-debt-tracker.md` |

## 8. Doc Read Order (for a fresh agent)

1. `AGENTS.md` (this file)
2. `ARCHITECTURE.md`
3. `docs/features/youtube-ingest.md` — yt-dlp + error taxonomy
4. `docs/features/ai-analysis.md` — Parakeet + Llama + graceful degradation
5. `docs/features/video-playback.md` — presigned URLs + seek
6. `docs/app-workflows.md` — submit/poll/done/cancel
7. `docs/SECURITY.md` + `docs/RELIABILITY.md`

## 9. When Unsure

- Prefer boring, stable libraries.
- Prefer small PRs over large changes.
- Never bypass lint rules without explicit instruction.
- Never run multiple uvicorn workers — state is per-process.
- Ask before destructive or irreversible changes.
