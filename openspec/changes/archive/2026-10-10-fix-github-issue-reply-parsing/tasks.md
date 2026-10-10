# Tasks

Delivers #150. Bug fix; `skip_specs: true`. Backend only. Change only the files named below. Do not touch `backend/feedback/engineering_issues.py`, the frontend, the API schema, or `openspec/specs/`.

Fix the fakes and write the tests first (groups 1 and 2) and see them fail, then make the fix (group 3).

Run backend tests with `task test-backend` (it builds the matcher first). A bare `uv run pytest` fails 17 unrelated matching tests when the matcher binary is missing.

## 1. Make the issue reply fakes match real replies

- [x] 1.1 Delete the `"repository": {"id": ..., "full_name": ...},` line that follows `"repository_url"` in each of these seven fakes. Keep `repository_url`. Change nothing else in them.
  - `backend/tests/issue_world.py` (`World.github_says`)
  - `backend/tests/test_github_issue_operations.py` (`CREATED_ISSUE`)
  - `backend/tests/test_github_issue_lifecycle.py` (`ISSUE_PAYLOAD`)
  - `backend/tests/test_engineering_issue_link_api.py` (`ISSUE_PAYLOAD`)
  - `backend/tests/test_engineering_issue_webhook.py` (`ISSUE_PAYLOAD`)
  - `backend/tests/test_github_reconciliation.py` (`ISSUE_PAYLOAD`)
  - `backend/tests/test_engineering_issue_refresh_api.py` (`ISSUE_PAYLOAD`)

  Leave webhook payload fakes alone: `issue_payload()` in `test_github_issue_lifecycle.py`, `test_receipt_retention.py`, and `test_github_webhook_view.py` have a top-level `repository`, which GitHub does send in webhooks.
- [x] 1.2 Verify no issue reply fake still has the key: `grep -n -A1 '"repository_url"' backend/tests/*.py | grep '"repository":'` prints nothing.
- [x] 1.3 Run `task test-backend`. Verify: exactly 30 tests fail, all with the parser rejecting the reply. They are in `test_github_issue_operations.py` (6), `test_worker_problem_lock_concurrency.py` (1), `test_github_issue_lifecycle.py` (3), `test_engineering_issue_link_api.py` (4), `test_workspace_lock_concurrency.py` (3), `test_engineering_issue_webhook.py` (6), `test_github_reconciliation.py` (1), `test_issue_event_ordering.py` (4), `test_follow_up_concurrency.py` (2). If the count differs, stop and ask.

## 2. New tests

Reuse each file's existing helpers. Do not change existing tests.

- [x] 2.1 `backend/tests/test_github_issue_lifecycle.py`: import `parse_issue_payload` from `integrations.github_app.issues` and add:

  ```python
  FOREIGN_REPLY = {
      **ISSUE_PAYLOAD,
      "repository_url": "https://api.github.com/repos/other/disposable",
      "html_url": "https://github.com/other/disposable/issues/7",
  }


  def test_issue_reply_identity_comes_from_the_caller() -> None:
      snapshot = parse_issue_payload(
          ISSUE_PAYLOAD,
          repository_id="999",
          repository_name="owner/disposable",
          error=IssueLinkError,
      )
      assert (snapshot.repository_id, snapshot.repository_name) == ("999", "owner/disposable")


  @pytest.mark.parametrize(
      ("reply", "message"),
      [
          (FOREIGN_REPLY, "another repository"),
          (
              {**ISSUE_PAYLOAD, "repository_url": FOREIGN_REPLY["repository_url"]},
              "another repository",
          ),
          ({**ISSUE_PAYLOAD, "html_url": FOREIGN_REPLY["html_url"]}, "mismatched issue URL"),
          ({k: v for k, v in ISSUE_PAYLOAD.items() if k != "repository_url"}, "incomplete"),
      ],
  )
  def test_issue_reply_must_name_the_callers_repository(reply: dict, message: str) -> None:
      with pytest.raises(IssueLinkError, match=message):
          parse_issue_payload(
              reply, repository_id="999", repository_name="owner/disposable", error=IssueLinkError
          )


  def test_issue_reply_follows_a_renamed_repository() -> None:
      renamed = {
          **ISSUE_PAYLOAD,
          "repository_url": "https://api.github.com/repos/owner/renamed",
          "html_url": "https://github.com/owner/renamed/issues/7",
      }
      snapshot = parse_issue_payload(
          renamed, repository_id="999", repository_name="owner/renamed", error=IssueLinkError
      )
      assert snapshot.repository_name == "owner/renamed"
      with pytest.raises(IssueLinkError, match="another repository"):
          parse_issue_payload(
              ISSUE_PAYLOAD,
              repository_id="999",
              repository_name="owner/renamed",
              error=IssueLinkError,
          )
  ```

- [x] 2.2 Same file, one test per reader. Each uses a handler that returns `httpx.Response(200, json=FOREIGN_REPLY)`:
  - `test_resolve_issue_link_rejects_a_reply_from_another_repository`: `resolve_issue_link(..., reference="7")` raises `IssueLinkError` matching `"another repository"`.
  - `test_apply_issue_event_rejects_a_reply_from_another_repository`: `apply_issue_event(..., event=closed_event(), stored_updated_at=None)` raises `InvalidWebhookPayload` matching `"another repository"`.
- [x] 2.3 `backend/tests/test_github_issue_operations.py`, create task. Add `import logging`. Define `FOREIGN_ISSUE` and `RENAMED_ISSUE` from `CREATED_ISSUE` with `repository_url` and `html_url` naming `other/widgets` and `acme/renamed`. Follow the setup of `test_approved_content_is_the_only_content_written_and_linked`.
  - `test_created_reply_from_another_repository_is_not_linked`: `client.create_issue.return_value = dict(FOREIGN_ISSUE)`. Assert the operation is `UNCERTAIN` and `EngineeringIssue.objects.filter(problem=problem).exists()` is false.
  - `test_create_follows_a_renamed_repository`: keep the connection from `make_connection`. Set `client.get_repository_by_id.return_value = {"id": 999, "full_name": "acme/renamed"}` and `client.create_issue.return_value = dict(RENAMED_ISSUE)`. Assert the operation is `SUCCEEDED`, `client.create_issue.call_args.kwargs["name"] == "renamed"`, and after `connection.refresh_from_db()`, `connection.repository == "acme/renamed"`.
  - `test_create_failure_after_the_write_logs_only_the_exception_type(caplog)`: `client = fake_provider(create_error=RuntimeError("customer text"))`. Run the task inside `caplog.at_level(logging.WARNING, logger="operations.tasks")`. Assert `"GitHub create failed during write: RuntimeError" in caplog.messages` and `"customer text" not in caplog.text`.
- [x] 2.4 Same file, recovery. Follow the setup of `test_marker_recovery_paginates_and_ignores_pull_requests` (operation set to `UNCERTAIN`, `marker` built the same way).
  - `test_recovery_by_reference_links_the_marked_issue`: call `request_recovery(actor=actor, problem_id=problem.pk, operation_id=operation.pk, reference="7")`, set `client.get_issue.return_value = {**CREATED_ISSUE, "body": marker}`, run `reconcile_github_issue_create`. Assert the operation is `SUCCEEDED` and the active issue's `issue_id == "555"`.
  - `test_recovery_does_not_link_a_reply_from_another_repository(caplog)`: `client.list_issues.side_effect = [([{**FOREIGN_ISSUE, "body": marker}], False)]`. Assert the operation stays `UNCERTAIN` with `safe_error == "recovery_unavailable"`, no `EngineeringIssue` exists for the problem, and `"GitHub issue recovery failed: IssueLinkError" in caplog.messages`.
- [x] 2.5 `backend/tests/test_engineering_issue_link_api.py`: `test_link_rejects_a_reply_from_another_repository`. `github_mock(issue=...)` with `ISSUE_PAYLOAD` whose `repository_url` and `html_url` name `other/widgets`; `link(client, actor, problem)`. Assert 400, `reason == "issue_reference_rejected"`, and no `EngineeringIssue` for the problem.
- [x] 2.6 `backend/tests/test_engineering_issue_webhook.py`, sync path. Follow the setup of `test_closed_event_sets_needs_review_and_keeps_state_reason`.
  - `test_sync_follows_a_renamed_repository`: build the mock with a closed reply whose `repository_url` and `html_url` name `acme/renamed`, and set `get_repository_by_id.return_value = {"id": 999, "full_name": "acme/renamed"}` on it. After `apply_issue_webhook`, assert `issue.state == "closed"` and `connection.repository == "acme/renamed"` (refresh both).
  - `test_sync_does_not_apply_a_reply_from_another_repository`: closed reply naming `other/widgets`. Assert `issue.state` is unchanged from before the call, `issue.sync_error == "provider_unavailable"`, and `problem.needs_review` is false.
- [x] 2.7 Run `task test-backend`. Verify the 30 failures from 1.3 remain and the parser acceptance tests fail with `TypeError` (unexpected keyword) or the "incomplete" message. Negative tests for create, link, and sync can pass before the fix because the old parser already rejects those replies as incomplete. This run had 43 failed and 998 passed; the 30 original failures and 13 new failures were expected until group 3.

## 3. Fix

- [x] 3.1 `backend/integrations/github_app/issues.py`, `parse_issue_payload`. New signature and docstring:

  ```python
  def parse_issue_payload(
      issue: Mapping[str, Any],
      *,
      repository_id: str,
      repository_name: str,
      error: type[Exception],
  ) -> EngineeringIssueSnapshot:
      """Parse an issue reply read from `repository_name`.

      GitHub names an issue's repository only by URL, so the caller passes the
      identity it verified before the read and the reply must name the same one.
      """
  ```

  In the body:
  - Replace the three `repository...` reads with `repository_url = issue.get("repository_url")`.
  - In the completeness check, replace the four `repository_id` and `repository_name` conditions with `and isinstance(repository_url, str)`.
  - After the timestamp check and before the `html_url` checks, add:

    ```python
    if repository_url.lower() != f"https://api.github.com/repos/{repository_name}".lower():
        raise error("GitHub returned an issue from another repository.")
    ```

  - Leave the `html_url` checks as they are. They now use the `repository_name` argument.
  - In the returned snapshot use `repository_id=repository_id` (it is already a `str`; drop the `str(...)`).
- [x] 3.2 Same file, `resolve_issue_link`: pass `repository_id=expected_repository_id, repository_name=expected_repository` to `parse_issue_payload`. Delete the `snapshot.repository_id != expected_repository_id` check and its `raise`. Keep the `snapshot.number != number` check.
- [x] 3.3 `backend/integrations/github_app/webhooks.py`, `fetch_current_issue`: pass the same two arguments. Delete the `snapshot.repository_id != expected_repository_id` check and its `raise`. Keep the `snapshot.issue_id != issue_id` check.
- [x] 3.4 `backend/operations/tasks.py`, `process_github_issue_create`:
  - Parse with `parse_issue_payload(created, repository_id=operation.repository_id, repository_name=canonical, error=IssueLinkError)`.
  - Replace the warning with:

    ```python
    logger.warning(
        "GitHub create failed during %s: %s",
        "write" if write_started else "preflight",
        type(error).__name__,
    )
    ```
- [x] 3.5 Same file, recovery:
  - `_recover` returns `tuple[str, list[dict[str, object]]]`: `return canonical, []`, `return canonical, [row]`, and `return canonical, matches`.
  - In `reconcile_github_issue_create`: `canonical, matches = _recover(hint)`, then `parse_issue_payload(matches[0], repository_id=hint.repository_id, repository_name=canonical, error=IssueLinkError)`.
  - Replace the warning with `logger.warning("GitHub issue recovery failed: %s", type(error).__name__)`.
- [x] 3.6 Verify nothing else calls the parser or reads the removed checks: `grep -rn "parse_issue_payload(" backend --include='*.py'` shows the four callers and the new tests, each with both keyword arguments. `git diff --stat backend/feedback/engineering_issues.py` is empty.
- [x] 3.7 Run `task test-backend`. Verify: 0 failed. Record the passed count for the PR.

## 4. Repository checks

- [x] 4.1 `npx @fission-ai/openspec validate --all --strict` passes.
- [x] 4.2 `task check test build schema-check` passes with PostgreSQL and Redis running (see `.claude/brief.md` for the ports; do not start or stop services). Record the test counts for the PR. `schema-check` must report no API change.
- [x] 4.3 `RESCRIBO_E2E_API_PORT=8150 RESCRIBO_E2E_FRONTEND_PORT=5150 task e2e` passes. Record the counts for the PR.
- [x] 4.4 No dev server is left on 8150 or 5150. `task worker-check` is not needed: no worker wiring changes.

## Workflow follow-up

- Archive this change in the PR that completes #150 (`/opsx:archive`).
- PR milestone: none.
- PR "Decisions to review": the reply is tied to the repository by name because GitHub sends no repository ID (design, first risk); `repository_url` is now required; the recovery warning also names the exception type.
- PR Checks must say the fix is covered by mocked tests only. Live verification is the coordinator's retest: journeys 9, 10, and 13, and recovery of the existing uncertain operation.
- PR Screenshots: "Not applicable: backend only".
