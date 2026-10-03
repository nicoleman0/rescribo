# engineering-issues Specification

## Purpose

Links each problem to one GitHub issue, creates issues on explicit request, and keeps issue state current.

## Requirements

### Requirement: One issue per problem
A problem SHALL have at most one active GitHub issue link, and an issue SHALL map to at most one problem in a workspace. Relinking SHALL record history and invalidate pending approvals based on the old issue.

#### Scenario: Relink
- **WHEN** a member replaces a problem's linked issue
- **THEN** the old link is kept in history and unsent approvals tied to it are invalidated

### Requirement: Link an existing issue
The system SHALL accept an issue URL or number, verify it belongs to the selected repository, fetch it, and reject pull requests.

#### Scenario: Pull request URL
- **WHEN** a member links a URL that resolves to a pull request
- **THEN** the link is rejected

### Requirement: Create with preview
Issue creation SHALL show an editable title, body, and destination before publishing. The default body contains the problem summary and a product link, without customer identities or raw Slack text. Publishing MUST happen only on an explicit member action.

#### Scenario: Preview not published
- **WHEN** a member opens the create preview and leaves
- **THEN** no GitHub issue exists

### Requirement: Recoverable issue creation
The approved issue body SHALL include an opaque operation marker. Before retrying an uncertain create, the system SHALL search the repository for that marker. With no conclusive result, it SHALL require manual reconciliation.

#### Scenario: Timeout after create
- **WHEN** the create request times out and a later search finds the marker
- **THEN** the found issue is linked and no second issue is created

### Requirement: Verified webhooks
The system SHALL verify GitHub webhook signatures, persist the accepted delivery by delivery ID before responding, and process it asynchronously. Duplicate deliveries MUST NOT repeat transitions.

#### Scenario: Duplicate delivery
- **WHEN** GitHub redelivers a delivery ID already accepted
- **THEN** the response succeeds and no second transition occurs

### Requirement: Current state wins
Processing an issue change SHALL fetch the current issue, serialise per issue, and keep provider update times. An older event MUST NOT overwrite newer state.

#### Scenario: Close and reopen arrive reversed
- **WHEN** a reopen event is processed before the earlier close event
- **THEN** the stored state is open

### Requirement: Reconciliation
The system SHALL reconcile active linked issues every 15 minutes and offer a Refresh status action. It SHALL show the last successful sync and stale or access-lost status.

#### Scenario: Missed webhook
- **WHEN** an issue closed while webhooks were not delivered
- **THEN** the next reconciliation or refresh records it as closed

### Requirement: Closure prompts review
A verified close SHALL flag the problem with "Review engineering update" and keep `state_reason`. A close as not planned MUST NOT be treated as a fix.

#### Scenario: Closed as not planned
- **WHEN** the issue closes with reason not planned
- **THEN** the problem is flagged for review and no fix follow-up is created

### Requirement: Reopen invalidates unsent work
Reopening a linked issue SHALL return a `fix_available` problem to `in_progress` with a review flag and invalidate unsent fix notifications. Sent notifications and recorded outcomes SHALL remain, and a later confirmation creates a new revision.

#### Scenario: Reopened after fix
- **WHEN** the linked issue reopens after a fix was confirmed
- **THEN** the problem is `in_progress`, unsent approvals are invalidated, and sent history is unchanged
