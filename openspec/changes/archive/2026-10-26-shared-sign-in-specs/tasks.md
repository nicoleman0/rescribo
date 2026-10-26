# Tasks

## 1. Shared seed type

- [x] 1.1 Add `expired_invitation_token: string` to `Seed` in `frontend/e2e/seed-session.ts`; verify `npm run typecheck` from `frontend` passes.

## 2. Move the sign-ins

- [x] 2.1 `accounts.spec.ts`: use `readSeed()` in every test that read `seed.json`; replace the sign-ins at lines 120, 171, and 226 with `signIn(page, seed.users[3])`, `signIn(page, seed.users[0])`, and `signIn(page, seed.users[3])`; leave lines 21, 159, 211, and 299 inline; delete `seedPath`, `Seed`, and unused imports. Verify `git diff` shows no test or assertion removed or reordered, and the spec passes alone.
- [x] 2.2 `settings.spec.ts`: in the four tests after the describe block, replace the seed read and sign-in with `readSeed()` and `signIn(page, seed.users[1])` (three tests) or `seed.users[4]` (Slack channel picker); keep the viewport call before sign-in in that test; delete `authDir` and unused imports. Verify as in 2.1.
- [x] 2.3 `seed-session.ts`: export `signInAsSeededOwner(page)` built on `readSeed()` and `signIn(page, seed.users[2])`. Put the fixed-credentials rationale here once.
- [x] 2.4 `inbox.spec.ts`: call `signInAsSeededOwner` from `beforeEach`; keep the inbox title check after the call; remove the private wrapper and local seed reads. Verify as in 2.1.
- [x] 2.5 `fix-release.spec.ts` and `github-issues.spec.ts`: call `signInAsSeededOwner` directly at the one and two prior call sites; remove private wrappers and seed reads. Verify as in 2.1 for each spec.
- [x] 2.6 `ui-foundation.spec.ts` 'user menu signs out': replace the seed read and form steps with `signIn(page, (await readSeed()).users[8])` in the same clean context; delete `authDir`, `seedPath`, and unused imports. Verify as in 2.1.
- [x] 2.7 Verify `grep -nE "seed.json|getByRole\('button', \{ name: 'Sign in' \}\)\.click" frontend/e2e/*.spec.ts` finds only the four kept accounts sign-ins, `demo.spec.ts`, and lines in `follow-ups.spec.ts` or `motion.spec.ts`.

## 3. Repository checks

- [x] 3.1 Run `task check test build schema-check` with PostgreSQL and Redis running; all pass.
- [x] 3.2 Run `RESCRIBO_E2E_API_PORT=8242 RESCRIBO_E2E_FRONTEND_PORT=5242 task e2e`; all pass. Record the pass count; the diff has no test declarations, so the count is unchanged from before the change.
- [x] 3.3 Run `npx @fission-ai/openspec validate --all --strict`; it passes.

## Workflow follow-up

- In the PR, list each changed spec with its count and each kept inline sign-in with its reason. Say `follow-ups.spec.ts` and `motion.spec.ts` were left alone.
- Archive the change in the PR that completes it.
