# Design

## Context

- `change_problem_state` in `backend/feedback/problems.py` already locks the problem, checks the version, applies `PROBLEM_TRANSITIONS` (`start`, `stop`, `decline`, `reopen`), requires a reason for `decline`, clears it on `reopen`, and writes a `problem.state_changed` activity entry. It stays unchanged.
- `ProblemActionView` gives every problem write the same shape: a versioned request, a 409 with the current problem, a 404 for another workspace, and CSRF.
- `ProblemDetailSerializer` does not return `not_planned_reason`, so a declined problem's reason is stored but never shown.
- Activity already renders `problem.state_changed` as "changed the status to X". The feedback domain model is in [ADR 0002](../../../docs/adr/0002-feedback-domain.md).

## Goals / Non-Goals

**Goals:**
- One thin endpoint over `change_problem_state`.
- One decline form, used by the Status card and by the no-reports offer.

**Non-Goals:**
- `fix_available` transitions and fix confirmation.
- Recording the decline reason in activity. Activity keeps its current `{action, state}` metadata.
- Tap target sizes on problem detail (#177).
- Problems list changes.

## Decisions

### One route with an action field

`POST api/workspaces/<id>/problems/<problem_id>/state/` with `{expected_version, action, reason?}`. `ProblemStateChangeView(ProblemActionView)` calls `change_problem_state`. `ProblemStateChangeSerializer(VersionedSerializer)` takes `action` as a choice from the keys of `PROBLEM_TRANSITIONS`, so the allowed actions have one home. `reason` is optional and may be blank, max 2000 characters. The domain raises `ReasonRequired` for a blank decline reason, which `feedback_error_response` already maps to a 400 on `reason`.

Alternative: one route per action, like report triage. Rejected: four views and routes for one use case that already takes an action, and the brief allows one route.

### Return the decline reason on problem detail

Append `not_planned_reason = serializers.CharField()` to `ProblemDetailSerializer`. Not added to list items. Existing fields keep their order.

### Status card in the side column

A new `ProblemStatusCard` in `frontend/src/features/problems/problem-status.tsx`, first in the side column, using `problemCard`. It shows the state badge and the actions the state allows:

| State | Text | Actions |
| --- | --- | --- |
| `open` | none | Start work, Mark not planned |
| `in_progress` | none | Move back to open, Mark not planned |
| `not_planned` | the decline reason | Reopen |
| `fix_available` | card not rendered | none |

Start, Move back to open, and Reopen run at once: each is one click to undo. A success toast names the new status. Focus moves to the card heading after success, because the clicked button is gone.

The "Not planned" next-step banner is unchanged. The reason lives in the card next to Reopen.

The state badge stays in the Status card and is removed from the detail header. The header keeps the fix-available badge because that state has no Status card. This avoids repeating the current state on desktop.

Alternative: actions in the next-step banner. Rejected: DESIGN.md says Mark reviewed is the banner's only write action.

### Shared decline form

`DeclineProblemForm` wraps `ConfirmPanel` with a required `TextareaField` labelled Reason. Confirm stays disabled until the trimmed reason is non-empty. It runs through `useProblemMutation`, so a 409 updates the cached problem. The form owns its draft, so a failed request keeps the typed reason and shows `ActionError`. The reason is not prefilled.

The Status card and the no-reports offer each mount their own instance. The offer sits in the linked reports empty text, shown only when the problem is `open` or `in_progress` and `report_count` is 0, matching `NoReportsBadge`. The condition moves to one exported helper that both use. If a cache update makes the problem ineligible while the offer form is open, the form closes.

Alternative: the offer opens the Status card's form. Rejected: on wide screens the card is in the other column, so focus would jump away from where the member clicked.

### Demo workspaces

State changes are allowed in demo workspaces, like Mark reviewed. They call no external provider.

## Risks / Trade-offs

- [Two decline forms could be open at once on an empty problem] → When one changes the problem, a cache update closes the other form.
- [#183 changes the same views, serializers, and schema files] → Generate the schema on this branch's current base. After #183 merges, the coordinator rebases this branch and regenerates the schema with `task schema`.
