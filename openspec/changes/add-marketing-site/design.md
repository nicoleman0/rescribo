# Design

## Context

See [proposal.md](proposal.md) for motivation. The repository has a React product frontend, shared product workflow copy in README, and no production host. The marketing build must not depend on Django, React, or the product bundle. Marketing hosting and domain are deferred by the maintainer until deployment readiness.

## Goals / Non-Goals

- Render all content at build time and enhance one decorative scene with Three.js.
- Keep the output portable to any static host and keep destination configuration at build time.
- Do not share product UI components or add an authentication runtime.

## Decisions

- Use a separate `marketing/` Vite + TypeScript project with static HTML and an independent lockfile. It is a build tool, not a route in the product Vite app. Astro would add a framework for a single page; plain unbundled HTML would complicate typed scene code and dependency builds. Record the lasting boundary in ADR 0006.
- Use the existing purple Playfair wordmark, warm paper, near-black typography, and an oversized ribbon connecting three report-like forms. The reference sites inform scale, dimensionality, and pointer response; the page keeps Rescribo's own identity and workflow.
- Use GSAP ScrollTrigger to map native scroll progress to 3D rotation, camera distance, and card separation, plus small workflow and heading translations. Do not pin the whole page or replace native scrolling. Keep orchestration in a separate scroll module; the existing scene owns rendering and motion permission. The pause control stays reachable through the page.
- HTML owns the copy, links, static SVG fallback, and motion control. The dynamically imported Three.js scene owns graphics and motion permission; a separate GSAP module owns scroll orchestration. Render once under reduced motion, pause on request, stop when hidden/offscreen, and dispose resources on teardown. Do not hijack scroll or use custom cursors.
- Describe the intended shipped workflow in present tense; omit development badges and status notes. Keep one copy source module with attribution to README and `openspec/config.yaml`; inject it into HTML at build time. Do not claim the current ranker meets its gate or imply automatic customer messaging.
- Present Rescribo as self-hosted, with the project repository as the adoption destination. The public marketing site has no application sign-in link. The optional canonical URL must use HTTPS when supplied; omit canonical metadata when absent.
- Browser checks run on built output and cover semantic links, mobile overflow, axe, keyboard pause, preference changes, JavaScript-disabled navigation, and graphics fallback. Build probes check synthetic canonical HTTPS URLs; CI checks the public site.

## Risks / Trade-offs

- GPU cost and motion sensitivity: cap pixel ratio, keep geometry bounded, pause offscreen, and keep a static fallback.
- Copy drift: isolate and attribute sourced copy; review it alongside product changes.
- Unselected host: produce portable `dist/`; keep release and live-link checks pending until URLs and hosting are chosen.

## Migration Plan

The independent CI build checks every PR. After site review, choose hosting and URLs, run the release build and live link checks, publish only with maintainer authorization, and record the verified destination. Rollback replaces the host's artifact with the prior static build. No product migration is required.

## Open Questions

- Static host and marketing domain, deferred by the maintainer.
