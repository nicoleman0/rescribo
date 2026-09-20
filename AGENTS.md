# Working in this repository

- Use the GitHub milestones and issues as the source of truth for implementation breakdown and delivery order.
- Read `docs/MVP_SPEC.md` before changing product behaviour.
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
