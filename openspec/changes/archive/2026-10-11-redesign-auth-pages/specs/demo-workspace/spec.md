# Spec Delta

## ADDED Requirements

### Requirement: Public demo offer
A signed-out client SHALL be able to read whether the instance offers a demo. The instance offers a demo only when an operator has configured the published visitor password and the demo workspace exists. When a demo is offered, the reply SHALL carry the visitor email and the configured password. Otherwise the reply MUST carry no credentials. The reply MUST NOT carry owner credentials or any detail of another workspace.

#### Scenario: Demo offered
- **WHEN** the visitor password is configured, the demo workspace is seeded, and a signed-out client reads the demo offer
- **THEN** the reply carries the visitor email and the configured password, and that login signs in

#### Scenario: Password not configured
- **WHEN** the demo workspace is seeded with a generated password and no visitor password is configured
- **THEN** the reply says no demo is offered and carries no credentials

#### Scenario: Demo not seeded
- **WHEN** the visitor password is configured and no demo workspace exists
- **THEN** the reply says no demo is offered and carries no credentials

#### Scenario: Owner login stays private
- **WHEN** a demo is offered and a signed-out client reads the demo offer
- **THEN** the reply names only the visitor account
