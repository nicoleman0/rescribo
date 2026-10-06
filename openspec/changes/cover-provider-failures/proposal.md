# Proposal

Delivers #18.

## Why

The `external-operations` spec already covers rate limits, revoked credentials, and uncertain writes. Slack follows it. GitHub does not in two places:

- A 429 during issue creation fails the operation for good, when the spec says to retry after `Retry-After`.
- Lost GitHub credentials mark one operation failed or one issue inaccessible, then keep retrying, when the spec says to disable the connection and stop.

Several failure paths in #18 also have no test.

## What Changes

- Retry backoff adds random jitter. The code does this already; the spec now says so.
- A rate-limited GitHub issue creation is queued again no earlier than the provider's delay. After the retry cap it fails with `rate_limited`.
- When GitHub refuses the installation (401 on any request; 403 without rate limiting or 404 when minting an installation token), every connection bound to that installation is disabled with an error that tells the owner how to reconnect. The failing creation is cancelled and active issues stop syncing. Queued creations cancel at their prewrite check, as they do today for any inactive connection.
- Add tests for retry timing, read timeouts, a 410 on sync, an applied issue-deleted webhook, and the new GitHub paths above.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `external-operations`: "Bounded retries" names jitter and gains a scenario for rate-limited issue creation. "Revoked credentials pause work" gains a GitHub scenario.

## Impact

- `backend/operations/tasks.py` (issue creation error handling), `backend/feedback/engineering_issues.py` (sync failure handling, installation fan-out), `backend/integrations/github_app/client.py` (error carries the failed request), `backend/connections/errors.py` and `backend/feedback/serializers.py` (error copy).
- New and extended backend tests. GitHub is mocked; no live provider verification.
- No API shape, schema, or migration changes.
