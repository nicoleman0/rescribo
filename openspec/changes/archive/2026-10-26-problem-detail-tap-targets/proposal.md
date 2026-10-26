# Proposal

## Why

Issue #177. At 390 px the standalone links on problem detail are 17 to 35.75 px tall. `frontend/DESIGN.md` asks for a 44 px phone touch target, and the shared `Button` minimum from #156 does not reach plain links or the activity summary.

## What Changes

- At phone width, every standalone link on problem detail is at least 44 px tall:
  - the linked report titles in Linked reports
  - the "linked N reports" activity summary, and the report links it reveals when opened
  - the GitHub issue link in the GitHub issue card
  - the release tag and "Fix evidence" links in the Confirmed fix card
  - "Open issue #N" after an issue is created, and "Open workspace settings" when GitHub is not connected
- Links inside running text stay as they are, as WCAG 2.5.8 allows: the report and problem links inside activity sentences, and "Open settings" inside the release picker's error sentence.
- Desktop layout does not change.
- `frontend/DESIGN.md` gains one line naming standalone links and the inline exemption.
- An e2e check measures the links on a seeded demo problem at 390 px.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `web-interface`: adds a phone touch-target requirement for problem detail. The spec states 44 px targets for other screens but has no requirement that covers problem detail links.

## Impact

- `frontend/src/features/problems/`: `problem-detail-page.tsx`, `problem-activity.tsx`, `github-issue-status.tsx`, `github-issue-create.tsx`, `problem-card.ts`.
- `frontend/e2e/demo.spec.ts`: one new test.
- `frontend/DESIGN.md`: one appended line.
- No API, schema, or backend change.
