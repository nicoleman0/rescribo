# Proposal

Delivers GitHub issue #146 (milestone G. Manual check findings). Found while diagnosing #145 in the manual end-to-end check (#57).

## Why

A form shows a field error only when it asks for that field by name. A validation reply that names any other field is dropped, and the member sees a generic line such as "Check the submitted fields." or "Check the highlighted fields." with nothing highlighted. The cause can then only be found in the browser's network tools.

#145 removed the one case the product produced (the Slack card sending a blank `repository`). The weakness is in the shared layer, so the next request that sends a field the form does not show will fail the same way.

## What Changes

- A form's error summary shows the errors for fields the form does not render, each on its own line with the field's name: "Repository: This field may not be blank."
- An error shown under its field is not repeated in the summary.
- An error that belongs to no field (`non_field_errors`) shows in the summary without a field name.
- A field error that only repeats the reply's reason code or its message adds no line. The reply's message already says it.
- The shared form layer decides which fields a form rendered. A form does not list its fields again. A field counts as rendered once the form has asked `fieldError` for it.
- Every form reads field errors through `fieldError`. The settings and sign-in forms stop reading `fieldErrors` directly.
- `fieldError` returns the first message for a field everywhere. Three settings fields joined all messages before.
- The manual report form now shows "Enter a title." for the `title_required` code, as the other forms do. It showed the raw code.

No backend, API, or `frontend/openapi.yaml` change.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `web-interface`: adds the requirement "Form errors for fields not shown". No existing requirement is reworded.

## Impact

Owned by this change:
- `frontend/src/components/forms/field-error.ts`
- `frontend/src/components/forms/field-error.test.ts` (new)
- `frontend/src/components/forms/form-error-message.tsx` (new)
- `frontend/src/components/forms/form-error-message.test.tsx` (new)
- `frontend/src/api/request.ts`: no change needed.

Shared files, each a small edit (see `design.md` D6 for the lines):
- `frontend/src/components/states/action-error.tsx` (#157 is in flight on this file)
- `frontend/src/components/states/async-states.tsx`
- `frontend/src/features/settings/connection-settings.tsx` (#148 edits this file later)
- `frontend/src/features/settings/members-settings.tsx`
- `frontend/src/features/settings/confirm-action.tsx`
- `frontend/src/features/inbox/manual-report-page.tsx`
- `frontend/src/pages/sign-in-page.tsx`
- `frontend/src/pages/reset-password-page.tsx`
- `frontend/src/pages/accept-invite-page.tsx`
- `frontend/src/features/settings/settings-page.test.tsx` (one new test)
- `frontend/DESIGN.md` (one new bullet)

Not edited: `frontend/src/features/follow-ups/`, `frontend/src/features/inbox/report-actions.tsx`, and `frontend/src/features/problems/`. They already use `fieldError` and `ActionError`, so they get the behaviour through those two.
