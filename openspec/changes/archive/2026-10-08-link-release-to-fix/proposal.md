# Proposal

Delivers GitHub issue #103, Link a release to a confirmed fix.

## Why

A confirmed fix records a note and a version, but nothing ties it to the release that shipped it. Members look the release up by hand before they tell customers.

## What Changes

- A member can pick a published release from the workspace's connected GitHub repository and link it to a problem whose fix is confirmed (`fix_available`). The confirmed fix card shows the linked release.
- A member can replace or remove the linked release. Each link and unlink is recorded in the problem's activity.
- The system stores a snapshot of the release (tag, name, URL, published date, provider ID). It does not re-read the release after linking.
- The GitHub App asks for one more repository permission, Contents read, because GitHub's release endpoints require it. Issue features keep working on installations that have not accepted it; the release picker explains what to grant.
- Release reads live in the GitHub integration module behind a provider-neutral boundary. Only GitHub is built.
- `fix_version` keeps its meaning and stays required. Follow-up messages do not change.

## Capabilities

### New Capabilities
- `fix-releases`: linking a provider release to a problem's confirmed fix, listing releases to choose from, and showing, replacing, and removing the link.

### Modified Capabilities
- `github-connection`: the Minimal permissions requirement adds Contents read, granted only for release reads, and an installation without it stays usable for issues.

## Impact

- Backend: new `FixRelease` model and migration in `backend/feedback/`, a release service, two problem endpoints and one workspace endpoint, two activity actions, demo seed data.
- GitHub integration: release listing and lookup in `backend/integrations/github_app/`, installation tokens scoped per operation, setup and probe permission checks.
- Shared files that need the coordinator's approval: `backend/config/urls.py` (three routes), `frontend/src/features/problems/problem-activity.tsx` (two activity labels), `openspec/specs/github-connection/spec.md` (an existing requirement changes, so it is not append-only), and the GitHub App setup docs (`docs/GITHUB_INSTALLATION_CHECK.md`, ADR 0005).
- API contract: regenerated `openapi.yaml` and `frontend/src/api/schema.d.ts`.
- Frontend: the confirmed fix card and a new release picker beside `problem-detail-page.tsx`.
- Operators must add Contents read to the GitHub App registration. Each installation owner must accept the new permission before releases can be listed.
