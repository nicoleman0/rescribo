# Design

## Context

- `apiRequest` (`frontend/src/api/request.ts`) copies the reply's `field_errors` to `ApiError.fieldErrors` and its `detail` to `error.message`. Nothing is dropped there.
- `fieldError(error, field)` (`frontend/src/components/forms/field-error.ts`) returns the first message for one field. The problem, inbox, and follow-up forms use it. The settings forms, the manual report form, and the three sign-in pages read `error.fieldErrors` directly.
- Summaries differ by screen:
  - `ActionError` (problems, inbox, follow-ups) maps `invalid_request`, `invalid_reference`, and `title_required` to "Check the highlighted fields." and otherwise shows `error.message`.
  - Settings forms pass `error.message` to `ErrorState`.
  - Sign-in pages and the manual report form render `error.message` in an `Alert` or a `<p role="alert">`.
- No summary reads `fieldErrors`, so a field the form never asks about is lost.

What the API sends:
- Serializer failures: `detail` "Check the submitted fields.", `reason` `invalid_request`, and DRF sentences per field (`accounts.views.api_exception_handler`, `feedback.http.invalid_request`).
- Domain errors that belong to a field: a specific `detail`, and the field's value is the reason code itself, for example `{"checked_slack": ["confirmation_required"]}` (`feedback/http.py`). Several of these fields are not rendered today: `checked_slack`, and `reason` on stop recovery.
- Domain errors that belong to no field: a specific `detail` and empty `field_errors`. They already reach every summary through `error.message`. `ActionError` replaces the text only for the reasons it maps.
- DRF's `non_field_errors` key: no serializer raises one. DRF adds it when the body is not an object. It arrives inside `field_errors` and is dropped like any field the form does not ask for.
- A 400 whose payload is a list gets `detail` "The request could not be completed." and empty `field_errors`. No code path raises one today.

## Goals / Non-Goals

**Goals:**
- Every form's summary shows errors for fields it does not render.
- A form names each field once.
- No edit in the files #157 and #161 own beyond `action-error.tsx`.

**Non-Goals:**
- Any backend or API change, including a clearer `detail` for serializer failures.
- One summary component for all screens.
- Showing every message for a rendered field. `fieldError` keeps returning the first.
- Summaries of actions with no form: `slack-account.tsx`, `release-picker.tsx`, the member row buttons, and the connection check. They keep showing `error.message`.

## Decisions

### D1. `fieldError` records the fields a form asked about
`field-error.ts` keeps a private module-level `WeakMap<ApiError, Set<string>>`. `fieldError(error, field)` adds `field` to the set for that error, then returns as it does today. `unrenderedFieldErrors` is the only reader; no other module reads or writes the map. A field is "rendered" when the form has asked for its error. The read records the field because the summary needs to know what the form asked about.
- The summary knows what the form rendered because the form already says so once, at the field.
- The key is the error object. Each failed request makes a new one, so a retry starts with no fields recorded. The entry is collected with the error.
- Adding to a set is idempotent, so StrictMode's double render is safe.
- Existing `fieldError` call sites need no edit.
- Alternative: a form context. `Field` takes `name`, reads its error from the context, and registers itself on mount. Precise and order-free. Rejected for this issue: every form changes at once (about 14 forms in 11 files, including the files #157, #161, and #148 hold), for a latent, low-priority finding.
- Alternative: each form passes its field names to the summary. Rejected: fields are listed twice, and a list that drifts brings the bug back silently.

### D2. `unrenderedFieldErrors(error)` builds the summary lines
Returns `string[]`, one line per field in `error.fieldErrors` that `fieldError` was not asked about.
- Messages go through the same `fieldMessages` map as inline errors.
- A message equal to `error.reason` or `error.message` is dropped. The first is a bare code and the second is already on screen. A field with no message left adds no line.
- The rest are joined with a space and prefixed with a label: `Repository: This field may not be blank.`
- The label is the API key with underscores as spaces and a capital first letter. `non_field_errors` gets no label.
- A field the form does not render has no visible label to reuse, so the key is the only name available.

### D3. `FormErrorMessage` renders the summary text
`form-error-message.tsx` exports `FormErrorMessage({ error, message = error.message })`. It renders `message`, then each line from D2 in its own `block` span.
- It is a component so that it reads the set after the form's body has run. A parent's body finishes before any child renders, so every `fieldError` call in the form has happened by then.
- `message` lets a summary keep its own wording (`ActionError`, the manual report form).
- No new colour, token, or layout. The lines take the style of the summary they sit in.

### D4. Summaries use `FormErrorMessage`
- `ActionError` renders `<FormErrorMessage error={error} message={actionMessage(error, record)} />`. Problem, inbox, and follow-up forms get the behaviour with no edit of their own.
- `ErrorState`'s `description` widens from `string` to `ReactNode`, so settings forms can pass the component.
- Sign-in pages and the manual report form render it where they render `error.message` today.

### D5. Every form reads through `fieldError`
The settings forms, the manual report form, and the sign-in pages switch to `fieldError`, so their fields are recorded.
- Three settings fields used `.join(' ')`. They now show the first message, like every other form.
- The manual report form's local `fieldError` closure is removed. Its title error becomes "Enter a title." for `title_required`.

### D6. Call sites
Line numbers are from commit f75904d.

| File | Edit |
| --- | --- |
| `components/states/action-error.tsx` | Line 41: description through `FormErrorMessage`. |
| `components/states/async-states.tsx` | `ErrorState`: `description?: ReactNode`. |
| `features/settings/connection-settings.tsx` | Lines 150 and 278: `fieldError`. Lines 179 and 293: `FormErrorMessage`. |
| `features/settings/members-settings.tsx` | Line 76: `fieldError`. Line 85: `FormErrorMessage`. |
| `features/settings/confirm-action.tsx` | Line 67: `fieldError`. Line 70: `FormErrorMessage`. |
| `features/inbox/manual-report-page.tsx` | Lines 56 to 57 and 68: shared `fieldError`. Line 144: `FormErrorMessage`. |
| `pages/sign-in-page.tsx` | Lines 51 and 61: `fieldError`. Line 65: `FormErrorMessage`. |
| `pages/reset-password-page.tsx` | Lines 84 to 91: `fieldError`. Line 102: `FormErrorMessage`. |
| `pages/accept-invite-page.tsx` | Lines 122 and 164 to 171: `fieldError`. Lines 125, 142, and 182: `FormErrorMessage`. |

### D7. Tests force the case
The product no longer produces the case, so tests stub the reply.
- Unit tests for `unrenderedFieldErrors` and `FormErrorMessage` in `components/forms/`.
- One component test in `settings-page.test.tsx`: the Slack connect form with a reply that rejects `repository`, which is the original report, and the GitHub form with the same reply, where the field is rendered.
- No new browser test. A Playwright test would intercept the reply too, so it would prove nothing the component test does not.

## Risks / Trade-offs

- A summary computed in a child component reads after the form body has asked about its direct fields, even when the summary appears first in the JSX. A field that asks for its error in a child rendered after the summary can repeat its message. This failure is a repeated message, never a hidden one.
- The recorded set lasts as long as the error. A field that was rendered and is then hidden while the same error stays on screen is still counted as rendered. The member saw the message under the field before it was hidden.
- Internal keys can show: "Version: A valid integer is required." This is accurate and only appears when the client sent a bad value.
- `ApiError.fieldErrors` is typed `Record<string, string[]>` and the OpenAPI type is `unknown`. A nested serializer would break both `fieldError` and the summary. No input serializer is nested today. Not changed here.
- `action-error.tsx` and `connection-settings.tsx` are held by #157 and #148. The edits are a few lines each, so whichever branch merges second has a small rebase.
