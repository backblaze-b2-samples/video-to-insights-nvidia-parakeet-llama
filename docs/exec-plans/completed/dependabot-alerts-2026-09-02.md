# Dependabot Alerts 2026-09-02

## Goal

Resolve the open Dependabot npm alerts by upgrading vulnerable direct and
transitive frontend dependencies.

## Scope

- Upgrade Next.js and its matching ESLint config past the latest patched
  advisory range.
- Refresh the pnpm lockfile so vulnerable transitive packages resolve to
  patched versions.
- Run the repository quality checks relevant to dependency changes.
- Document the security maintenance update.

## Verification

- `pnpm lint`
- `pnpm build`
- `pnpm lint:api`
- `pnpm test:api`
- `pnpm check:structure`
