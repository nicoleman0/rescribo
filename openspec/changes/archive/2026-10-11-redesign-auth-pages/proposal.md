# Proposal

## Why

Sign-in, accept-invite, and reset-password are a small card on an empty page, and the submit button is shorter than the inputs above it. A visitor to a demo instance gets no sign of the demo login on the page. Delivers #202.

## What Changes

- One shared layout for the three signed-out pages: the wordmark and one line about the product beside the form card on desktop, and above it on phones.
- The submit action on each page is as tall as the inputs and spans the form.
- A public, unauthenticated API read reports whether the instance offers a demo and, when it does, the published visitor login.
- The sign-in page shows a demo hint when a demo is offered: the visitor email and password, and a button that fills the form.
- The three pages show a failed submit in the same alert.

## Capabilities

### New Capabilities

### Modified Capabilities
- `web-interface`: adds the shared signed-out layout and the demo sign-in hint
- `demo-workspace`: adds the public demo offer

## Impact

- Backend: one view and serializer in `backend/accounts/views.py`. `backend/accounts/demo.py` gains `demo_offer()` and becomes the home of `DEMO_SLUG` and `VISITOR_EMAIL`.
- Contracts: `frontend/openapi.yaml` and `frontend/src/api/schema.d.ts`, regenerated.
- Frontend: `auth-layout.tsx`, the three pages, `frontend/src/api/auth.ts`, and their tests.
- Shared files, each edit approved and limited to this:
  - `backend/feedback/demo.py`: the two constants become an import from `accounts.demo`.
  - `backend/config/urls.py`: one route.
  - `frontend/src/components/ui/button.tsx`: `lg` becomes `h-10`.
  - `frontend/src/features/problems/problems-page.tsx`: the `h-10` override goes.
  - `frontend/playwright.config.ts`: the demo password reaches the API server.
  - `frontend/DESIGN.md`: one new section.
  - `docs/LOCAL_DEVELOPMENT.md`: one line.
- No migration. No new dependency.
