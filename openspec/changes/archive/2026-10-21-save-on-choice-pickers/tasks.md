# Tasks

## 1. Popover and toast primitives

- [x] 1.1 Add shadcn `popover` to `components/ui/popover.tsx` from the existing `radix-ui` package; verify `npm run typecheck` passes.
- [x] 1.2 Install `sonner` and add shadcn `sonner` to `components/ui/sonner.tsx`, with the theme from `useThemePreference`/`resolveTheme` instead of `next-themes` and tokens `bg-popover`, `text-popover-foreground`, `shadow-elevation-3`; verify `package.json` and `package-lock.json` both change and `npm run build` passes.
- [x] 1.3 Mount `<Toaster />` in `main.tsx`, bottom-right on desktop and bottom-center above the phone navigation; verify with a unit test that `toast.success` renders in a polite live region without moving focus.

## 2. Shared member picker

- [x] 2.1 Build `components/member-picker/member-picker.tsx` as in design.md (trigger with `role="combobox"`, Popover + Command, empty choice, current member kept when unlisted, unavailable members, `note`, `error`, `pending`, `onChoose` promise, `onClose`); verify unit tests in `member-picker.test.tsx` for: filter by name, choose resolves and closes with focus on the trigger, choose rejects and stays open, Escape closes without calling `onChoose`, choices blocked while pending, unlisted current member shown, unavailable member not choosable, members error shows retry.

## 3. Optimistic mutation hooks

- [x] 3.1 Add `patchReport` to `api/cache.ts` and make `applyReport` use it (only after the coordinator approves editing the shared file; see plan question 2); verify existing `api` and inbox tests still pass.
- [x] 3.2 Add the `optimistic` option to `useReportMutation`, `useProblemMutation`, and `useFollowUpMutation` (`onMutate` snapshot and patch, `onError` restore then apply the 409 record); verify unit tests for each: the cache shows the new value before the request resolves, a network error restores the old value, a 409 ends with the server's record.

## 4. Replace the three forms

- [x] 4.1 Replace `AssignReportForm` with a `ReportAssigneePicker` used by inbox triage (outline trigger, warning under it and as `note`) and by `ReportAssigneeEditor` (ghost trigger, no Change/Done toggle, warning as `note`); toast "Assigned to <name>" or "Unassigned"; update `report-actions.test.tsx` and `problems-page.test.tsx` for save on choice, rollback, conflict, and the warning visible before choosing.
- [x] 4.2 Replace `OwnerCard`'s toggle and `OwnerForm` with the picker (ghost trigger, "No owner"); toast "Owner set to <name>" or "No owner"; update `problems-page.test.tsx`.
- [x] 4.3 Replace the select and button in `RecipientForm` with the picker (no empty choice, members without a Slack link unavailable, refetch members on error); toast "Recipient changed to <name>"; update `follow-up-recipient-form.test.tsx`, including the `recipient_not_linked` message shown in the open picker.
- [x] 4.4 Remove code the forms no longer use (`SelectField` imports, `choice` state, Save button labels); verify `npm run lint` and `npm run typecheck` report nothing unused.

## 5. End-to-end and docs

- [x] 5.1 Update `e2e/report-triage.spec.ts`: reassign from a linked report row by choosing, see the toast, see the row text change; phone touch-target loop uses the new trigger names and an open picker option; no horizontal scroll with the picker open.
- [x] 5.2 Update `e2e/follow-ups.spec.ts` so the recipient test opens the picker and checks that a member without a Slack link is unavailable and the owner is choosable.
- [x] 5.3 Check `e2e/inbox.spec.ts` and `e2e/motion.spec.ts` still pass. Add the reduced-motion toast check to `e2e/report-triage.spec.ts` (`motion.spec.ts` is shared): with reduced motion on, the toast has no running animation or transition.
- [x] 5.4 Add "Toasts" and "Member picker" sections to `frontend/DESIGN.md` without rewording existing text; verify `git diff frontend/DESIGN.md` shows only added lines.

## 6. Repository checks

- [x] 6.1 Run `npx @fission-ai/openspec validate --all --strict` and verify it passes.
- [x] 6.2 With PostgreSQL and Redis running, run `task check test build schema-check` and verify every task passes.
- [x] 6.3 Run `RESCRIBO_E2E_API_PORT=8200 RESCRIBO_E2E_FRONTEND_PORT=5200 task e2e` and verify it passes.
- [x] 6.4 Take after screenshots with `shots.mjs` into `.claude/shots/after` and build `.claude/shots/compare.html` with `compare.py`.

## Workflow follow-up

- Archive the change in the PR that completes it.
