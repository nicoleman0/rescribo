# Tasks

## 1. Version in the API

- [x] 1.1 Add `backend/health/version.py`: read `[project] version` from `pyproject.toml` two directories above `backend/health/` with `tomllib`, once at import, as `VERSION`. A missing file or key raises with a message naming the path. Verify with a unit test that `VERSION` equals the value parsed from the repo's `pyproject.toml`.
- [x] 1.2 Add `VersionSerializer` and `VersionView` to `backend/health/views.py`, using the default authentication and permissions, returning `{"version": VERSION}`. Add `path("api/version/", VersionView.as_view(), name="version")` beside the health routes in `backend/config/urls.py`. Verify with tests: a signed-in member gets 200 and the `pyproject.toml` version; a request with no session gets 401 and no `version` key.
- [x] 1.3 Run `task schema`; verify `frontend/openapi.yaml` and `frontend/src/api/schema.d.ts` gain only the version path and schema.

## 2. Version in the user menu

- [x] 2.1 Add `getVersion()` to `frontend/src/api/health.ts`, typed from the generated schema, throwing on a non-OK response or a body without a string `version`. Verify with a unit test for both failures.
- [x] 2.2 In `app-shell.tsx`, query the version once with `staleTime: Infinity` and pass it to both `UserMenu` instances as an optional `version` prop. In `user-menu.tsx`, render "Rescribo {version}" as a muted line in the label below the email and above the demo notice; render nothing when the prop is absent. Verify with `app-shell.test.tsx` or `user-menu` tests: the line shows when the request succeeds, and is absent while loading and after a failed request, with Sign out still present.
- [x] 2.3 Add one line under "App shell" in `frontend/DESIGN.md` that the user menu shows the running version as a muted line under the email. Add the line; do not reword existing text.
- [x] 2.4 Take after screenshots per the brief, including the open user menu at desktop and phone width; verify the version line shows in both themes.

## 3. Package versions

- [x] 3.1 Remove `"version"` from `frontend/package.json` and `marketing/package.json`. Run `npm install --package-lock-only` in each directory. Verify `git diff` on both lockfiles shows only the two root `version` lines removed, and `npm ci` then `npm run build` pass in each.

## 4. Changelog, release doc, roadmap

- [x] 4.1 Rewrite `CHANGELOG.md` to the shape in design.md: empty `## [Unreleased]`, `## [0.1.0] - YYYY-MM-DD` with Added and Security, and compare links. Base entries on `openspec/specs/` and `docs/`, aimed at a self-hoster. Verify every listed feature exists in a spec or doc and no contributor-only item remains.
- [x] 4.2 Add `docs/RELEASING.md` with the checklist and release notes template from design.md. Refer to the image workflow by its tag trigger only. The candidate and final steps include the compose image tag forms and the note that the workflow fails when tag, `pyproject.toml`, and `compose.prod.yaml` disagree, plus the one-time GHCR public step. Verify each step names the file or command it changes and the doc links `CHANGELOG.md` and `docs/DEPLOYMENT.md`.
- [x] 4.3 Add a short `## Roadmap` section to `README.md` after "The workflow", naming Teams, Discord, and GitLab support as future work. Add `docs/RELEASING.md` to Links. Verify `git diff README.md` leaves "Project status" untouched.

## 5. Repository checks

- [x] 5.1 Run `task check test build schema-check` with PostgreSQL and Redis running; all pass.
- [x] 5.2 Run `RESCRIBO_E2E_API_PORT=8254 RESCRIBO_E2E_FRONTEND_PORT=5254 task e2e`; all pass. Record the pass count.
- [x] 5.3 Run `npx @fission-ai/openspec validate --all --strict`; it passes.

## Workflow follow-up

- In the PR, list the shared-file lines touched outside the owned paths: the route in `backend/config/urls.py` and the lockfile lines.
- Archive the change in the PR that completes it.
