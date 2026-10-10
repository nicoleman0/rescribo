# Spec Delta

## ADDED Requirements

### Requirement: Connection check result
When an owner checks the status of a Slack or GitHub connection in Settings, the card SHALL show the result of that check beside the check action: that the connection is working, and the time of the check to the second. The result MUST be announced to assistive technology without moving focus. A failed check MUST show its reason and time in the same place. The card MUST NOT show a passed result and a failed result together, and MUST NOT show a passed result for a connection that is not active.

#### Scenario: Check passes
- **WHEN** an owner chooses "Check GitHub status" on an active GitHub connection and the check passes
- **THEN** the place beside the button reads that the GitHub connection is working with the time of the check to the second, and a screen reader announces it

#### Scenario: Repeated check in the same minute
- **WHEN** an owner runs a second passing check less than a minute after the first
- **THEN** the result shows the time of the second check, which differs from the first

#### Scenario: Check fails
- **WHEN** an owner chooses "Check Slack status" and the check fails
- **THEN** the place beside the button shows the reason and the time, and no passed result is shown

#### Scenario: Check passes after a failure
- **WHEN** an owner runs a check that passes after one that failed
- **THEN** the passed result replaces the failure
