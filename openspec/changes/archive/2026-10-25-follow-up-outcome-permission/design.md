# Design

## Context

- The web rule is `_can_record_outcome(actor, report)` in `backend/feedback/follow_ups.py`: owner, `report.assignee`, or `report.submitted_by`. `record_outcome` calls it when the request is not from Slack. The Slack path checks the linked identity and the follow-up recipient instead, and is not touched.
- `FollowUpDetailSerializer` has no viewer today. The follow-up views build it in nine places in `backend/feedback/views.py`, including the `current` callables that `feedback_error_response` puts on every 409.
- `get_follow_up` already `select_related("report")`, so the rule needs no extra query.
- The frontend's `useFollowUpMutation` writes a 409's `current` record into the detail cache. A stale page therefore picks up the new field from the refusal with no extra code.
- `RecordOutcomeForm` returns the owner `CorrectionForm` or nothing when the outcome is final. Owners always pass the rule, so the correction path is unaffected.

## Goals / Non-Goals

**Goals:**
- One source for the rule: the payload field and the endpoint call the same function.
- Hide the form for members who would be refused, and say who can record.

**Non-Goals:**
- Changing who may record. In particular, a recipient that an owner set with a recipient change can record from Slack but not from the web app unless they are also the assignee or submitter. That stays as it is.
- Naming the actual assignee or submitter in the line.
- A new error message for the 409.

## Decisions

### Field: top-level `can_record_outcome` on `FollowUpDetail`
A read-only boolean, appended after `history`. It describes the viewer, not the outcome record, so it sits beside `outcome` rather than inside `FollowUpOutcomeSerializer`. Alternative: `outcome.can_record`. Rejected because `outcome` reads as stored data and is reused by `source="*"`.

### Rule stays in one function
Rename `_can_record_outcome` to `can_record_outcome` so the serializer can import it without reaching into a private name. `record_outcome` keeps calling it. The serializer method does `can_record_outcome(actor=self.context["actor"], report=follow_up.report)`. A missing `actor` raises `KeyError`, so a call site that forgets the context fails in tests instead of returning a wrong answer. Alternative: a wrapper function. Rejected as a second name for the same rule.

The rename is a separate first commit with no behaviour change, so the reviewer can read it on its own.

### Views pass the viewer at each call site
Each `FollowUpDetailSerializer(...)` in the follow-up views gains `context={"actor": self.membership}` (or the `actor` argument in `_follow_up_current`). No call sites are reordered or merged, so #181 rebases cleanly. Alternative: one shared helper for all nine. Rejected here because it rewrites lines #181 also edits; it can come later as its own refactor.

### Frontend
`ContactSection` reads `followUp.can_record_outcome`. When it is false and `choicesFor(state)` is not empty, it renders one `<p className="text-sm text-muted-foreground">` with the line instead of `RecordOutcomeForm`. When choices are empty, the existing branch already shows the correction form to owners and nothing to others. The `isOwner` prop stays for the correction form, which follows the separate owner-only rule.

Wording: "Only an owner, the report's assignee, or its submitter can record customer contact."

## Risks / Trade-offs

- [The panel and page layouts both render `ContactSection`] → The change is inside the section, so both get it. The component test covers the section directly.
- [The standard shots sign in as the demo visitor, a member, and open a follow-up with a final outcome] → They show no difference. An extra before and after pair opens a pending follow-up the visitor may not record. The component tests are the evidence for each state.
