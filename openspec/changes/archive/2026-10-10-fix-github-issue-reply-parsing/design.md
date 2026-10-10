# Design

## Context

Every issue read or write goes through `selected_repository` (`backend/integrations/github_app/repository.py`). It:

1. mints an installation token restricted to one repository by stable ID (`repository_ids: [id]`),
2. reads `GET /repositories/{id}` with that token and checks the reply's `id` equals the bound ID,
3. yields the token and the reply's `full_name` (the canonical name).

The caller then requests `/repos/{canonical}/issues...` with that token. The client treats redirects as errors, so a moved repository or issue answers 301 and is never followed.

`parse_issue_payload` then demanded a second proof inside the issue reply: `repository.id` and `repository.full_name`. Real replies have neither. The key set of a real single-issue reply, read on 10 Oct 2026 with a repository-restricted installation token, has `repository_url` (`https://api.github.com/repos/{owner}/{repo}`), `html_url`, and `url`, all by name. No field carries the repository ID. GitHub's REST schema marks `repository_url` as required on an issue and `repository` as optional (https://docs.github.com/en/rest/issues/issues).

`EngineeringIssueSnapshot.repository_id` and `.repository_name` have these readers:

- `record_created_issue` (`feedback/engineering_issues.py`): rejects the snapshot if `repository_id` differs from the locked connection's ID, then writes `repository_name` to `connection.repository`.
- `sync_issue` (same file): writes `repository_name` to `connection.repository`.
- `resolve_issue_link` and `fetch_current_issue`: compare `repository_id` with the expected ID.
- One equality assertion in `test_github_issue_lifecycle.py`.

**Prototyped before planning.** The `repository` line was removed from the seven fakes, the backend tests were run, and the files were restored. 30 issue tests failed on the current code, covering all four callers: create 6, recovery 1, link 7, fetch and sync 16. (17 matching tests also failed because the run skipped `task matcher-build`. They are unrelated.)

## Goals / Non-Goals

**Goals:**
- Real replies from create, read, and list parse.
- A reply that names another repository is still rejected, in every caller.
- A renamed or transferred repository is still followed by its stable ID.
- A failed create names its exception type in the log.
- No test fake carries a key the real API does not send.

**Non-Goals:**
- Frontend, API contract, migrations, specs.
- How uncertain operations are shown or recovered in the UI.
- Webhook payload parsing (`parse_issue_event`). GitHub does send a top-level `repository` there and it does not use this parser.
- Consolidating the seven fakes into one builder (question 2).
- #146, #148, #149.

## Decisions

**The caller supplies the identity. The parser checks that the reply names it.**

```python
def parse_issue_payload(
    issue: Mapping[str, Any],
    *,
    repository_id: str,
    repository_name: str,
    error: type[Exception],
) -> EngineeringIssueSnapshot:
```

`repository_id` and `repository_name` are copied onto the snapshot. The parser requires:

- `repository_url` equals `https://api.github.com/repos/{repository_name}`, compared case-insensitively. A different value raises "GitHub returned an issue from another repository." A missing or non-string value raises the existing "incomplete issue payload".
- `html_url` path equals `/{repository_name}/issues/{number}` (the existing check, now against the caller's name).

Both keyword arguments are required, so no caller can parse a reply without stating which repository it asked.

Alternatives:
- Parse the name out of `repository_url` and put it on the snapshot. The identity would again come from the reply, which the brief rules out.
- Drop `repository_id` and `repository_name` from the snapshot and pass the canonical name to `record_created_issue` and `sync_issue` separately. It changes four more call sites and the typed contract in `docs/DEVELOPMENT.md` for no gain.
- Check `html_url` only. `repository_url` is the API's own statement of the repository and costs four lines.

**Remove the two comparisons that became tautologies.** `resolve_issue_link` and `fetch_current_issue` compare `snapshot.repository_id` with the `expected_repository_id` they just passed in. That can no longer fail, so the lines go. The check in `record_created_issue` stays: it compares the ID the read was made under with the connection row locked later, which catches a rebinding between the read and the write.

**`_recover` returns the canonical name with its matches.** `reconcile_github_issue_create` parses the match outside `_recover`, after the count check, and needs the name. Return type becomes `tuple[str, list[dict[str, object]]]`. Parsing inside `_recover` would turn a malformed second match into `recovery_unavailable` where today it is `multiple_marker_matches`.

**The API host is a literal in `issues.py`**, next to the existing `github.com` literal for `html_url`. `settings.py` holds the client's `base_url`. Sharing one constant is a refactor and is left out.

**The warnings name the exception type only.** `type(error).__name__`, no message, no payload. `GitHubAPIError` messages are safe, but other exceptions (`KeyError`, `ValueError` from a parser) can quote input.

### How each caller stays safe

All four rely on the same three facts: the token works only for the bound repository ID, the canonical name was read by that ID with that token a moment earlier, and the reply must name that canonical repository.

| Caller | Repository ID passed | Name passed | Extra checks that remain |
| --- | --- | --- | --- |
| Create task | `operation.repository_id` | `canonical` | Before the write: `connection.repository_id == operation.repository_id`. After it, under lock: the same, plus `binding_revision`. `record_created_issue` compares the snapshot ID with the locked connection. A token for another repository cannot write: GitHub refuses it. |
| Link | `expected_repository_id` (= `connection.repository_id`) | `expected_repository` (= `canonical`) | A URL reference naming another repository is rejected before any request. `snapshot.number == number`. Under lock: binding unchanged, then `record_created_issue`. |
| Fetch after webhook, refresh, sync | `expected_repository_id` (= `connection.repository_id`) | `expected_repository` (= `canonical`) | `snapshot.issue_id` must equal the stored stable issue ID. Before and after the read: `issue.repository_id == connection.repository_id`. |
| Recovery | `operation.repository_id` | `canonical` from `_recover` | The issue body must contain this operation's marker. Under lock: `repository_id` and `binding_revision` unchanged, then `record_created_issue`. |

**Repository renamed or transferred to another owner (same ID).** `GET /repositories/{id}` answers with the new `full_name`. The request goes to the new name and the reply names it, so the parse passes. The snapshot carries the new name and `record_created_issue` or `sync_issue` writes it to `connection.repository`, as today. A reply that still named the old repository would be rejected. If the new owner has not installed the App, token creation fails and the existing access-lost handling applies.

**Issue transferred to another repository.** `GET /repos/{canonical}/issues/{n}` answers 301. The client raises, link reports "not found", and sync reports `access_lost`. Unchanged. If GitHub ever answered 200 with the moved issue, `repository_url` would name the other repository and the parser would reject it.

**Rebinding to a different repository.** Unchanged. `binding_revision` and `repository_id` are compared under lock in every caller.

## Risks / Trade-offs

- [The reply is tied to the repository by name, not by ID. If the repository is renamed and a public repository takes the old name between the lookup and the issue request, a read could return the other repository's issue with matching URLs] → Accepted, see question 1. GitHub's reply has no repository ID to check, so the old ID comparison never protected a real request. The window is two back-to-back requests. Create is not exposed (the token cannot write elsewhere). Sync is not exposed (stable issue ID must match). Recovery needs this operation's marker in the body. Only link is exposed, and only if the repository's own admin renames it and recreates the name at that moment.
- [`repository_url` is now required. A real reply without it would be rejected, as the `repository` object was] → It is present in the real single-issue reply and required in GitHub's schema for create, read, and list. The create and list replies were not captured live. The coordinator's retest after merge covers create and recovery.
- [Cannot be verified against live GitHub in this worktree] → By design: `.env` has no credentials. Retest journeys 9, 10, and 13 and recover the existing uncertain operation after merge.
- [Seven fakes still repeat one shape] → See question 2.
