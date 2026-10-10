# Proposal

Delivers GitHub issue #150 (no milestone). Found by the manual end-to-end check (#57).

## Why

Publishing a new GitHub issue creates the issue on GitHub but does not link it. The create operation ends `uncertain` with `write_outcome_unknown` and the problem stays unlinked.

`parse_issue_payload` requires `issue["repository"]["id"]` and `issue["repository"]["full_name"]`. GitHub's replies for creating an issue, reading one issue, and listing a repository's issues carry `repository_url` and no `repository` object. Every real reply is rejected with "GitHub returned an incomplete issue payload."

The parser has four callers and all four are broken against real replies:

| Caller | What a real reply does today |
| --- | --- |
| Create task (`operations/tasks.py`) | Observed live. The operation ends `uncertain` after GitHub created the issue. |
| Link an existing issue (`issues.py`, `resolve_issue_link`) | The link request is refused with 400 `issue_reference_rejected`. |
| Fetch after a webhook, refresh, or scheduled sync (`webhooks.py`, `fetch_current_issue`) | The sync fails with `provider_unavailable` and retries. A closure never reaches the problem. |
| Recovery through "Check creation result" (`operations/tasks.py`) | Recovery ends `recovery_unavailable` and retries. The uncertain operation is never resolved. |

The mocked tests pass because seven test fakes include `"repository": {"id": 999, "full_name": ...}`, which the real API does not send.

`engineering-issues` requires linking an existing issue, creating one after approval, recovering an uncertain create by its marker, and applying closure. The code diverges from it.

## What Changes

- `parse_issue_payload` takes the repository identity from its caller: the bound stable repository ID and the canonical name from the repository lookup. It no longer reads a `repository` object.
- The parser requires the reply's `repository_url` and `html_url` to name the caller's repository, and rejects the reply otherwise.
- All four callers pass the identity they already verified.
- The two comparisons of `snapshot.repository_id` with the expected ID in `resolve_issue_link` and `fetch_current_issue` are removed. They would compare a value with itself.
- The create task's failure warning names the exception type. The recovery warning does the same (question 3 in the plan summary).
- The seven issue reply fakes lose the `repository` object.
- New tests cover each caller: a reply that names another repository is rejected, and a renamed repository is followed.

No frontend, API contract, migration, or spec change. The change sets `skip_specs: true`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. The code is brought back in line with `engineering-issues` and `github-connection`.

## Impact

- `backend/integrations/github_app/issues.py` (`parse_issue_payload`, `resolve_issue_link`).
- `backend/integrations/github_app/webhooks.py` (`fetch_current_issue`).
- `backend/operations/tasks.py` (create task, `_recover`, `reconcile_github_issue_create`, two warnings).
- `backend/feedback/engineering_issues.py`: no change. It keeps reading `snapshot.repository_id` and `snapshot.repository_name`.
- Tests: `backend/tests/issue_world.py`, `test_github_issue_operations.py`, `test_github_issue_lifecycle.py`, `test_engineering_issue_link_api.py`, `test_engineering_issue_webhook.py`, `test_github_reconciliation.py`, `test_engineering_issue_refresh_api.py`.
