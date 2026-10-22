# Proposal

Delivers GitHub issue #220 (milestone G. Manual check findings).

## Why

Some component tests fail when the machine is loaded. The cost is in how they wait: a `findByRole` with a `name` runs a role and accessible-name pass over the page on every DOM change and every 50 ms poll. Under load those passes fill the 1000 ms `findBy` budget, and in long tests they add up to the 5000 ms test timeout.

## What Changes

- The inbox page test "lists reports and sends search and filter changes to the API" waits for the first row and the assignee option with `findByText`, then checks the list by role once.
- The recipient form tests wait for the recipient picker and its options with cheap queries, then check each by role once.
- The command palette tests wait for the open dialog through its search input placeholder, then check the dialog by role once.
- The settings test "members see connections but no owner controls" waits for its heading with `findByText`, then checks the heading by role once. It failed at the agreed load, so it is in scope.
- Markdown and follow-up outcome tests are unchanged: they did not fail at the agreed load.

No app code, API, `frontend/openapi.yaml`, or spec change. The change sets `skip_specs: true`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. Tooling only.

## Impact

- `frontend/src/features/inbox/inbox-page.test.tsx`
- `frontend/src/features/follow-ups/follow-up-recipient-form.test.tsx`
- `frontend/src/components/command-palette/command-palette.test.tsx`
- `frontend/src/features/settings/settings-page.test.tsx`
