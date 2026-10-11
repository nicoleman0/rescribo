# Spec Delta

## ADDED Requirements

### Requirement: Problem left without reports
A problem whose last linked report is moved or ungrouped SHALL keep its state, owner, fix details, and activity history. The system MUST NOT change its state or delete it. A member decides what happens to it.

#### Scenario: Only report ungrouped
- **WHEN** a member ungroups the only report of an `open` problem
- **THEN** the problem stays `open` with zero linked reports, and its activity still shows the report was linked and ungrouped

#### Scenario: Only report moved
- **WHEN** a member moves the only report of an `in_progress` problem to another problem
- **THEN** the first problem stays `in_progress` with zero linked reports
