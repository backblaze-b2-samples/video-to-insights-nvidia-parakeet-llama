# Issue 1 B2 Standards Correction

Issue: https://github.com/backblaze-b2-samples/video-to-insights-nvidia-parakeet-llama/issues/1

## Goal

Bring the sample into the current B2 standards:

- Use the S3-compatible API as the default.
- Set a Backblaze sample user-agent on every S3 client.
- Use the standard env names: `B2_APPLICATION_KEY_ID`,
  `B2_APPLICATION_KEY`, `B2_BUCKET_NAME`, `B2_REGION`, and optional
  `B2_PUBLIC_URL_BASE`.

## Plan

1. Updated backend settings and startup validation to use
   `B2_APPLICATION_KEY_ID` and derive the S3 endpoint from `B2_REGION`.
2. Kept the existing boto3 S3 client and custom user-agent behavior intact.
3. Updated `.env.example`, local doctor checks, tests, and user docs.
4. Ran lint, backend tests, structure checks, and a B2 standards scan.

## Review fixes

- Added strict `B2_REGION` validation before deriving the S3 endpoint.
- Mirrored the same region validation in `scripts/doctor.mjs`.
- Added a one-release `B2_KEY_ID` fallback for rolling deploys, with the
  standard env var taking precedence and removal tracked after 2026-07-31.
- Documented `B2_PUBLIC_URL_BASE` as reserved/currently unused by this app.
- Added repo-boundary coverage for `get_s3_client()`.
