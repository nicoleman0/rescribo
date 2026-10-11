# Design

## Context

- `AuthLayout` is a centred `max-w-md` raised card holding the wordmark. Each page repeats its own `PageTitle` and `h1`.
- `Button` default is `h-8` and `Input` is `h-10`. `lg` is `h-9`. No shared button size matches an input. `problems-page.tsx` already works around this with `size="lg" className="h-10"`.
- `is_demo` reaches the browser only inside the session, after sign-in.
- The server stores the visitor password hashed. It can publish a password only when `RESCRIBO_DEMO_PASSWORD` is set. Without it, `seed_demo` generates one and prints it once.
- `feedback` depends on `accounts`, never the reverse. `DEMO_SLUG` and `VISITOR_EMAIL` sit in `feedback/demo.py` today. `backend/tests/test_demo.py` is their only caller outside that file and imports them from `feedback.demo`.
- Playwright matches accessible names by substring. Every e2e spec and `shots.mjs` find the button with `{ name: 'Sign in' }` and the field with `getByLabel('Password')`.
- The `web-interface` spec and `DESIGN.md` name "the sign-in card" as a raised panel. Shared spec text must not be reworded.
- `marketing/` is a separate package. It holds the phrase "Customer feedback. Engineering work. Follow-up." as literal HTML in `marketing/index.html` and shares no code with `frontend/`.

## Goals / Non-Goals

**Goals:**
- One layout component owns the wordmark, the product line, the page title, and the heading.
- One fact, one home: the password in settings, the demo slug and visitor email in `accounts.demo`, the app's product line in `auth-layout.tsx`.
- Sign-in keeps working when the demo offer read fails.

**Non-Goals:**
- Colour tokens, the signed-in shell, new shadcn components.
- Changes to login, invitation, or reset behaviour.
- Checking that the configured password still matches the stored hash.
- Sharing the product line between `marketing/` and `frontend/`. They are separate builds.

## Decisions

1. **Offer rule: password configured and demo workspace exists.** `demo_offer()` lives in `backend/accounts/demo.py`. It returns the visitor email and `settings.RESCRIBO_DEMO_PASSWORD` when the setting is non-empty and a workspace with `DEMO_SLUG` and `is_demo=True` exists, else `None`. No hash check.
   - `DEMO_SLUG` and `VISITOR_EMAIL` move to `accounts/demo.py`, which is already the single answer about the demo workspace.
   - `feedback/demo.py` replaces the two definitions with an import from `accounts.demo`, so `feedback.demo.DEMO_SLUG` and `feedback.demo.VISITOR_EMAIL` still resolve. Nothing else in that file changes.
   - `accounts` imports nothing from `feedback`.
   - Password only: publishes a login that does not work on an unseeded instance.
   - Also verify the hash: one password hash per unauthenticated request. Rejected for cost. The gap is a password changed in the environment and not reseeded; the nightly reset closes it.

2. **New endpoint `GET /api/auth/demo/`.** `DemoOfferView` in `accounts/views.py`, `AllowAny`, no authentication classes, like `CsrfView`. Reply: `{"credentials": {"email", "password"}}` or `{"credentials": null}`. One nullable field, so "offered" has no second flag to disagree with. A typed serializer feeds the generated contract; `auth.ts` reads the type from `schema.d.ts`.
   - `auth/csrf/` returns 204 with no body and is called before every write. Adding a body changes its contract.
   - `auth/session/` needs a session. Health and the development status page are ruled out by `AGENTS.md`.

3. **No throttle.** The read costs one indexed `exists()` query, hashes nothing, and returns a value the operator chose to publish. There is no secret to guess. The login it leads to keeps `LoginIdentityThrottle` and `LoginAddressThrottle`. The token preview views are also unthrottled. The reply sets `Cache-Control: no-store` so a proxy does not serve a rotated password.

4. **Hint fills the form.** Inside the card, under the form, the sign-in page shows "Try the demo. Its data is fictitious.", the email and password as plain text in Geist Mono, and an outline button "Use demo login". The button sets both fields and moves focus to Sign in. Sign-in stays one code path, so throttling and errors show in one place.
   - The button name must not contain "Sign in", and no hint element may be labelled "Email" or "Password". That keeps the e2e and `shots.mjs` locators unique.
   - The query uses `retry: false`. Pending, error, and `null` all render nothing.
   - The hint lives in `sign-in-page.tsx`. It has one caller.

5. **Submit height comes from the shared `Button`.** Change `lg` from `h-9` to `h-10` in `button.tsx` and use `size="lg" className="w-full"` on the three pages. Remove the `h-10` override in `problems-page.tsx`, the only other `lg` caller, which then renders the same. Those are the only edits to those two files.
   - `size="lg"` unchanged: 3px shorter than the inputs at the 13px root. Does not meet the issue.
   - A one-off `h-10` class per page: ruled out by the brief.

6. **Layout.** `AuthLayout` takes `title` and `children`. It renders `PageTitle`, the brand block (wordmark and product line as a `p`), and the raised card with the `h1`.
   - At `lg` and up: two columns centred in the viewport, brand block left, raised card right.
   - Below `lg`: one column, brand block above the card.
   - The card keeps `surface-raised` and `shadow-elevation-2`, so the existing "Raised panels stand apart" requirement holds unchanged.
   - Existing tokens only. No new component under `components/ui/`.

7. **Product line: "Customer feedback. Engineering work. Follow-up."** This is the marketing page's eyebrow. The constant lives in `auth-layout.tsx`, because `marketing/` is a separate build with the phrase in static HTML.

8. **One error presentation.** Accept-invite and reset-password show submit errors in the destructive `Alert` that sign-in already uses. The conditions that decide when an error shows do not change.

9. **E2E needs the password on the API server.** `playwright.config.ts` passes `RESCRIBO_DEMO_PASSWORD` to the API web server. The default moves to one exported constant that `auth.setup.ts` and the config both import.

## Risks / Trade-offs

- An operator sets `RESCRIBO_DEMO_PASSWORD` on a seeded instance and the login appears on the sign-in page → the setting already means "published"; `docs/LOCAL_DEVELOPMENT.md` gains one line saying so.
- Password changed in the environment without a reseed → the hint shows a login that fails until the 03:00 UTC reset. The docs line says to run `task demo-seed` after a change.
- `demo_offer()` and `reset_demo()` each test that the demo workspace exists → the rule is short and both read `DEMO_SLUG` from one home. Folding them together means a wider edit to `feedback/demo.py` than this change is allowed.
- The product line exists in `marketing/index.html` and in `auth-layout.tsx` → two builds, no shared module. A reworded line needs both edits.
- With the password set for e2e, every spec's sign-in page shows the hint → decision 4 keeps the locators unique; the full e2e run proves it.
- #197 and #198 merge first → rebase before the after shots. `button.tsx`, `DESIGN.md`, and `frontend/e2e/accounts.spec.ts` are the likely conflicts. #198 changes four Sign out lines in `accounts.spec.ts` to a `signOut(page)` helper, so this change leaves those lines alone.
