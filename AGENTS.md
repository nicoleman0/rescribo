# Working in this repository

- Use the GitHub milestones and issues as the source of truth for implementation breakdown and delivery order.
- Product behaviour lives in `openspec/specs/`. Change it through an OpenSpec change in `openspec/changes/` (`/opsx:propose`, `/opsx:apply`, `/opsx:archive`), exactly one change per GitHub issue. If work is too big for one PR, split the issue, not the change. Archive the change in the PR that completes it.
- New work: open a short GitHub issue (problem and milestone) first, then propose a change that names it. After proposing, add `Change: openspec/changes/<name>` as the first line of the issue body with `gh issue edit`. Use `/opsx:explore` while an idea is still vague. Acceptance criteria live in the change's scenarios and tasks; the issue links to the change instead of repeating them.
- Skip OpenSpec when no observable behaviour changes: bugs where code diverges from the spec, tooling, infrastructure, refactors. Use an issue and PR, or a change with `skip_specs: true`.
- Run `npx @fission-ai/openspec validate --all --strict` when specs or changes are edited.
- Prioritise reusability, modularity, DRY, and maintainability. Use clear ownership boundaries, shared workflow rules, and typed contracts.
- Keep provider-specific behaviour in integration modules. Keep HTTP handlers and background tasks thin.
- Do not add business logic to environment health checks or the development status page.
- Use `uv` from the repository root and `npm` from `frontend`. Commit both lockfiles.
- Never commit `.env`, provider credentials, real customer reports, or unredacted webhook fixtures.
- Run `task check test build schema-check` with PostgreSQL and Redis running. Run `task e2e` for browser/API changes and `task worker-check` for worker wiring changes.
- Regenerate OpenAPI and TypeScript contracts with `task schema` when the API changes.
- Database changes require migrations. Cross-workspace access checks belong in both application code and tests.
- Use real services for integration checks. Distinguish mocked tests from live provider verification.
- This scaffold is local development infrastructure, not a production deployment.
- Frontend visual rules and shared component ownership are documented in [frontend/DESIGN.md](frontend/DESIGN.md).
