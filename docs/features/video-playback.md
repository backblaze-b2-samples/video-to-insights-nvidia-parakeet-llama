# Feature: Video playback

## Goal

After a job finishes, render the B2-hosted source MP4 in a native
`<video>` element and let the user jump between insight sections by
clicking a card.

## How playback works

The frontend `<VideoPlayer>` uses
`src={artifactUrl(jobId, "source")}`, which resolves to:

```
{API_BASE}/jobs/{job_id}/source
```

The API endpoint returns `302 Found` with a 1-hour presigned URL to
`source.mp4` in B2. The browser follows the redirect transparently and
streams via HTTP Range requests, which means:

- The whole MP4 doesn't have to download before playback starts.
- Seek bar drags issue new range requests against the same presigned URL.
- The URL is minted on demand per page load (and lives in the redirect
  response). State files never store the URL — only the raw B2 key.

## Insight cards & seeking

`<InsightsPanel>` fetches `{API_BASE}/jobs/{job_id}/insights` (same 302
pattern, this time to `insights.json`) and renders one button per
insight. Click handler:

```ts
videoRef.current.currentTime = insight.start_seconds;
videoRef.current.play();
```

`videoRef` is a `useRef<HTMLVideoElement>` passed to `<VideoPlayer>` via
`forwardRef`. No clip slicing, no DASH/HLS — just `currentTime`.

## "Done (no analysis)" branch

When `job.status === "done_no_analysis"` the right column renders a muted
notice instead of `<InsightsPanel>`. The video player still appears
exactly as in the happy path.

## Presigned URL expiry

The API mints URLs with `ExpiresIn=3600`. Long viewing sessions that
outlive that window will fail mid-playback; the user can reload the page
to get a fresh URL. We deliberately don't surface a re-mint affordance
in the UI for the MVP — keep this in mind when reviewing.
