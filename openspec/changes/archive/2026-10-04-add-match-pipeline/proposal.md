# Proposal

## Why

With the contract frozen (#22), reports can be ranked against existing problems in the background. Delivers #23. Requires `freeze-matcher-contract` to be archived first.

## What Changes

- Retrieve up to ten same-workspace open problems with PostgreSQL text search after report creation or a matching-relevant edit.
- Rank them with a deterministic local Rust executable. No hosted model, network access, or credentials. Design: [ADR 0003](../../../docs/adr/0003-local-rust-matcher.md), slices 2 to 4.
- Persist workspace-scoped runs and suggestions with input versions and safe failure categories.
- Add authenticated accept, reject, and retry endpoints. Acceptance uses the normal report-linking use case.

Suggestions are not shown in the UI until #21 and the #24 gates.

## Capabilities

### New Capabilities
- `match-suggestions`: advisory problem suggestions for a report, their lifecycle, and human decisions

### Modified Capabilities

## Impact

New `rust/` crate and CI jobs; container images build the matcher binary; backend matching module, migrations, Celery tasks, and API endpoints; regenerated OpenAPI and TypeScript contracts. Open: deployment OS/CPU targets and Rust MSRV, chosen with the base image.
