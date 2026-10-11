# Spec Delta

## ADDED Requirements

### Requirement: Mark problems with no reports
The problems list and the problem detail header SHALL show a "No reports" status in the warning tone on an `open` or `in_progress` problem that has no linked reports. A problem with a linked report, and a `fix_available` or `not_planned` problem, MUST NOT show it. The problem picker MUST keep a problem with no reports selectable.

#### Scenario: Empty problem in the list
- **WHEN** a member ungroups the only report of an open problem and opens the problems list
- **THEN** that row shows "No reports" beside its Open status

#### Scenario: Empty problem detail
- **WHEN** a member opens an in-progress problem with no linked reports
- **THEN** the header shows "No reports" beside its In progress status, and the linked reports section says no reports are linked and that the problem and its history are kept

#### Scenario: Report linked again
- **WHEN** a member links a report to a problem that shows "No reports"
- **THEN** the problem no longer shows "No reports" in the list or on its detail page

#### Scenario: Settled problem
- **WHEN** a `not_planned` or `fix_available` problem has no linked reports
- **THEN** it does not show "No reports"

#### Scenario: Pick an empty problem
- **WHEN** a member links a report and the picker lists a problem with no reports
- **THEN** the member can choose that problem
