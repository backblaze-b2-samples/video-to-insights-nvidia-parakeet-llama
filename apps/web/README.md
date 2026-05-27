# apps/web

Next.js 16 frontend for `video-to-insights-pipeline`. App Router, Tailwind v4,
shadcn/ui ("new-york" style, zinc base, lucide icons — see `components.json`).

## shadcn primitive policy

This sample ships only the shadcn/ui primitives it actually uses. Adding the
full kit pulls a lot of unused tree and packages along with it. To add another
primitive when you genuinely need it:

```
pnpm dlx shadcn@latest add <component>
```

If the new component pulls in a Radix subpackage that isn't already declared,
add it to `package.json` in the same change.

## Scripts

```
pnpm dev          # next dev
pnpm build        # next build (typechecks)
pnpm lint         # eslint
pnpm typecheck    # tsc --noEmit
```
