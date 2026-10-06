# Verification

Local checks on 6 October 2026, using Node 24 and isolated real PostgreSQL 17
and Redis 7 services. No product files or API contracts changed.

- `marketing`: `npm run check`, `npm run build`, and four build/link probes pass.
- Marketing browser suite: 14 checks pass without an app URL; 15 pass with
  synthetic app/canonical URLs after adding the 720px reflow check. Axe passes
  at 320, 390, 720, 768, and 1440 CSS pixels. The 720px width covers the layout
  viewport equivalent to a 1440px display at 200% browser zoom.
- Browser coverage includes no-JavaScript HTML, keyboard pause, frozen rendered
  frames, pointer response with animation time held constant, initial/changed
  reduced motion, offscreen suspension, and actual WebGL context loss. Hidden
  document and back-forward-cache events are simulated lifecycle checks.
- `npm run check:links -- --live`: built assets/fragments and the public GitHub
  project/license URLs pass. Synthetic app URLs are only checked structurally
  and in browser rendering; no live app destination is verified.
- `task check test build schema-check`: pass. Backend 969 tests, frontend 89,
  matcher 26. The checks use real isolated services.
- `task e2e`: 33 checks pass against the isolated local product stack.
- `npx @fission-ai/openspec validate --all --strict`: 17 items pass.
- `git diff --check`: pass.

The independent GitHub workflow is added but has not run remotely. Hosting,
marketing domain, DNS, publication, and deployed-site verification remain
pending. The app link is optional. The change stays active until the deferred
hosting task is resolved; issue #53 is not closed.
