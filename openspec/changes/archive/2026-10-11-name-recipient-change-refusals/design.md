# Design

## Context

See proposal.md for the problem. What the code does today:

| Cause | Raised in `change_recipient` | HTTP | Text the form shows |
| --- | --- | --- | --- |
| Actor is not an owner | `InvalidTransition` | 403 from `OwnerWorkspaceView`, before the use case runs | DRF's permission sentence |
| New recipient has no Slack link | `InvalidTransition` | 409 `invalid_transition` | "This action is no longer available for the report. The latest version is shown." |
| New recipient is the current one | `InvalidTransition` | 409 `invalid_transition` | Same. The button is disabled, so only the API reaches it. |
| New recipient is not active, or not in the workspace | `NotFound(record="recipient")` | 404 | "This report no longer exists, or it belongs to another workspace." |

Constraints:

- `feedback_error_response` in `backend/feedback/http.py` translates every domain error. An error it does not know is re-raised as a 500.
- `ActionError` maps a few reasons to its own text and otherwise shows the server's `detail`. Reports and problems share it.
- `RecipientForm` already passes `fieldError(mutation.error, 'new_recipient_id')` to its select. Nothing sends that field error today.
- `GET members/` returns `MemberSummarySerializer` rows: `id` and `display_name`. The same serializer is embedded in about twenty other payloads. `useMembers` caches the directory once for every picker.
- `has_slack_identity` and `change_recipient` each spell out the same identity query.

## Goals / Non-Goals

**Goals:**
- Each refusal has its own reason and a sentence the owner can act on.
- The picker does not offer a choice the server will refuse.
- One definition of "this member has a Slack link" on the server.
- No change to the text `ActionError` shows to any other caller.

**Non-Goals:**
- The customer contact and notification sections of the same files (#160).
- The shared form error summary, `frontend/src/components/forms/`, and `frontend/src/api/request.ts` (#146).
- Restricting recipient changes by follow-up state.
- The check in `slack_readiness` that the identity belongs to the connected Slack team. See Risks.
- `correct_outcome`, which also raises `InvalidTransition` for a non-owner.

## Decisions

**A new error for the missing Slack link.** `RecipientNotLinked(FeedbackError)` with reason `recipient_not_linked`. `http.py` gets one branch: 400, `detail` "This member has not linked a Slack account. Choose a member with a Slack link, or ask this member to link Slack in Settings.", empty `field_errors`. It is a 400 because the request names a value the server cannot accept, and the follow-up did not change, so there is no current row to return. `DeliveryNotReady` uses the same shape for `no_slack_identity`.

Alternative: raise `DeliveryNotReady(reason="recipient_not_linked", detail=...)`, which `http.py` already maps, so that file stays untouched. Rejected: the error's meaning is "a Slack delivery cannot start", and no delivery is being started here.

Alternative: put the reason in `field_errors` so it shows under the select. Rejected: `fieldError` prints an unmapped code as raw text, and its message table is in a file #146 owns.

**Reuse `NoChanges` for the current recipient.** It already answers 409 `no_changes` with the current row, and `ActionError` already says "Nothing changed."

**Reuse `InvalidReference` for a member who is not active.** `InvalidReference(field="new_recipient")` answers 400 with `field_errors: {"new_recipient_id": ["invalid_reference"]}`. The form already shows that under the select as "Choose an active record in this workspace.", and `ActionError` says "Check the highlighted fields." Revoked, unknown, and other-workspace members get the same response, so the answer does not reveal whether a membership exists elsewhere. The use case keeps its own locked query; `validate_reference` does not lock the row.

**Leave the non-owner guard as it is.** HTTP callers never reach it: the view answers 403 first, and that response names its cause. The guard is a second line of defence for other callers. A new domain error for it would need a 403 mapping and the same change in `correct_outcome`.

**The server sends the sentence.** `ActionError` falls back to `detail` for reasons it does not map. With a 400 and a new reason, the form shows the server's sentence and `action-error.tsx` does not change, so no other caller's text can move.

**One definition of a Slack link.** A private helper in `follow_ups.py` returns the identity queryset for a workspace and membership (`ExternalIdentity`, provider Slack). `has_slack_identity`, `change_recipient`, and the directory annotation use it. The annotation passes `OuterRef` values, so the directory costs one query.

**A directory entry type.** `MemberDirectoryEntrySerializer` extends `MemberSummarySerializer` with `has_slack_link`. Only `MemberDirectoryView` uses it. `MemberSummary` stays `id` and `display_name` everywhere it is embedded.

Alternative: add the flag to `MemberSummarySerializer`. Rejected: it adds a query per embedded member across about twenty payloads that do not need it.

Alternative: send eligible recipients inside the follow-up detail. Rejected: it duplicates the directory and grows a payload every member loads.

The flag is visible to every member, as the directory is. The follow-up detail already tells any member whether the recipient has a Slack link.

**Disabled and labelled, not hidden.** An option for a member with no Slack link is `disabled` and reads "Una Unlinked (no Slack link)". The owner sees why the member cannot be chosen and what would fix it. The current recipient's option is never disabled, so the owner can move the select back to it. It still carries the label when the recipient has no link.

Alternative: leave ineligible members out. Rejected: the owner cannot tell a missing member from a bug.

**Refetch the directory after a refusal.** The directory is cached for 60 seconds. A refusal means it may be stale, so the form refetches members on error through the per-call `onError` of `mutate`. `useFollowUpMutation` does not change.

## Risks / Trade-offs

- [API clients that match 409 `invalid_transition` or 404 on this endpoint see new codes] → The web app is the only client. The generated contract already lists 400 for this endpoint.
- [A member linked to a Slack team other than the connected one counts as linked. The change is accepted and a later send fails with `no_slack_identity`] → Existing behaviour, and the same rule `has_slack_link` already uses on the follow-up detail. Not changed here. Listed in the PR under "Decisions to review".
- [Every picker's directory call now carries one more boolean and one `EXISTS` subquery] → One indexed lookup per row on a list of workspace members.
- [Component tests in other features stub `members/` without the flag] → Only `RecipientForm` reads it. Those stubs keep working.
