# Proposal

Delivers #74.

## Why

Nothing stops two product workspaces from binding the same GitHub installation and repository, and the `github-connection` spec does not say whether that is allowed. The #19 audit flagged it. A company with one org-wide installation can reasonably run two workspaces against the same repository. Each owner already proves access to the installation before binding, so sharing it exposes nothing that owner could not already see in GitHub.

## What Changes

- State in the spec that several workspaces may bind the same installation and repository, and that each keeps its own issues, links, and connection state.
- A workspace MUST NOT learn that another workspace shares its binding.
- Add tests that prove this isolation on the paths that fan out by installation: issue webhooks, installation lifecycle events, and disconnect.
- No code or behaviour change is expected. If a test exposes a leak, fix it as a bug against the new requirement.

This does not add cross-workspace sharing, which stays out of scope. Workspaces share an external binding, not records.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `github-connection`: adds a requirement that permits shared installation and repository bindings and keeps them isolated.

## Impact

- `openspec/specs/github-connection/spec.md` gains one requirement.
- New backend tests around `apply_issue_webhook`, `apply_installation_webhook`, and `disconnect`.
- No API, schema, or migration changes.
