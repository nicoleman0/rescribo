# Tasks

## 1. Retry timing and read coverage

- [x] 1.1 Add unit tests for `next_retry_at`: doubling, the cap at ten doublings, `Retry-After` as a floor, zero delay, and the jitter bound. Verify they pass against the current code.
- [x] 1.2 Add sync tests for a read timeout (issue keeps `ok` access, `provider_unavailable`, retry scheduled) and a 410 on the issue request (`inaccessible`). Verify they pass.
- [x] 1.3 Add a test that applies an issue `deleted` webhook to a linked issue end to end. Verify the issue ends `deleted` with no retry scheduled.

## 2. Extract the installation fan-out (refactor, own commit)

- [ ] 2.1 Move the disable-and-mark loop from `apply_installation_webhook` into `disable_github_installation`, with no behaviour change. Verify the existing installation webhook and shared-binding tests pass unchanged.

## 3. Rate-limited issue creation

- [ ] 3.1 Store the operation name on `GitHubAPIError`. Verify with a client test.
- [ ] 3.2 Requeue a rate-limited creation with `due_at` from `next_retry_at`, and fail it with `rate_limited` at `MAX_ATTEMPTS`. Add `rate_limited` operation copy. Verify with tests for a 429 on token creation, a 429 on the create request, a `Retry-After` floor on `due_at`, and the cap.

## 4. Refused GitHub installation

- [ ] 4.1 Add the installation-failure classifier and the `github_credentials_invalid` connection error copy. Verify with unit tests for 401 on any request, 403 and 404 on token creation, a rate-limited 403, and 403/404/410 on an issue request.
- [ ] 4.2 On an installation failure during creation, cancel the operation with `disconnected` and call `disable_github_installation`. Add `disconnected` operation copy. Verify that every connection on the installation is disabled, no create request is sent, and a second queued creation cancels at its prewrite check.
- [ ] 4.3 On an installation failure during sync, call `disable_github_installation` and schedule no retry for the issue. Verify that the issue is marked, the dispatcher no longer selects it, and revalidation after reconnect restores sync without re-queuing cancelled creations.

## 5. Checks

- [ ] 5.1 Run `npx @fission-ai/openspec validate --all --strict` and verify it passes.
- [ ] 5.2 Run `task check test build schema-check` and `task worker-check` with PostgreSQL and Redis running, and verify both pass.

## Workflow follow-up

- Archive the change in the PR that completes #18.
