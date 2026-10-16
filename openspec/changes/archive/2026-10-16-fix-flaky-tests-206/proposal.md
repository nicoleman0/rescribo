# Proposal

Delivers GitHub issue #206 (milestone G. Manual check findings).

## Why

Three tests failed once each on 2026-10-11 and passed on rerun. Each failure has a cause in the test or the seed, not in the app:

- Triage "confirms fixes ... for a late report": the confirm action is a CSRF `GET` followed by the `POST`. The button reads "Recording…" from the click, so `toHaveCount(0)` on "Confirm fix applies" passes before either request finishes. `page.reload()` can then cancel the confirmation before the `POST` is sent.
- Follow-ups "paginates follow-ups ...": the test waits on the right state, but each `*ByRole` poll over the 25-row page costs 17 ms idle and up to 251 ms under load. A few polls fill the 1000 ms `findBy` budget.
- Settings "allows and removes a Slack channel": `seed_test_accounts` keeps the `e2e-test` Slack connection with `update_or_create` and never clears its `AllowedChannel` rows. A run cut off after "Allow channel" leaves `C0E2EPUBLIC` allowed, and the picker hides allowed channels.

## What Changes

- The triage test waits for a successful `confirm-fix-applies` response before it reloads.
- The follow-ups pagination test waits for each new row with `findByText`, then checks the link by role once.
- `seed_test_accounts` deletes the `AllowedChannel` rows of the `e2e-test` workspace on every run. Other workspaces keep theirs.
- A new backend test runs the command twice with a leftover row and checks that the demo and an unrelated workspace keep their rows.

No app code, API, `frontend/openapi.yaml`, or spec change. The change sets `skip_specs: true`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. Tooling only.

## Impact

- `frontend/e2e/report-triage.spec.ts` (one test).
- `frontend/src/features/follow-ups/follow-ups-page.test.tsx` (one test).
- `frontend/e2e/settings.spec.ts` (no change planned; the seed fix covers it).
- `backend/accounts/management/commands/seed_test_accounts.py`.
- `backend/tests/test_seed_test_accounts.py` (new).
