# Proposal

## Why

Issue #200. The report assignee, problem owner, and follow-up recipient are each a native select beside a Save button that stays disabled until the value changes. The problem page and report panel repeat this form, the list is not searchable, and a save gives no confirmation.

## What Changes

- One shared member picker replaces the three select-and-save forms. It opens from a trigger that shows the current member, searches by name, and saves when the member chooses. The Save assignee, Save owner, and Change recipient buttons go away.
- The picker keeps the "Unassigned" and "No owner" choices, and keeps listing a current member who is no longer in the members list. The recipient picker marks members without a Slack link as unavailable, as the select does today.
- The choice shows at once through an optimistic update and rolls back when the save fails. A failed save keeps the picker open with its error. A version conflict rolls back and shows the latest version, as `ActionError` does today.
- A successful save shows a toast. This is the first toast in the app. `frontend/DESIGN.md` gets a Toasts section on what earns a toast and what stays inline.
- The assignee warning about cancelled notifications is visible before the member chooses.
- On problem detail, the owner card and each linked report row show the picker trigger in place of the Change toggle and inline form.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `web-interface`: adds the save-on-choice member picker, its rollback and failure behaviour, the save toast, and the pre-choice assignee warning; changes "Compact linked reports" so the row opens the picker instead of an inline form.

## Impact

- Frontend: `features/inbox/report-actions.tsx`, `features/problems/report-assignee-editor.tsx`, `features/problems/problem-detail-page.tsx`, `features/follow-ups/follow-up-recipient-form.tsx`, and the three mutation hooks; a new `components/member-picker/`; new shadcn `components/ui/popover.tsx` and `components/ui/sonner.tsx`; the `Toaster` in `main.tsx`.
- New dependency: `sonner`. Popover comes from the existing `radix-ui` package.
- No API, schema, or migration change.
- Unit tests for the three forms and the e2e specs for inbox, report triage, problems, and follow-ups change with the controls.
