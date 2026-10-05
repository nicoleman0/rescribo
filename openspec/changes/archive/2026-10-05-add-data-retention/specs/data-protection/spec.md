# Spec Delta

## ADDED Requirements

### Requirement: Inbound payload retention
The system SHALL clear the stored payload of each successfully processed inbound receipt within seven days. It SHALL keep only provider, delivery ID, event, status, and timestamps for deduplication.

#### Scenario: Old successful receipt
- **WHEN** a successful receipt is older than seven days
- **THEN** its payload is empty and a redelivery with the same ID is still recognised as a duplicate

#### Scenario: Failed receipt
- **WHEN** a receipt has not succeeded
- **THEN** its payload is kept so it can be retried or inspected

### Requirement: Documented backup retention
Operator documentation SHALL state a default backup retention of 30 days that the operator can change, and that deleted data persists in backups until they expire. The product MUST NOT claim immediate erasure from backups.

#### Scenario: Owner deletes a report
- **WHEN** an owner asks whether a deleted report is gone everywhere
- **THEN** the documentation says backups keep it for 30 days unless the operator set a different policy

### Requirement: Verified restore
The project SHALL provide a restore procedure and a smoke test that restores a backup into a fresh database and checks the application starts and reads restored records.

#### Scenario: Restore smoke test
- **WHEN** the restore smoke test runs against a recent backup
- **THEN** it passes only if migrations are current and a restored report can be read through the API

## MODIFIED Requirements

### Requirement: Workspace deletion
An owner SHALL be able to delete the workspace after typing its slug. Deletion cancels pending sends, removes credentials, and removes all tenant records. Deletion SHALL revoke the Slack bot token with Slack before removing it; if revocation fails, deletion SHALL still complete. GitHub installations are not uninstalled. Upstream Slack messages and GitHub issues are not deleted.

#### Scenario: Workspace deleted
- **WHEN** an owner confirms workspace deletion
- **THEN** no report, problem, follow-up, activity, operation, invitation, or credential for that workspace remains

#### Scenario: Slack revocation fails
- **WHEN** an owner confirms workspace deletion and Slack rejects or does not answer the token revocation
- **THEN** the workspace is still deleted and no credential for it remains
