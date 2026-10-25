# Proposal

## Why

Delivers GitHub issue #183. Only an owner, the report's assignee, or its submitter may record a customer contact outcome in the web app. The follow-up detail shows the Customer contact form to every member, so any other member fills it in and gets a 409 with the generic text for an unavailable action. Since #160 the form shows on every follow-up, so more members meet the refusal.

## What Changes

- The follow-up detail payload gains `can_record_outcome`: whether the viewing member may record an outcome. The server computes it from the same rule that guards the outcome endpoint.
- Every endpoint that returns the follow-up detail, including the `current` record on a 409, carries the field for the requesting member.
- When the viewer may not record and an outcome can still be recorded, the Customer contact section hides the record form and shows one line saying who can record contact.
- The server check on the outcome endpoint stays. A stale page that submits still gets the 409, and the returned record replaces the form with the line.
- No change to owner corrections, the Slack outcome buttons, or who may record.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `follow-ups`: adds a requirement that the follow-up detail says whether the viewer may record an outcome, and that the web app shows the record form only to those who may.

## Impact

- Backend: `backend/feedback/follow_ups.py` (the permission function becomes public), `backend/feedback/serializers.py` (`FollowUpDetailSerializer`), `backend/feedback/views.py` (follow-up views pass the viewer to the serializer).
- API: one new read-only boolean on `FollowUpDetail`. Additive. Regenerated `frontend/openapi.yaml` and `frontend/src/api/schema.d.ts`.
- Frontend: `frontend/src/features/follow-ups/follow-up-outcome.tsx` and the detail fixture.
- Tests: `backend/tests/test_follow_ups.py`, `frontend/src/features/follow-ups/follow-up-outcome.test.tsx`.
