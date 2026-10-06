# external-operations Specification

## Purpose

Makes inbound provider events and outbound Slack and GitHub writes durable, deduplicated, and recoverable without blind resends.

## Requirements

### Requirement: Transactional outbox
A state change and the external operation it requires SHALL commit in one database transaction. Dispatch SHALL happen after commit, and a periodic dispatcher SHALL recover operations that never reached the broker.

#### Scenario: Broker down after commit
- **WHEN** the broker is unavailable when a committed operation is dispatched
- **THEN** the operation stays pending and the periodic dispatcher sends it later

### Requirement: Verified and deduplicated receipts
Inbound events SHALL be signature-verified before storage. GitHub receipts SHALL be persisted before responding, within GitHub's ten-second limit. Deduplication SHALL use GitHub delivery IDs, Slack event IDs for lifecycle events, and deterministic keys for shortcuts and actions.

#### Scenario: Slack event retried
- **WHEN** Slack retries a lifecycle event with an event ID already stored
- **THEN** it is acknowledged and not processed again

### Requirement: Leased execution with prewrite checks
Workers SHALL claim operations atomically with expiring leases. Before an external write they SHALL recheck workspace, connection, membership where applicable, and the approved input version.

#### Scenario: Approval invalidated while queued
- **WHEN** a queued send's draft is edited before a worker claims it
- **THEN** the worker cancels the send instead of calling Slack

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

### Requirement: No exactly-once claims
A non-idempotent write without a conclusive result SHALL be marked `uncertain` and reconciled before any retry. The system MUST NOT claim exactly-once delivery.

#### Scenario: Timeout on write
- **WHEN** a provider write times out
- **THEN** the operation is `uncertain`, not failed or succeeded

### Requirement: Connection health
Connection settings SHALL show queued, failed, and uncertain operations, the last successful API request, the last successful issue reconciliation, and actionable errors. Webhook silence alone MUST NOT count as a health failure.

#### Scenario: Quiet repository
- **WHEN** no webhook has arrived for a day and API calls succeed
- **THEN** the GitHub connection shows healthy
