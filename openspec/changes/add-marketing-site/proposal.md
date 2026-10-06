# Proposal

## Why

Issue [#53](https://github.com/nicoleman0/rescribo/issues/53) needs a public explanation of Rescribo without shipping the authenticated application. A separate static site lets product copy and visual design ship independently.

## What Changes

- Add `marketing/` with its own static build, lockfile, browser checks, and deployment documentation.
- Explain the existing Capture, Connect, Follow up workflow using README and OpenSpec context copy.
- Add scroll-driven choreography to the Three.js composition and workflow sections.
- Add an interactive Three.js composition, with semantic HTML, reduced motion, a pause control, and a static fallback.
- Present Rescribo as self-hosted and link to the project repository. Keep only optional canonical site URL configuration.
- Add an independent CI job for build, link validation, and axe checks.
- Leave hosting, domain selection, and publication until the site is ready, as requested on 6 October 2026.

## Capabilities

### New Capabilities

- `marketing-site`: Public product explanation, visual enhancement, accessible navigation, and a self-hosted adoption path.

### Modified Capabilities

None. The authenticated application is unchanged.

## Impact

Adds Three.js and a static build tool under `marketing/`, plus a separate CI workflow. No API, database, worker, or product frontend changes. Hosting and domain remain open; this change is not complete until deployment choices and release checks are recorded. Pricing, billing, public signup, and claims about adoption remain out of scope.
