# Design

## Context

- `seed-session.ts`: `seedSessionPath(name)` returns `.auth/seed-<name>.json`. `saveSeedSession(browser, baseURL, sessionPath, userIndex = 1)` reads `.auth/seed.json`, signs in from a signed-out page, saves `storageState`, closes the page in `finally`, and returns the seed.
- `follow-ups.spec.ts:14-34` and `report-triage.spec.ts:8-33` hold the same steps for users 5 and 4, saving to `.auth/follow-ups-owner.json` and `.auth/triage-owner.json`.
- `follow-ups.spec.ts` also signs in inline twice: `ensureFollowUpOwner` (user 5, after a redirect to sign-in) and one test's member page (user 7).
- `demo-session.ts`: `signInAsDemo(page)` reads `.auth/demo.json` and runs the same five sign-in steps. `saveDemoSession` opens a signed-out page, calls `signInAsDemo`, saves `storageState`. `themes.spec.ts` calls `signInAsDemo` on its own.
- `playwright.config.ts` runs with `workers: 1`, so specs do not run at the same time today. Unique session files still keep each spec's session independent of run order.

Seed user indexes in use (`seed.users[i]`):

| Index | Users |
|---|---|
| 0 | accounts (password of 0 used with emails 1 and 3) |
| 1 | `saveSeedSession` default: z-product-states; accounts and settings inline |
| 2 | command-palette, theme-tokens (`saveSeedSession`); inbox, fix-release, github-issues inline |
| 3 | accounts |
| 4 | report-triage; settings.spec.ts:271 inline |
| 5 | follow-ups |
| 7 | follow-ups member |
| 8 | ui-foundation |
| 9 | settings-owner |

## Goals / Non-Goals

**Goals:**
- One home for the sign-in steps and the signed-out save of `storageState`.
- Same user per spec: follow-ups 5, report-triage 4.

**Non-Goals:**
- Inline sign-ins in other specs (accounts, inbox, fix-release, github-issues, settings, ui-foundation) and `auth.setup.ts`.
- Changing which user any spec uses.

## Decisions

### Shared core in `session.ts`

`demo-session.ts` can share the core without a new option or flag. The only difference from the seed path is where the credentials come from, so the core takes `{ email, password }`:

- `authDir`
- `signIn(page, credentials)`: goto `/sign-in`, fill Email and Password, click Sign in, expect `/inbox$`.
- `saveSession(browser, baseURL, sessionPath, credentials)`: signed-out page, `signIn`, `mkdir`, save `storageState`, close in `finally`.

`seed-session.ts` and `demo-session.ts` read their own JSON and call the core. Their exported names and signatures stay, so callers do not change.

Alternative: put `signIn` and `saveSession` in `seed-session.ts` and import it from `demo-session.ts`. Rejected because "seed" there means the `seed_test_accounts` output, which the demo user is not part of.

Alternative: leave `demo-session.ts` alone. Leaves a second copy of the same steps and the same throttle workaround, which the issue names.

`saveDemoSession` gains `mkdir` and the `finally` close from the shared core. `auth.setup.ts` already creates `.auth/`, so `mkdir` is a no-op there.

### Session file names

Use `seedSessionPath('follow-ups-owner')` and `seedSessionPath('triage-owner')`. The files gain the `seed-` prefix every other `saveSeedSession` caller has. No other spec uses those names, so each spec still owns its session file. Keeping the exact old names would need the spec to build the path from `authDir` itself, which is the duplication this change removes.

### Remaining sign-ins in `follow-ups.spec.ts`

`seed-session.ts` exports `readSeed()`, which `saveSeedSession` also uses. `ensureFollowUpOwner` and the member sign-in call `readSeed()` and `signIn`. The member page keeps its current `browser.newPage({ baseURL })` options. `signIn` adds a `goto('/sign-in')` to `ensureFollowUpOwner`, which today fills the form on the page it was redirected to. Both paths end on `/inbox`, and the `toHaveURL(/\/inbox$/)` check stays.

### Comments

The deleted copies say "No other spec signs in as this owner or changes its password." That is false for user 4: `settings.spec.ts:271` signs in as user 4. The spec-side comment keeps only what is true: the user index is chosen so no other spec saves a session for it.

## Risks / Trade-offs

- [Every demo spec now runs through the new core] → Run `demo`, `motion`, `themes`, and `ui-foundation` alone, then the full `task e2e`.
- [Login throttle on user 4, shared with `settings.spec.ts:271`] → Unchanged by this change. Flagged for a separate issue if it ever fails.
