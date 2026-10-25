## Changes

- Add problem state actions for starting work, returning to open, declining with a reason, and reopening.
- Show decline reasons and offer an inline decline action for open problems without reports.
- Add API, UI, and workspace isolation coverage. Sync the problem spec.

## Decisions to review

- Problem state actions use the existing version check and activity history.
- OpenAPI and TypeScript schema were generated on the current base. Regenerate after rebasing onto #183.

## Checks

- `task check test build schema-check` passed. Backend: 1,150 passed. Frontend: 386 passed. Matcher: 8 library tests and 18 contract tests passed.
- `task e2e` passed: 106 tests.
- `npx @fission-ai/openspec validate --all --strict` passed: 19 items.
- Existing warnings: backend staticfiles directory warning, frontend lint warnings, and build chunk size warning.

## Review

Pending

## Screenshots

Pending
