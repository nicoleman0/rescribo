# Spec Delta

## ADDED Requirements

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
