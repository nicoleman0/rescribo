# Design

## Context

`ConnectionSettings` renders one card per provider. Both cards share one setup form, which posts `body: { repository, consent }` to `connections/{provider}/setup/`. `repository` state starts as `connection?.repository ?? ''`. Only the GitHub card renders the repository field, so for Slack the value is always `''`, on first connect and on reconnect.

`SetupSerializer` (`backend/connections/views.py`) declares `repository` as a `RegexField` with `required=False, default=""`. A missing key is valid. A blank string fails the field's blank check before the default applies, and `api_exception_handler` answers 400 `invalid_request`.

The gap survived because the backend tests post `{"consent": True}` for Slack, and no frontend test submits either connect form.

## Goals / Non-Goals

**Goals:**
- An owner can start Slack setup from Settings, on first connect and on reconnect.
- A test fails if the Slack form sends `repository` again.
- A test fails if the Slack form's body stops passing the real serializer.

**Non-Goals:**
- Backend, API, and `frontend/openapi.yaml`. A blank repository stays invalid.
- Showing field errors for fields a card does not render.
- #144 (no confirmation after "Check status") and #141 (Sign out position).
- Splitting `ConnectionSettings` per provider.

## Decisions

**Build the body by provider.** The body is `{ repository, consent }` for GitHub and `{ consent }` for Slack. The rule "Slack has no repository" is stated once, where the request is built.

Alternatives:
- Drop `repository` whenever it is blank, for both providers. GitHub would then answer `consent_required` with no field error where it answers a `repository` field error today. The browser's `required` attribute blocks a blank GitHub submit in practice, but this would still change GitHub behaviour for no gain.
- Give each provider its own state or form component. It removes the shared `repository` state, but it is a refactor and the maintainer is blocked on this fix.

**Component tests go in `settings-page.test.tsx`.** That file already renders the real page with `stubApi`, and has `owner()` and `slackConnection`. A new file would copy those helpers. The tests render `SettingsPage`, tick the consent box in the provider's card, click the button, and compare the parsed request body with `toEqual`. `toEqual({ consent: true })` fails on any extra key.

Three cases: Slack first connect, Slack reconnect (an active connection, button "Reconnect Slack"), and GitHub with a typed repository. The GitHub case guards against dropping `repository` for both providers.

**The stubbed setup answers 400 `operator_setup`.** On 200 the form calls `window.location.assign`, and jsdom does not implement navigation. The 400 is what the API returns when no OAuth application is configured, so the form stays put and the test can also wait for the error text before reading the request.

**One browser test against the real API.** A stubbed `fetch` cannot tell whether the body passes `SetupSerializer`, which is the contract that broke. The browser test submits the Slack form and asserts two things: the request body equals `{ consent: true }`, and the reply's `reason` is not `invalid_request`.

It does not need Slack credentials. With none, `start_setup` raises `operator_setup` (400) after validation passes. With credentials (a developer's `.env`), the API answers 200 and the form navigates to `slack.com`; the test fulfils `https://slack.com/**` itself so the browser never leaves the machine. Both replies pass the assertions.

It signs in as `seed.users[1]` (owner of `e2e-test`), as the 320px test in the same file does. Login is throttled to 10 per minute per identity; this adds one sign-in for that user.

**Prototyped before planning.** The component tests and the browser test were written, run, and removed:
- Without the fix: both Slack component tests fail on `repository: ""`, the GitHub test passes, and the browser test fails on the body assertion.
- With the fix: 3 of 3 component tests pass and the browser test passes (API replied 400, no credentials).

## Risks / Trade-offs

- [The browser test's reply check is loose: it accepts 200 or 400 and only rules out `invalid_request`] → Accepted. A stricter check would depend on whether the machine has Slack credentials.
- [With Slack credentials configured, the browser test creates one `SetupState` row in the `e2e-test` workspace] → Harmless: it is unused and expires in ten minutes.
- [The Slack card still cannot show a field error for a field it does not render] → Out of scope. See "Decisions to review" in the PR; it may need its own issue.
