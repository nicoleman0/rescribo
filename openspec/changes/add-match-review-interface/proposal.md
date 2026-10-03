# Proposal

## Why

Members need to see and act on suggestions in the inbox. Delivers #21. Requires `add-match-pipeline` to be archived first; suggestions stay hidden unless the #24 gates pass.

## What Changes

- Show matching states and up to three suggestions with source evidence in the inbox. Design: [ADR 0003](../../../docs/adr/0003-local-rust-matcher.md), slice 5.
- Wire accept, reject, and retry actions. Manual search and grouping stay available in every state.
- Hide suggestions while the evaluation gate is unmet.

## Capabilities

### New Capabilities

### Modified Capabilities
- `match-suggestions`: adds the review interface and the evaluation gate on visibility

## Impact

Inbox feature in `frontend/src/features/inbox/`; component and Playwright tests.
