# Spec Delta

## ADDED Requirements

### Requirement: Change a problem's state from problem detail
A workspace member SHALL be able to start work on an `open` problem, move an `in_progress` problem back to `open`, mark an `open` or `in_progress` problem not planned with a reason, and reopen a `not_planned` problem, from problem detail. The system SHALL record the member and the new state in the problem's activity. A change MUST be refused when the state does not allow it or the member's copy is out of date. A problem in another workspace MUST be not found.

#### Scenario: Start work
- **WHEN** a member starts work on an `open` problem
- **THEN** the problem is `in_progress` and its activity records that member changed the status

#### Scenario: Mark not planned with a reason
- **WHEN** a member marks an `in_progress` problem not planned with a reason
- **THEN** the problem is `not_planned` and keeps that reason

#### Scenario: Reopen
- **WHEN** a member reopens a `not_planned` problem
- **THEN** the problem is `open` and no longer has a decline reason

#### Scenario: State does not allow the change
- **WHEN** a member marks a `fix_available` problem not planned
- **THEN** the request is refused with the current problem and nothing changes

#### Scenario: Stale copy keeps the reason
- **WHEN** a member marks a problem not planned using an out-of-date version
- **THEN** the request is refused with the current problem, the state is unchanged, and the reason the member typed stays in the form

#### Scenario: Another workspace's problem
- **WHEN** a member of workspace A changes the state of a problem in workspace B
- **THEN** the response is not found and the problem is unchanged

### Requirement: Show why a problem is not planned
Problem detail SHALL show the reason a `not_planned` problem was declined.

#### Scenario: Declined problem opened
- **WHEN** a member opens a `not_planned` problem
- **THEN** the page shows the reason given when it was declined

### Requirement: Offer to decline a problem without reports
Problem detail SHALL offer to mark an `open` or `in_progress` problem not planned when no reports are linked to it. The member MUST still give a reason. The offer MUST NOT appear on a problem with linked reports or on a `fix_available` or `not_planned` problem.

#### Scenario: Open problem with no reports
- **WHEN** a member opens an `open` problem with zero linked reports
- **THEN** the linked reports section offers to mark it not planned

#### Scenario: Problem with reports
- **WHEN** a member opens an `open` problem with linked reports
- **THEN** no such offer is shown

#### Scenario: Fixed problem with no reports
- **WHEN** a member opens a `fix_available` problem with zero linked reports
- **THEN** no such offer is shown
