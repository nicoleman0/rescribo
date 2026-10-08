# Design

## Context

- The fix lives on `Problem` as `fix_note`, `fix_version`, `fix_evidence_url`, `fix_confirmed_at`, and `fix_confirmed_by` (`backend/feedback/models.py`). `confirm_fix` in `backend/feedback/problems.py` overwrites them and bumps `resolution_revision`.
- Issue linking is the pattern to follow: `link_issue` in `backend/feedback/engineering_issues.py` resolves the active GitHub `Connection`, opens `github_client()` and `selected_repository(...)`, and calls a resolver in `integrations/github_app/issues.py`.
- GitHub's release endpoints (`GET /repos/{owner}/{repo}/releases`, `GET /repos/{owner}/{repo}/releases/{release_id}`) require the Contents read repository permission for installation tokens ([GitHub: permissions required for GitHub Apps](https://docs.github.com/en/rest/authentication/permissions-required-for-github-apps), "Repository permissions for Contents"). The app grants only Issues write and Metadata read today, and `github-connection` forbids Contents. ADR 0005 chose the GitHub App for "Selected repositories and separate issue permissions".
- `GitHubAppClient.create_installation_token` hard-codes `{"issues": "write", "metadata": "read"}`. `github_setup` and `InstallationProbe` require that exact permission set.
- Draft releases are listed only for callers with push access ([GitHub: List releases](https://docs.github.com/en/rest/releases/releases#list-releases)). A Contents read token never sees drafts.

## Goals / Non-Goals

**Goals:**
- One provider boundary for releases that a GitLab module could implement later without changing `feedback`.
- Least privilege per token: Contents read only on tokens that read releases.
- Existing installations keep working for issues until their owner accepts the new permission.

**Non-Goals:**
- Release webhooks, release detection, or re-reading a linked release.
- Search across releases. GitHub has no release search endpoint; the picker filters only what it has loaded.
- Linking a release while confirming the fix. Linking is a separate action on the confirmed fix card.
- Changing follow-up message text (#102) or the problems list (#122).

## Decisions

### D1. Separate `FixRelease` table, one row per problem
`FixRelease(problem OneToOne PK-cascade, workspace FK, provider, external_id, repository_id, tag_name, name, url, published_at, linked_by FK Membership PROTECT, linked_at)`.
- Keeps provider fields out of `Problem` and clears as one unit.
- Alternative: six `fix_release_*` columns on `Problem`. Rejected: nullable as a group, harder to assert all-or-nothing.
- `provider` is a `TextChoices` with only `github`. `external_id` and `repository_id` are strings, matching `EngineeringIssue` and `Connection`.
- Unique constraint on `problem`. Check constraint: `tag_name` and `url` non-empty.

### D2. Snapshot, verified once
Linking fetches the release by ID with a fresh token, checks it is not a draft and that its `html_url` is `https://github.com/{canonical}/releases/tag/...`, then stores the snapshot. No later reads. Alternative: read live on each page view. Rejected: one provider call per view, and a deleted release would blank the card.

### D3. `fix_version` sits beside the release
`fix_version` stays required, member-written, and the text follow-ups use. The release is extra evidence. Alternatives: fill `fix_version` from the tag (changes a customer-facing string without the member typing it), or replace it (breaks follow-ups and every `confirm_fix` caller).

### D4. Provider boundary
- `integrations/github_app/releases.py`: `ReleaseSnapshot` dataclass (`external_id`, `tag_name`, `name`, `url`, `published_at`, `prerelease`), `parse_release_payload`, `list_releases(client, token, repository, page) -> (list[ReleaseSnapshot], has_next)`, `get_release(client, token, repository, repository_id, release_id) -> ReleaseSnapshot`, and `ReleaseAccessMissing` / `ReleaseNotFound` errors.
- `GitHubAppClient` gains `list_releases(..., page)` (`per_page=20`, returns rows and `has_next` from the `Link` header, same as `list_issues`) and `get_release(...)`.
- `feedback/releases.py` holds the use cases (`list_repository_releases`, `link_fix_release`, `unlink_fix_release`) and is the only caller of the GitHub module. A second provider would add a module with the same three functions and a dispatch on `Connection.provider`; that dispatch is not built now.

### D5. Per-operation token permissions
- `create_installation_token` takes a `permissions` mapping that defaults to the issue set, so existing callers (including `operations/tasks.py`) do not change. Release reads pass `{"contents": "read", "metadata": "read"}`.
- `selected_repository(...)` takes the same `permissions` argument and passes it through.
- One home for the permission sets: `integrations/github_app/permissions.py` with `ISSUE_PERMISSIONS`, `RELEASE_PERMISSIONS`, `REQUIRED_INSTALLATION_PERMISSIONS`, `OPTIONAL_INSTALLATION_PERMISSIONS`, and `check_installation_permissions(permissions) -> bool` (required present, nothing outside required plus optional). `github_setup` and `InstallationProbe` use it.
- GitHub refuses a token request for a permission the installation lacks with HTTP 422 (to verify in the live check; mocked tests assume 422). Release code maps 422 on token creation to `ReleaseAccessMissing`. `installation_failure` must not treat it as an installation failure, so the connection stays active.

### D6. API
- `GET /api/workspaces/{ws}/releases/?page=N` → `{results: [{external_id, tag_name, name, url, published_at, prerelease}], has_next}`. Workspace-scoped because releases belong to the repository, not a problem.
- `POST /api/workspaces/{ws}/problems/{id}/fix-release/` body `{expected_version, external_id}` → `ProblemDetail`. Replaces any existing link.
- `POST /api/workspaces/{ws}/problems/{id}/fix-release/unlink/` body `{expected_version}` → `ProblemDetail`.
- Errors reuse `FeedbackError` reasons: `connection_not_ready` (409), `demo_workspace`, `invalid_transition` (state is not `fix_available`), version conflict, plus new `release_access_missing` (409), `release_not_found` (422), `release_provider_unavailable` (503).
- Link and unlink bump `Problem.version` and write `Activity` `problem.fix_release_linked` (metadata `{tag_name}`) or `problem.fix_release_unlinked`.
- `ProblemDetailSerializer` gains `fix_release: FixRelease | null`, declared `required=False` so the generated TypeScript field is optional. That keeps existing `ProblemDetail` fixtures compiling, including `problems-page.test.tsx`, which #122 owns.

### D7. Permissions within the workspace
Any active member may list, link, replace, and unlink, the same as confirming a fix. Workspace isolation follows `get_problem(actor=...)` and `Connection` lookup by `actor.workspace_id`.

### D8. UI
- `FixCard` (fix_available) shows the linked release as a link (tag, name when it differs from the tag, published date) and `Change release` / `Remove release` buttons. With no link it shows `Link a release`.
- `release-picker.tsx` beside the page: a `useInfiniteQuery` over the list endpoint, rows as radio options, a `Load more` button when `has_next`, a pre-release badge, and a client-side filter box over loaded rows. Entering uses `animate-panel-enter`; rows use `stagger-rows`. No new motion or surface tokens.
- Unavailable states render inside the picker: no connection (link to `/settings`), release access missing (text naming Contents read and the installation owner), provider unavailable (retry).
- Demo: the seed links release `v4.13` to the fixed demo problem. Change and remove buttons are disabled with the existing demo note, as `GitHubIssueSection` does.

## Risks / Trade-offs

- [Contents read lets the app read source code in the selected repository] → Tokens request it only for release reads, and the token is revoked after each operation. The maintainer must accept this change to `github-connection` (Q1 in the plan).
- [Existing installations lack the permission until the owner accepts it] → Issue features stay up; the picker names the missing grant.
- [422 status for an ungranted permission is not verified live] → Mocked tests cover it; the PR says whether a live check ran.
- [Snapshot goes stale if a release is renamed or deleted] → Accepted (D2). The link still points to GitHub, which shows its own 404.

## Migration Plan

1. Deploy code and migration. No data backfill; existing problems have no release.
2. Operator adds Repository permission Contents: Read-only to the GitHub App registration. GitHub asks each installation owner to accept.
3. Until accepted, the picker shows the release-access message. Rollback: revert the code; the `FixRelease` table can stay or be dropped by reverse migration.
