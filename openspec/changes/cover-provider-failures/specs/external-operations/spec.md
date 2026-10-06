# Spec Delta

## MODIFIED Requirements

### Requirement: Bounded retries
Retries SHALL use capped exponential backoff with random jitter and honour provider `Retry-After` values. Validation failures MUST NOT be retried indefinitely.

#### Scenario: GitHub rate limit
- **WHEN** GitHub responds 429 with Retry-After
- **THEN** the next attempt is scheduled no earlier than that delay

#### Scenario: Rate-limited issue creation
- **WHEN** GitHub rate-limits a request made while creating an approved issue
- **THEN** the creation is queued again no earlier than the provider's delay, and fails with a rate-limit error once the retry cap is reached

### Requirement: Revoked credentials pause work
Invalid or revoked credentials SHALL disable the connection, pause dependent operations, and show reconnection guidance. They MUST NOT cause a retry loop. Reconnection MUST NOT release obsolete approvals.

#### Scenario: Slack token revoked
- **WHEN** Slack returns `token_revoked` during a send
- **THEN** the connection is disabled, unsent deliveries are cancelled, and settings ask the owner to reconnect

#### Scenario: GitHub installation refused
- **WHEN** GitHub rejects the app's credentials, or refuses an installation token because the installation is gone or suspended, during issue creation or sync
- **THEN** every connection bound to that installation is disabled with reconnection guidance, the creation is cancelled without a write, and its issues stop syncing until the owner reconnects
