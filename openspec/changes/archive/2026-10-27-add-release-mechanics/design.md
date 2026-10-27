# Design

## Context

- `pyproject.toml` has `version = "0.1.0"` and `[tool.uv] package = false`, so the project is never installed and `importlib.metadata.version("rescribo")` raises `PackageNotFoundError`.
- Both backend image targets copy `pyproject.toml` to `/app`, beside `/app/backend`. A dev checkout has the same layout. So `Path(__file__).resolve().parents[2] / "pyproject.toml"` from `backend/health/` finds it in both.
- The frontend runs in its own proxy image. It cannot know the backend's version at build time without a second source.
- `frontend/package.json`, `marketing/package.json`, and their lockfiles' root entries say `0.1.0`. Nothing reads these fields (no `npm_package_version`, no Vite `define`). Both packages are `private`.
- `CHANGELOG.md` stops at early milestones (#6 to #41). Most shipped behaviour (Slack capture, follow-ups, fix releases, demo, retention, deployment) is missing from it.
- Release tags are `v0.1.0`, and candidates are `v0.1.0-rc.1`, per #252.

## Goals / Non-Goals

**Goals:**
- One place to change the version. Everything else reads it or checks against it.
- A member can copy the running version into a bug report.

**Non-Goals:**
- Image labels, tag checks, and publishing. #252 owns them.
- Self-hoster quickstart, upgrade steps, and the README status section. #253 owns them.
- A Django setting for the version. None is needed.

## Decisions

### Read the version from `pyproject.toml` at import

`backend/health/version.py` parses `pyproject.toml` with `tomllib` once, at import, and exposes `VERSION`. A missing file or key raises at startup, so a broken image fails loudly instead of serving a blank version.

Alternatives:
- `importlib.metadata`: fails because the project is not installed. Making it a package would change how `uv sync` and the images work.
- A `RESCRIBO_VERSION` env var or build arg set from the tag: a second source, and the dev server would have none.
- A hard-coded `__version__`: a second source to bump.

### `GET /api/version/` for signed-in members, in the health app

`VersionView` returns `{"version": "0.1.0"}` with a `VersionSerializer` for the schema. It uses the default authentication and `IsAuthenticated`, so a signed-out request gets the usual 401. The route is `api/version/`, not under `api/health/`, because it is not a health check. The view lives in `backend/health/` because that app holds the operational endpoints, and the version is static metadata, not business logic.

Alternatives:
- Add `version` to `/api/health/live/`: no new route, and an operator could curl it. But liveness responses stay minimal, and it tells anyone on the internet which version runs. Kept as an option for the coordinator.
- Add `version` to `/api/auth/session/`: no extra request, but it mixes static metadata into the session contract and touches `backend/accounts/`, which this issue does not own.

### Show it in the user menu

`app-shell.tsx` runs one `useQuery` for the version with `staleTime: Infinity` and passes the result to `UserMenu` as an optional `version` prop. `UserMenu` renders "Rescribo 0.1.0" as a second muted line inside the existing `DropdownMenuLabel`, below the email and above the demo notice. Loading and failure render nothing, matching how the navigation counts hide. The label is not focusable, so keyboard behaviour does not change.

The user menu is on every product screen and already shows who you are. Settings would need a new section or an extra line in an unrelated one.

### Remove `version` from both `package.json` files

They are private, nothing reads them, and a third copy of `0.1.0` would be wrong after the next release. Removing the field also needs the two root `version` lines in each lockfile removed (`npm install --package-lock-only`), with no dependency change. The marketing site is not the product, so it has no reason to carry the product version.

Alternatives:
- Keep and bump them each release: three places to change, for no reader.
- Keep and never bump: a stale number that looks authoritative.

### Changelog shape

```
## [Unreleased]

## [0.1.0] - YYYY-MM-DD

### Added   (grouped by what a self-hoster runs: capture, triage, GitHub, follow-ups, workspaces, demo, self-hosting)
### Security

[Unreleased]: https://github.com/nicoleman0/rescribo/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/nicoleman0/rescribo/releases/tag/v0.1.0
```

Write each line from the current specs and docs, not from the old entries alone, since those miss most of the product. Drop contributor-only items: CI, screenshots, feasibility checks, e2e fixes, test tooling. Drop the "Changed" items that only affected pre-release local databases. Keep issue numbers off; a self-hoster reads features, not tickets. Each line names a feature, not a phrase like "improved". Match suggestions are listed as off by default.

### Release notes template lives in `docs/RELEASING.md`

The issue asks for a template; the brief does not mention it. A section in the release doc keeps it next to the step that uses it. `.github/release.yml` only configures GitHub's PR list and is in `.github/`, which this issue does not own.

The template: one-line summary, highlights copied from the changelog section, upgrade notes (link to #253's upgrade steps), image names and tag, and a link to the full changelog.

### Release checklist

`docs/RELEASING.md` steps, each one line:
1. Set `[project] version` in `pyproject.toml` on a release branch.
2. Move Unreleased entries into a new version section in `CHANGELOG.md` and update the compare links.
3. Merge, then push `vX.Y.Z-rc.N` from `main`. The image workflow runs on version tags and publishes the candidate.
4. Clean-install check: a fresh host following the self-hoster quickstart with the candidate images, sign in, open the user menu, and confirm the version.
5. Set the date in the changelog heading, merge, push `vX.Y.Z`.
6. Publish the GitHub release with notes from the template.

The candidate and final versions must agree across the tag, `pyproject.toml`, and the two image tags in `compose.prod.yaml`: a candidate commits `pyproject.toml` as PEP 440 (`0.1.0rc1`) and the compose tags as `0.1.0-rc.1` before it tags `v0.1.0-rc.1`; a final release sets `0.1.0` in all three before it tags `v0.1.0`. `docs/RELEASING.md` states the candidate forms in their general shapes (`X.Y.ZrcN`, `X.Y.Z-rc.N`) with the 0.1.0 values as examples. The workflow fails when they disagree. After the first published release, the maintainer makes both GHCR packages public once.

It names the workflow by trigger ("runs on `v*` tags"), not by file contents.

## Risks / Trade-offs

- [#252's tag check reads a field this change does not move] → No conflict. This change leaves the field and its value alone.
- [`backend/config/urls.py` is in #257's directory] → One added line near the health routes. The coordinator decides whether to accept it (question 1).
- [Lockfile lines are in #257's scope] → Two metadata lines per lockfile, no dependency change. Question 2.
- [A future packaging change could move `pyproject.toml` relative to `backend/`] → The import-time read fails at startup, and a unit test asserts the served version matches `pyproject.toml`.
- [Version visible to every member] → Members already see the whole product. No anonymous exposure.
