# Tasks

## 1. Static site

- [x] 1.1 Add the independent marketing build, sourced HTML copy, responsive layout, and ADR; verify local build, keyboard navigation, no-JavaScript rendering, and mobile overflow checks.
- [x] 1.2 Add optional URL configuration with setup documentation; verify configured destinations and successful unconfigured builds and invalid URL failures.

## 2. Visual enhancement

- [x] 2.1 Add the interactive Three.js composition and matching static fallback; verify pointer response, failed initialization, and context-loss browser checks.
- [x] 2.2 Add reduced-motion, pause/resume, visibility suspension, and cleanup; verify initial and changed preferences, keyboard control, and offscreen suspension.

- [x] 2.3 Add reversible scroll choreography for the 3D composition and workflow; verify forward/backward scrolling, rendered pose changes with animation time frozen, native navigation, pause/reduced motion, fallback, and teardown.

## 3. Delivery checks

- [x] 3.1 Add independent CI build, link checks, and axe/browser checks; verify the same commands locally and retain a built artifact for review.
- [ ] 3.2 Choose hosting, marketing domain, and optional app URL when the site is ready; verify a release build and live destination checks and document deployment and rollback. Deferred by the maintainer until deployment readiness.

## 4. Repository integration

- [x] 4.1 Run `npx @fission-ai/openspec validate --all --strict`, `task check test build schema-check` with real PostgreSQL/Redis, `task e2e`, and `git diff --check`; record outcomes and any baseline failures separately from marketing checks. Worker wiring is unchanged.

## Workflow follow-up

- Archive this change in the PR that completes issue #53, after deployment choices and required verification are complete.
