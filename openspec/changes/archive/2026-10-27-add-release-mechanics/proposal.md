# Proposal

Delivers GitHub issue #254.

## Why

Rescribo has no tags or releases, and nothing tells a self-hoster or a bug report which version runs. `CHANGELOG.md` is one long Unreleased section that stops at early milestones. The first release (milestone I) needs a version, a changelog cut, and a repeatable way to release.

## What Changes

- `[project] version` in `pyproject.toml` stays the one source of truth (already `0.1.0`). #252's release workflow checks tags against it.
- The backend reads that field once at startup from `pyproject.toml` and serves it at `GET /api/version/` to signed-in members.
- The user menu shows "Rescribo 0.1.0" as a muted line under the email.
- The `version` field goes from `frontend/package.json` and `marketing/package.json`, with the matching root lines in their lockfiles. Both packages are private and nothing reads the field, so it could only drift.
- `CHANGELOG.md` is cut to `## [0.1.0] - YYYY-MM-DD`, condensed to what a self-hoster cares about, with an empty Unreleased section above and Keep a Changelog compare links below.
- New `docs/RELEASING.md`: a release checklist and a release notes template.
- `README.md` gains a short Roadmap section naming Teams, Discord, and GitLab support as future work. The status section is unchanged.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `web-interface`: adds a requirement that the user menu shows the running version, read from the API.

## Impact

- Backend: new `backend/health/version.py` and a `VersionView` in `backend/health/views.py`. One route line in `backend/config/urls.py`, which is in #257's directory.
- API contract: `frontend/openapi.yaml` and `frontend/src/api/schema.d.ts` regenerate with `task schema`.
- Frontend: `frontend/src/api/health.ts`, `app-shell.tsx`, `user-menu.tsx`, and their tests.
- Lockfiles: two metadata lines each in `frontend/package-lock.json` and `marketing/package-lock.json`. No dependency changes.
- Docs: `CHANGELOG.md`, `README.md`, new `docs/RELEASING.md`.
- No settings, migrations, workflow, compose, or Dockerfile changes.
