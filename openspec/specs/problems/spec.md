# problems Specification

## Purpose

Groups related reports into a problem and records when a fix is available to customers.

## Requirements

### Requirement: Grouping reports
Members SHALL be able to link a report to an existing problem, create a problem from a report, move a report between problems, and ungroup it. Provenance SHALL be kept in activity history.

#### Scenario: Ungroup a report
- **WHEN** a member ungroups a report from a problem
- **THEN** the report returns to `new`, its unsent operations are cancelled, and sent history remains

### Requirement: Problem lifecycle
A problem SHALL be `open`, `in_progress`, `fix_available`, or `not_planned`. Members may move between `open` and `in_progress`, decline from either to `not_planned` with a reason, and return `not_planned` to `open`.

#### Scenario: Decline without reason
- **WHEN** a member marks a problem not planned without a reason
- **THEN** the change is rejected

### Requirement: Human fix confirmation
Only a member SHALL move a problem to `fix_available`, from `open` or `in_progress`, by supplying a fix note and availability or version information, with an optional evidence URL. Each confirmation SHALL increment the resolution revision.

#### Scenario: Fix confirmed
- **WHEN** a member confirms a fix with a note and version
- **THEN** the problem is `fix_available`, its resolution revision increases, and follow-ups are created for active linked reports

### Requirement: Distinct resolution facts
GitHub issue closed, fix available, employee notified, customer contacted, and customer confirmed SHALL be stored and shown as separate facts. None SHALL be inferred from another.

#### Scenario: Issue closed
- **WHEN** the linked GitHub issue closes
- **THEN** the problem is flagged for review and stays in its current state

### Requirement: Late report on a fixed problem
A report linked to a `fix_available` problem SHALL get its own follow-up only after a member confirms the existing fix applies to it.

#### Scenario: Late report confirmed
- **WHEN** a member confirms the fix applies to a newly linked report
- **THEN** one follow-up is created for that report at the current resolution revision

### Requirement: Still affected
Recording that a customer is still affected SHALL flag the problem for review. It MUST NOT reopen the GitHub issue.

#### Scenario: Customer still affected
- **WHEN** a member records `still_affected` on a follow-up
- **THEN** the problem shows a review flag and GitHub is not called

### Requirement: Mark a flagged problem reviewed
A workspace member SHALL be able to clear a problem's review flag by marking it reviewed, in any problem state. The action MUST be refused when the problem is not flagged or the member's copy is out of date, and MUST leave the state, fix details, and resolution revision unchanged. The system SHALL record in the problem's activity which member marked it reviewed. A problem in another workspace MUST be not found.

#### Scenario: Fixed problem marked reviewed
- **WHEN** a member marks reviewed a `fix_available` problem that is flagged for review
- **THEN** the flag is cleared, the problem stays `fix_available`, and the activity records that member marked it reviewed

#### Scenario: Problem not flagged
- **WHEN** a member marks reviewed a problem that is not flagged for review
- **THEN** the request is refused with the current problem and nothing changes

#### Scenario: Stale copy
- **WHEN** a member marks reviewed a flagged problem using an out-of-date version
- **THEN** the request is refused with the current problem and the flag stays set

#### Scenario: Another workspace's problem
- **WHEN** a member of workspace A marks reviewed a flagged problem in workspace B
- **THEN** the response is not found and the flag stays set
