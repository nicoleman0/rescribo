# Design

## Context

Three forms do the same job with a `SelectField` and a Save button: `AssignReportForm` (`features/inbox/report-actions.tsx`, reused by `features/problems/report-assignee-editor.tsx` on each linked report row), `OwnerForm` (`features/problems/problem-detail-page.tsx`, inside `OwnerCard`'s Change/Cancel toggle), and `RecipientForm` (`features/follow-ups/follow-up-recipient-form.tsx`). Each keeps a local `choice` and saves through its feature's mutation hook (`useReportMutation`, `useProblemMutation`, `useFollowUpMutation`). On a 409 those hooks write the server's current record into the cache. None of them updates the cache before the reply.

`components/ui/command.tsx` (from #199) wraps `cmdk`. `radix-ui` already ships Popover. `sonner` is not installed.

Report copies live in two caches: `reportKeys.detail` and the problem detail's linked-report pages. `applyReport` in `api/cache.ts` already knows both.

## Goals / Non-Goals

**Goals:**

- One picker component, three thin callers.
- Optimistic update and rollback inside the existing mutation hooks, so callers do not repeat cache code.

**Non-Goals:**

- The inbox filter bar's assignee select, `CreateProblemPanel`'s owner select, and `ConfirmPanel`. They are filters or draft fields, not saves.
- Optimistic rows in the inbox, problems, and follow-ups lists. They refresh from the existing invalidation after the save.

## Decisions

### Shared `MemberPicker` in `components/member-picker/`

A presentational component built from shadcn `Popover` and `Command`. Props:

- `label` (visible text, also the trigger's accessible name), `value` (member id or `''`), `members` (the directory query result), `current` (the record's member, so a member who left is still listed), `emptyLabel` (`"Unassigned"`, `"No owner"`, or absent for recipient), `isUnavailable` (recipient: no Slack link), `note` (text shown at the top of the open picker), `error` (a node, the caller's `ActionError`), `pending`, `triggerVariant`.
- `onChoose(id) => Promise<unknown>`. The picker awaits it. Resolve closes the popover and returns focus to the trigger. Reject keeps it open; the caller renders the error from its mutation state, so the rejection is handled, not swallowed.
- Closing the popover calls `onClose`, which the caller uses for `mutation.reset()`.
- Members loading and members failing render inside the list (`ErrorState` with retry for the failure, as today).

It does not import from `features/`. It shows `member.display_name` directly; `memberName` in `features/inbox/report-format.ts` is the same field, and the picker cannot depend on a feature.

Trigger: a `Button` with `role="combobox"`, `aria-expanded`, and a chevron, showing the current member or the empty label. On problem detail it uses the ghost variant and sits where the value text was, so the row and the owner card still read as text. The Change/Done and Change/Cancel toggles go away: opening the popover is the "member asks to change it" step, and the popover staying open on failure keeps the trap from `report-assignee-editor.tsx` covered.

Alternative: keep each toggle and put an inline `Command` list under it. Rejected: it keeps two steps and a second open/close state per caller.

### Optimistic updates in the mutation hooks

Each hook takes an optional `optimistic` option: the record id and `(record, input) => record`. When given:

- `onMutate`: cancel the record's queries, snapshot every cache entry that holds the record, write the patched copy, return the snapshot.
- `onError`: restore the snapshot, then apply the 409 record if there is one (existing behaviour).
- `onSuccess`: unchanged; the server reply replaces the optimistic copy, including its new `version`.

The patch for the report needs both report caches. Add `patchReport(client, workspaceId, reportId, fn)` to `api/cache.ts` next to `applyReport`, and make `applyReport` use it, so "where report copies live" stays in one place. The coordinator approved editing `api/cache.ts`; `patchReport` returns an undo function, and `patchQuery` does the same for one record. Problem and follow-up only patch their detail key.

The optimistic copy keeps the old `version`. The picker blocks a second choice while pending, so no request goes out with a stale optimistic version.

### Toasts with shadcn Sonner

- `components/ui/sonner.tsx` from the shadcn registry. Its `next-themes` import is replaced with `useThemePreference` and `resolveTheme` from `lib/theme.ts`. Styled with `bg-popover`, `text-popover-foreground`, `shadow-elevation-3`, control radius.
- `<Toaster />` mounts in `main.tsx` beside `<App />`. Position bottom-right; on phones bottom-center with an offset above the fixed bottom navigation.
- Callers call `toast.success(...)` from their mutation's `onSuccess`. Text: "Assigned to Ana" / "Unassigned", "Owner set to Ana" / "No owner", "Recipient changed to Ana".
- Sonner renders a polite `aria-live` region and does not move focus. Its own CSS turns off movement under `prefers-reduced-motion`; `e2e/motion.spec.ts` checks it.

### Callers

- Inbox triage: `AssignReportForm` becomes `ReportAssigneePicker` with the outline trigger and the cancellation warning both under the trigger (as today) and as the picker's `note`.
- Problem row: `ReportAssigneeEditor` renders the same `ReportAssigneePicker` with the ghost trigger. The warning shows as the `note`.
- Owner card: `OwnerForm` and the toggle become the picker in the card body.
- Recipient: `RecipientForm` keeps its heading and owner-only note, and swaps the select and button for the picker. It keeps refetching members on error.

### DESIGN.md

Add two sections and leave existing text alone: "Toasts" (a toast confirms a save made without a separate step; failures, warnings, and anything needing action stay inline; one line naming the result; elevation 3; never takes focus) and "Member picker" (the one way to choose a member for a saved field). The `/dev/ui` gallery is outside this change's paths and stays as it is.

## Risks / Trade-offs

- [Save on choice removes the review step before a side effect: a new assignee or recipient cancels an unsent notification] → The warning shows in the open picker before the choice, and the toast confirms what changed.
- [Popover on phones near the bottom navigation] → Radix collision handling plus the e2e phone check for overflow and touch targets.
- [Optimistic copy briefly disagrees with list rows] → Lists refresh from the existing invalidation after the save.
- [Tests that drove `selectOption` and Save buttons] → Rewritten for the picker in the same change.

## As built

- The picker takes the members query itself (`MembersSource`) instead of separate loading and error props, and exports `MemberPickerError`, which shows a field error and the `ActionError` together in the open picker.
- The trigger's accessible name is `<label>: <current member or empty label>`. On a problem row the label is `Assignee for <report title>`.
- Choosing the member already shown closes the picker without a request. Closing is ignored while a save runs.
- The recipient form is a `section` named "Change recipient", not a form, since it has no submit.
- Sonner's own CSS does turn off movement under reduced motion. The e2e check in `report-triage.spec.ts` confirms no running animation and a `0s` transition.
- jsdom lacks `ResizeObserver` and `scrollIntoView`, which cmdk reads. `components/member-picker/test-support.ts` stubs them; the shared `src/test/setup.ts` is unchanged.
