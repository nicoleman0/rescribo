# Design

## Context

- `next_retry_at` (`backend/operations/retries.py`) already adds jitter on top of the backoff or `Retry-After` delay, so a jittered retry is never earlier than the provider asked.
- Issue creation (`process_github_issue_create`) treats every GitHub error below 500 as a conclusive failure. Rate limits land there.
- Sync (`sync_issue`) maps 401, 403, 404, and 410 to an `inaccessible` issue and schedules another attempt, including when the failure was minting the installation token.
- `apply_installation_webhook` already disables every connection bound to an installation and marks its active issues when GitHub reports the installation deleted or suspended. Revalidation reactivates the connection later.
- Queued creations already cancel at their prewrite check when the connection is not active, and the dispatcher skips syncs for inactive connections. Disabling the connection is enough to pause dependent work.

## Goals / Non-Goals

**Goals:**
- One code path disables an installation's connections, whether a webhook or a failed request found the problem.

**Non-Goals:**
- Retrying other conclusive pre-write failures, such as a 5xx before the create request. They still fail and the member approves again.
- Slack changes. Slack already meets both requirements.
- Changing revalidation, which still only logs a failed check.

## Decisions

- **Classify by the failed request.** `GitHubAPIError` gains the operation name it already formats into its message. A 401 on any request, or a 403 that is not a rate limit or a 404 on `installation token creation`, is an installation failure. A 403, 404, or 410 on an issue request stays an issue-level `inaccessible` result. Alternative: a separate exception from `selected_repository`. Rejected because sync and creation both catch `GitHubAPIError` already, and the client is the one place that knows which request failed.
- **Codes.** 404 on token creation maps to `access_lost` and 403 to `installation_suspended`, the same codes the webhook uses. 401 maps to a new `github_credentials_invalid` code, because the copy differs: the operator, not the installation owner, has to fix the app key.
- **Extract the fan-out.** Move the disable-and-mark loop out of `apply_installation_webhook` into `disable_github_installation(installation_id, error_code, issue_access)`, in a refactor commit before any behaviour change. The webhook and both failure paths call it after their own transaction ends, so it takes workspace locks in the same order as today.
- **Cancel the failing creation.** It becomes `cancelled` with `safe_error="disconnected"`, as a revoked Slack token does to an unsent delivery. No write was attempted, so it is not `uncertain`.
- **Requeue on rate limit.** A rate-limited creation goes back to `queued` with `due_at` from `next_retry_at` and its lease cleared. The dispatcher already picks up due queued operations. Once `attempts` reaches `MAX_ATTEMPTS` it fails with `rate_limited`. This applies only when no write began, or when the create request itself returned the rate-limit response, since both are conclusive.

## Risks / Trade-offs

- [A single bad 401 disables every workspace sharing the installation] → A 401 against a freshly minted token means the app or installation is broken for everyone. Reconnecting runs revalidation, which restores the connection.
- [GitHub may return other codes for a removed repository during token creation] → I don't know the exact code. Those cases stay on the existing path; this change does not guess.
