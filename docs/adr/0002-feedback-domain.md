# ADR 0002: Workspace-scoped feedback domain

Status: accepted

## Decisions

- Report and problem mutations use transactional services. They lock the target row, scope it to the actor's workspace, and check its version before saving.
- Services validate membership and problem references in the actor's workspace. Django 5.2 has no composite foreign keys, so direct ORM writes can bypass this boundary; application tests cover the use cases.
- PostgreSQL enforces external source uniqueness. Every report has one immutable provenance record, including manual reports.
- Activity metadata contains field names and state or ID changes only. It does not contain report, customer, or snapshot content.
- Members cannot move a `fix_available` problem to another state yet. GitHub issue reopening will own that transition in a later issue.
