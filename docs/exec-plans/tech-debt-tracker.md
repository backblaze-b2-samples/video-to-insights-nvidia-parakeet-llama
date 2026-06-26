<!-- last_verified: 2026-05-26 -->
# Tech Debt Tracker

| Description | Impact | Proposed Resolution | Priority | Status |
|---|---|---|---|---|
| Presigned URL re-mint on long viewing sessions | Browser playback dies after 1h | Surface a re-mint affordance in the UI, or move to streaming via a backend reverse-proxy | Low | Open |
| In-flight jobs are abandoned on server restart | Single-worker MVP behavior — documented, not a regression | Move state behind a shared store + add restart-aware reconciliation | Medium | Open |
| `subprocess.run` for yt-dlp can produce huge stderr | Memory blip on pathological errors | Stream stderr instead of buffering, or truncate before classification | Low | Open |
| Temporary `B2_KEY_ID` fallback | Keeps one rolling deploy compatible with the previous B2 env contract | Remove the fallback from settings, doctor, and docs after 2026-07-31, once old processes have drained | Medium | Open |
