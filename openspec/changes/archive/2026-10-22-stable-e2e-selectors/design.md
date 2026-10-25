# Design

## Context

### `ui-foundation.spec.ts:25`, "shell at desktop width"

`getByRole('heading', { name: 'Follow-ups' })` matches any heading whose name contains "follow-ups", case-insensitive. When the workspace has no follow-ups, `EmptyState` renders an `h1` "No follow-ups yet" (`frontend/src/components/states/async-states.tsx`), so two headings match and strict mode fails. Whether the empty state shows depends on what earlier specs left in the workspace.

### `settings.spec.ts:9`, "owner manages invitations, members and confirmed deletion on desktop and mobile"

The failure is the 30 second test timeout under CPU load. It is not a selector, a race, or the Vite cache.

Reproduction in this worktree (api 8221, web 5221, HMR off as `task e2e` runs it, `--trace=on`). Load average was 49 to 67 on 10 cores from parallel worktree sessions.

| Run | Vite cache | Result | Duration |
| --- | --- | --- | --- |
| Full suite | cold | passed | 15.7s (slowest test in the suite) |
| Settings spec only, HMR on | cold | passed | 28.6s |
| `settings.spec.ts:9` cold1 | cold | passed | 9.3s |
| warm1 | warm | failed: "Test timeout of 30000ms exceeded." | 42.9s |
| cold2 | cold | failed: "Test timeout of 30000ms exceeded." | 36.5s |
| warm2 | warm | passed | 11.2s |

What the traces show:

- No single step stalls. The slowest step in a failing run took 2.8s (`goto /settings/members`).
- Every kind of step is slower in the failing runs. Page evaluates: 182 took 13.9s in warm1, 215 took 2.5s in cold1. `toHaveURL`: 24 took 5.6s in warm1, 26 took 1.0s in cold1.
- The time goes to the volume of work: sign-in, invitation, a second page that accepts it, 10 settings section visits (5 sections at 390px and 320px, each with an overflow check, a touch-target scan of every control, and an axe run), two more axe runs and full-page screenshots, then report and workspace deletion.
- The cold cache is not required: warm1 failed too. With HMR on and a cold cache, Vite logged no dependency re-optimization and no reload. #223 has since turned HMR off for Playwright runs in any case.

The run in #221 kept no error output, so I cannot prove it hit the same timeout. It is the only failure this test showed in seven runs here.

## Goals / Non-Goals

**Goals:**

- Each test matches only the element it means.
- No test needs more than a third of the default timeout on an unloaded machine.

**Non-Goals:**

- Raising timeouts, `test.slow()`, or retries (decided in the issue notes).
- App code. The empty state renders a second `h1` on the page; that is noted below, not changed.
- Vitest tests (#220) and `theme-tokens.spec.ts` (#225).
- Other specs with the same pattern, listed below.

## Decisions

### 1. Exact heading name in `ui-foundation.spec.ts:29` and `follow-ups.spec.ts:283`

Use `getByRole('heading', { name: 'Follow-ups', exact: true })` in `ui-foundation.spec.ts`, and `{ level: 1, name: 'Follow-ups', exact: true }` in `follow-ups.spec.ts` on the `?bucket=needs_approval` assertion. Approved in `.switchyard/answers/plan.md`.

- Alternative: `level: 1`. Rejected for `ui-foundation.spec.ts`: `EmptyState` titles are also `h1`, so the level does not separate them. `follow-ups.spec.ts` already pins `level: 1`; that still does not separate it from the "No follow-ups waiting for approval" `h1`, so `exact: true` carries the fix.

### 2. Split the settings journey into a serial block

Wrap the journey in `test.describe('Settings owner journey', ...)` with `test.describe.configure({ mode: 'serial' })`. A `beforeAll` signs in `seed.users[9]` with `saveSeedSession(browser, baseURL, seedSessionPath('settings-owner'), 9)` and the block uses that storage state. The member's own page passes `storageState: { cookies: [], origins: [] }`: Playwright applies describe-level `test.use()` options to `browser.newPage()` contexts too, so without the empty state the member starts with the owner's session, and the accept's login rotates that session, deleting the owner's row. Tests, in order, with assertions moved as they are:

1. Owner keeps one active owner and invites a member who sees only member settings (current lines 24 to 61).
2. Settings sections fit, meet touch targets and pass axe at 390px.
3. The same at 320px. Tests 2 and 3 come from one `for (const width of [390, 320])` loop, so the check is written once.
4. Members page lists the new member on desktop and mobile, and the owner promotes them (current lines 87 to 108).
5. Owner deletes a report, then the workspace, after typed confirmation (current lines 109 to 141).

Why serial: tests 4 and 5 depend on state from earlier tests. Serial mode skips the rest when one fails, so a failure reports once, at its cause. The file already runs with one worker.

The four other tests in `settings.spec.ts` stay as they are and after the block, so they still run after the workspace deletion as they do today.

- Alternative: `test.slow()`. Rejected by the issue notes.
- Alternative: drop the 390px sweep and keep 320px. Halves the cost but removes coverage of five sections at 390px that no other spec checks (`z-product-states.spec.ts` checks only `/settings`). Not chosen without a maintainer answer.
- Alternative: split only the sweep out. Fewer tests, but the rest of the journey still holds two axe runs, two full-page screenshots, and both deletions in one budget. The full split costs one sign-in in `beforeAll`.

## Risks / Trade-offs

- [Serial tests share state] → `mode: 'serial'` makes the dependency explicit and stops after the first failure.
- [A heavily loaded machine can still stretch one test past 30s] → each part now does a fifth of the work. A timeout under that load would be an environment problem, not this test.
- [`seed.users[9]` sign-in now happens in `beforeAll`] → `saveSeedSession` is the helper `ui-foundation.spec.ts` already uses.

## Same pattern in other specs

Non-exact string names that are a substring of another accessible name of the same role the page can show.

- `follow-ups.spec.ts:283`: fixed in this change (decision 1), approved in `.switchyard/answers/plan.md`.
- `ui-foundation.spec.ts:152`: `getByRole('link', { name: 'Problems' }).first()`. `.first()` hides the ambiguity; on `/inbox` only the nav link matches today. Not changed in this change.
- `ui-foundation.spec.ts:31` and `:108`: `getByRole('link', { name: 'Settings' })`. "Open workspace settings" is a link, but only on the GitHub issue form, not on `/follow-ups`. No clash today. Not changed in this change.

Checked and safe: `github-issues.spec.ts:189` (scoped and `level: 5`), `themes.spec.ts:59` (the error-state title is not a heading), `ui-foundation.spec.ts:253` (scoped to the breadcrumb). 450 non-exact string locators exist in total; most are labels and buttons with unique names.

## Noted, not changed

- `EmptyState` renders its title as an `h1`, so an empty list page has two `h1` elements. App code; ask before changing.
