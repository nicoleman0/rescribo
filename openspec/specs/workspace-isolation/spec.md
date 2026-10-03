# workspace-isolation Specification

## Purpose

Keeps every product workspace's records, credentials, and background work invisible and unusable from any other workspace.

## Requirements

### Requirement: Every record belongs to a verified workspace
Every business record, lookup, background job, suggestion, and external operation SHALL belong to exactly one workspace, resolved from verified membership or a verified provider identity.

#### Scenario: Background task
- **WHEN** a worker processes a job
- **THEN** it resolves the acting membership or connection for the job's workspace and rechecks it before any write

### Requirement: Foreign records are not found
A request for a record in a workspace where the caller has no active membership SHALL return not found. The system MUST NOT rely on UUID secrecy for authorisation.

#### Scenario: Guessed identifier
- **WHEN** a member of workspace A requests a report ID that belongs to workspace B
- **THEN** the response is 404 and reveals nothing about the record

### Requirement: Scoped search and aggregation
The system SHALL apply the workspace filter before search, filtering, counting, aggregation, or candidate selection.

#### Scenario: Search count
- **WHEN** a member searches the inbox for text that also appears in another workspace's reports
- **THEN** results and counts include only the member's workspace

### Requirement: Scoped references
Every foreign-key assignment, including assignee, problem, and connection, SHALL be validated against the actor's workspace.

#### Scenario: Cross-workspace link attempt
- **WHEN** a member submits a request that links their report to another workspace's problem
- **THEN** the system rejects the request and changes nothing

### Requirement: Scoped credentials
External calls SHALL use only the credentials of the workspace that owns the operation.

#### Scenario: Send through another workspace
- **WHEN** an operation in workspace A names a connection owned by workspace B
- **THEN** the operation fails before any external call
