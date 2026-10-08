# Tasks

Delivers #122. Layout only; `skip_specs: true`. Change only the elements named below.

## 1. Row layout in `frontend/src/features/problems/problems-page.tsx`

All three edits are inside `ProblemList`, in the `<Link>` for each problem. Leave the `<ul>` (including `stagger-rows`), the `<Link>` classes, the badge components, the GitHub chip's own `<span>`, the summary line, and the owner line unchanged.

- [x] 1.1 On the row span that wraps the title and badges (today `className="flex items-start justify-between gap-3"`), set `className="flex flex-wrap items-start justify-between gap-x-3 gap-y-1.5"`. Verify: `git diff` shows only this attribute changed on that line.
- [x] 1.2 On the title span (today `className="min-w-0 font-medium break-words"`, it renders `{problem.title}`), set `className="min-w-0 grow basis-48 font-medium break-words"`. Verify: `git diff`.
- [x] 1.3 On the badge group span (today `className="flex shrink-0 flex-wrap justify-end gap-1"`), set `className="flex min-w-0 flex-wrap gap-1"`. This removes `shrink-0` and `justify-end`. Verify: `git diff`; `cd frontend && npx prettier --check src/features/problems/problems-page.tsx` passes.

## 2. E2E check in `frontend/e2e/demo.spec.ts`

Add the steps at the end of the existing test `the demo visitor sees labelled, simulated data`, after the Settings assertions. Do not add a new test or a new sign-in: the demo login is throttled to 10 per minute and the suite already uses all 10.

- [x] 2.1 Add the phone check. Use this code:

  ```ts
  // Rows animate in; measure them at rest.
  await page.emulateMedia({ reducedMotion: 'reduce' })
  const title = 'Password reset emails arrive after the link expires'
  const row = page
    .getByRole('list', { name: 'Problems' })
    .getByRole('link', { name: new RegExp(title) })

  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/problems')
  await expect(row).toBeVisible()
  const rowBox = (await row.boundingBox())!
  const titleBox = (await row.getByText(title, { exact: true }).boundingBox())!
  expect(titleBox.width).toBeGreaterThan(rowBox.width * 0.6)
  for (const badge of [
    row.getByText('Needs review'),
    row.getByText('Fix available'),
    row.getByText(/^GitHub #\d+/),
  ]) {
    const box = (await badge.boundingBox())!
    expect(box.x + box.width).toBeLessThanOrEqual(rowBox.x + rowBox.width)
  }
  ```

  Verify: it fails on the title width without task 1 and passes with it. To revert task 1 for that run, do not use `git stash` (it is shared across worktrees). Run `git diff frontend/src/features/problems/problems-page.tsx > .claude/shots/row.patch && git checkout -- frontend/src/features/problems/problems-page.tsx`, run the test, then `git apply .claude/shots/row.patch`.
- [x] 2.2 Add the desktop check directly after 2.1. Use this code:

  ```ts
  await page.setViewportSize({ width: 1280, height: 860 })
  const wideTitle = (await row.getByText(title, { exact: true }).boundingBox())!
  const wideBadge = (await row.getByText('Needs review').boundingBox())!
  // On desktop the badges share the title's first line.
  expect(wideBadge.y).toBeLessThan(wideTitle.y + wideTitle.height)
  expect(wideBadge.x).toBeGreaterThan(wideTitle.x + wideTitle.width)
  ```

  Verify: passes before and after task 1.
- [x] 2.3 Run `cd frontend && RESCRIBO_E2E_API_PORT=8122 RESCRIBO_E2E_FRONTEND_PORT=5122 npx playwright test e2e/demo.spec.ts`. Verify: 1 passed (plus setup).

## 3. Design doc

- [x] 3.1 Append this section at the very end of `frontend/DESIGN.md`. Do not edit any existing text.

  ```markdown
  ## Problems list

  - A row's title keeps at least 12rem. When the badges do not fit beside
    it, they move under the title, left-aligned, and wrap. No breakpoint is
    involved, so the rule holds beside the sidebar and on phones.
  ```

  Verify: `git diff frontend/DESIGN.md` shows only added lines.

## 4. Screenshots

- [x] 4.1 With the dev servers on 8122 and 5122 and the demo seeded (see `.claude/brief.md`), run `SHOTS_BASE=http://127.0.0.1:5122 node .claude/skills/work-issues/scripts/shots.mjs .claude/shots/after`, then build `.claude/shots/compare.html` with `.claude/skills/work-issues/scripts/compare.py`. Verify: `problems-phone-light.png` shows the password reset title on at most two lines with its badges below, and `problems-desktop-light.png` matches the before shot.

## 5. Repository checks

- [x] 5.1 `npx @fission-ai/openspec validate --all --strict` passes.
- [x] 5.2 `task check test build schema-check` passes with PostgreSQL and Redis running. Record the test counts for the PR.
- [x] 5.3 `RESCRIBO_E2E_API_PORT=8122 RESCRIBO_E2E_FRONTEND_PORT=5122 task e2e` passes. Record the counts for the PR.

## Workflow follow-up

- Archive this change in the PR that completes #122 (`/opsx:archive`).
- PR milestone: E. UI polish.
