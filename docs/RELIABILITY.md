<!-- last_verified: 2026-05-26 -->
# Reliability

## Single-worker constraint

State files are per-process. Run uvicorn with `--workers 1`. Scaling out
means moving `app/repo/job_state.py` behind a shared store (Redis /
Postgres / files on shared storage) first.

## Atomic state file

`app/repo/job_state.py::write` does tmp + `os.replace` so a reader is
always seeing a fully-formed JSON document. A POSIX rename on the same
filesystem is atomic; that's the only invariant we depend on. A leftover
`*.tmp` file from a process kill is harmless: the next `write` will
create a fresh one, and `read` ignores anything that isn't `{job_id}.json`.

## Partial success surfacing

The pipeline never silently drops artifacts. `JobStatus.result` carries
nullable B2 keys for `source`, `transcript`, `insights`, `manifest`.
Terminal status + `analysis_status` together describe the outcome:

| `status` | `analysis_status` | What landed in B2 |
|---|---|---|
| `done` | `ok` | source + transcript + insights + manifest |
| `done_no_analysis` | `skipped_no_api_key` | source + manifest |
| `done_no_analysis` | `failed_asr` | source + manifest |
| `done_no_analysis` | `failed_insights` | source + transcript + manifest |
| `cancelled` | (any) | up to whichever stage finished before cancel |
| `failed` | (any) | up to whichever stage finished before error |

The frontend renders the player as long as `status` is `done` or
`done_no_analysis`.

## Cooperative cancellation

`DELETE /jobs/{id}` sets `cancel_requested = true`. The pipeline checks
the flag between stages and exits with `status: "cancelled"`. A
subprocess already mid-stage (yt-dlp download, ffmpeg extract) will run
to completion before the next check; the README and CODE_REVIEW
document that.

## Cleanup

`run_job`'s `finally` block runs `shutil.rmtree(work_dir, ignore_errors=True)`
for the per-video scratch dir. B2 holds the durable artifacts; nothing
on local disk is needed once the manifest is written.

## Restart semantics

A server restart leaves finished and failed jobs intact (their state
files persist). In-flight jobs are abandoned — their state files will
show the last stage they reached before the restart and never advance.
The frontend's poller will keep retrying until the user navigates away.
This is the documented MVP behavior.
