# reports Specification

## Purpose

Records each customer experience as a report and lets members triage it in the inbox.

## Requirements

### Requirement: One report per customer experience
A report SHALL describe one customer experience. Message author, submitting member, assigned member, and affected customer SHALL be stored as separate fields. Similar names MUST NOT establish customer identity.

#### Scenario: Submitter differs from author
- **WHEN** a member captures a message written by a colleague
- **THEN** the report records the colleague as author and the member as submitter

### Requirement: Manual entry
Members SHALL be able to create a report in the web app. Manual and Slack capture SHALL use the same report workflow and rules.

#### Scenario: Manual report
- **WHEN** a member submits the manual capture form
- **THEN** a report with no source snapshot is created in state `new` with an activity entry

#### Scenario: Repeated manual submission
- **WHEN** the same manual submission is sent twice with the same submission key
- **THEN** only one report is created

### Requirement: Triage states
A report SHALL be `new`, `linked`, or `dismissed`. Linking sets `linked`; unlinking returns to `new`; only a `new` report can be dismissed; restoring returns a dismissed report to `new`. Dismissed reports SHALL NOT generate follow-ups.

#### Scenario: Dismiss a linked report
- **WHEN** a member dismisses a report in state `linked`
- **THEN** the transition is rejected

### Requirement: Inbox search and filters
The inbox SHALL paginate reports, search title, description, and customer reference, and filter by triage state, assignee, and source.

#### Scenario: Filter by assignee
- **WHEN** a member filters the inbox by an assignee
- **THEN** only that member's assigned reports in the current workspace are listed

### Requirement: Assignment and editing
Any active member SHALL be able to edit report fields and assign or unassign a report to an active member of the same workspace.

#### Scenario: Reassignment with an unsent follow-up
- **WHEN** a report with an unsent follow-up is reassigned
- **THEN** unsent deliveries are cancelled, pending follow-ups move to the new assignee, and a new preview needs approval

### Requirement: Conflicting edits
Reports, problems, and follow-ups SHALL carry a row version. A write based on an old version MUST return a conflict with the current data instead of overwriting.

#### Scenario: Two members edit at once
- **WHEN** a member saves a report another member changed since it was loaded
- **THEN** the save returns a conflict with the current report

### Requirement: Activity history
Each business change SHALL record actor, action, record, and time. Activity metadata SHALL contain field names and state or ID changes, not customer content.

#### Scenario: Report edited
- **WHEN** a member edits a report's title
- **THEN** activity records that the title changed, without the old or new text

### Requirement: Owner report deletion
An owner SHALL be able to permanently delete a report after typing `DELETE`. Deletion removes the report, its snapshot, follow-ups, pending notifications, and activity, then records a content-free deletion entry. Upstream Slack messages and GitHub issues are not deleted.

#### Scenario: Report deleted
- **WHEN** an owner confirms deletion of a report
- **THEN** the report and its content are gone and activity shows only that a report was deleted
