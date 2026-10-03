# data-protection Specification

## Purpose

Protects credentials and customer content at rest and in logs, and defines what disconnect and workspace deletion remove.

## Requirements

### Requirement: Encrypted credentials
Provider credentials SHALL be encrypted with a maintained cryptography library and an operator-managed key stored outside the database.

#### Scenario: Database dump
- **WHEN** someone reads the connection table without the key
- **THEN** no usable credential is visible

### Requirement: No secrets or content in logs
Logs and telemetry MUST NOT contain tokens, response URLs, invite or reset codes, raw message bodies, report text, or customer content. Error records SHALL store safe categories, not free-form exception text.

#### Scenario: Provider error logged
- **WHEN** a Slack call fails
- **THEN** the log has the error category and operation ID, without the message body or token

### Requirement: Disconnect keeps business records
Disconnecting a provider SHALL delete usable credentials and stop pending sends. It MUST NOT erase stored reports, problems, or history.

#### Scenario: Slack disconnected
- **WHEN** an owner disconnects Slack
- **THEN** credentials are removed, unsent deliveries are cancelled, and reports remain

### Requirement: Short-lived capture context
Slack capture contexts SHALL expire after 15 minutes and be deleted by a periodic sweep.

#### Scenario: Abandoned modal
- **WHEN** a member opens the capture modal and never submits
- **THEN** its context is deleted after expiry

### Requirement: Workspace deletion
An owner SHALL be able to delete the workspace after typing its slug. Deletion cancels pending sends, removes credentials, and removes all tenant records. Upstream Slack messages and GitHub issues are not deleted.

#### Scenario: Workspace deleted
- **WHEN** an owner confirms workspace deletion
- **THEN** no report, problem, follow-up, activity, operation, invitation, or credential for that workspace remains
