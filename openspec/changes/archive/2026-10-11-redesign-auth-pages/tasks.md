# Tasks

## 1. Public demo offer

- [x] 1.1 Move `DEMO_SLUG` and `VISITOR_EMAIL` into `backend/accounts/demo.py`. In `backend/feedback/demo.py`, replace the two definitions with an import from `accounts.demo` and change nothing else. `backend/tests/test_demo.py` passes unchanged, and neither `accounts/demo.py` nor `accounts/views.py` imports `feedback`. Leave the existing imports in `accounts/management/commands/seed_test_accounts.py` unchanged.
- [x] 1.2 Add `demo_offer()` to `backend/accounts/demo.py` per design decision 1. Unit tests cover: offered, password not configured, demo not seeded, and a non-demo workspace holding the `demo` slug
- [x] 1.3 Add `DemoOfferView` and its serializers to `accounts/views.py` and the route `api/auth/demo/` in `backend/config/urls.py`, with no other edit to that file. API tests cover: 200 without a session or CSRF token in each state, `Cache-Control: no-store`, the reply never contains `OWNER_EMAIL`, and the returned login signs in through `auth/login/`
- [x] 1.4 Run `task schema` and commit `frontend/openapi.yaml` and `frontend/src/api/schema.d.ts`. `task schema-check` passes
- [x] 1.5 Add one line to `docs/LOCAL_DEVELOPMENT.md`: a set `RESCRIBO_DEMO_PASSWORD` on a seeded instance shows the login on the sign-in page, and a changed password needs `task demo-seed`

## 2. Shared layout and controls

- [x] 2.1 Change `Button` size `lg` to `h-10` and drop the `h-10` override in `problems-page.tsx`, with no other edit to either file. `button.test.tsx` asserts the `lg` height class; the problems page create button keeps its height in the after shots
- [x] 2.2 Rework `AuthLayout` per design decisions 6 and 7 with a `title` prop. A component test asserts one `h1` with the title, the wordmark, the product line "Customer feedback. Engineering work. Follow-up.", and the document title
- [x] 2.3 Move the three pages onto the `title` prop, set `size="lg"` and full width on each submit button, and use the destructive `Alert` for submit errors on accept-invite and reset-password. `sign-in-page.test.tsx` and `token-preview-pages.test.tsx` pass, with an added assertion that a rejected invite and a rejected reset show the reply in an alert
- [x] 2.4 Add a "Signed-out pages" section to `frontend/DESIGN.md`: layout, product line home, submit size, demo hint. Do not reword existing text

## 3. Demo hint

- [x] 3.1 Add `getDemoOffer` and its query key to `frontend/src/api/auth.ts`, typed from `schema.d.ts`
- [x] 3.2 Show the hint inside the card, under the form, per design decision 4. Component tests cover: offered shows the email, password, and "Use demo login"; the button fills both fields and focuses Sign in; `null` shows nothing; a failed read shows nothing and sign-in still submits
- [x] 3.3 Export the e2e demo password from one module, import it in `auth.setup.ts`, and pass it to the API server in `playwright.config.ts`, with no other edit to the config
- [x] 3.4 E2E in `accounts.spec.ts` and `demo.spec.ts`: the hint action then Sign in opens the demo inbox; sign-in has no axe violations in light and dark with the hint shown; at 390px the three pages do not scroll horizontally and sign-in controls are at least 44px tall; at 1280px the Sign in button matches the Email input's height and width; an expired invite and an expired reset link show the wordmark and product line. Leave the four Sign out lines in `accounts.spec.ts` as they are

## 4. Checks

- [x] 4.1 `npx @fission-ai/openspec validate --all --strict`
- [x] 4.2 `task check test build schema-check` with PostgreSQL and Redis running
- [x] 4.3 `RESCRIBO_E2E_API_PORT=8202 RESCRIBO_E2E_FRONTEND_PORT=5202 task e2e`
- [x] 4.4 Take the after shots into `.claude/shots/after` with the API dev server started with `RESCRIBO_DEMO_PASSWORD` set to the seed password, so the hint shows. Run `shots.mjs`, then `.claude/shots/auth-shots.mjs` for the invite and reset pages. Restart the API server without the variable and take one sign-in shot with no hint. Build `.claude/shots/compare.html`
- [x] 4.5 Write the PR body per the brief. Under Decisions to review, say that `DEMO_SLUG` and `VISITOR_EMAIL` moved from `feedback/demo.py` to `accounts/demo.py`

## Workflow follow-up

- Archive the change in the PR that completes it.
