# Proposal

## Why

Members group reports into problems by searching by hand. Suggesting likely problems for a new report saves time, but only if the suggestions are evaluated and stay advisory. Delivers #22, #23, #24, and #21 in milestone D.

## What Changes

- Retrieve up to ten same-workspace open problems with PostgreSQL text search after report creation or a matching-relevant edit.
- Rank them with a deterministic local Rust executable behind a versioned JSON contract. No hosted model, network access, or credentials.
- Persist workspace-scoped runs and suggestions with input versions and safe failure categories.
- Show up to three suggestions with source evidence. A member accepts or rejects; acceptance uses the normal report-linking use case.
- Evaluate retrieval and ranking against labelled fixtures and predeclared gates. Suggestions stay hidden until the gates pass.

## Capabilities

### New Capabilities
- `match-suggestions`: advisory problem suggestions for a report, their lifecycle, and human decisions
- `matching-evaluation`: the labelled dataset, metrics, and release gates that decide whether suggestions are shown

### Modified Capabilities

## Impact

New `rust/` crate and CI jobs; backend matching module, migrations, Celery tasks, and API endpoints; inbox suggestion UI; regenerated OpenAPI and TypeScript contracts; container image builds the matcher binary.
