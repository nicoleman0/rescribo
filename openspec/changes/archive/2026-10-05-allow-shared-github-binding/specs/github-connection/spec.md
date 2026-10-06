# Spec Delta

## ADDED Requirements

### Requirement: Shared installation binding
The system SHALL let several product workspaces bind the same GitHub installation and repository when each owner passes verified installation binding. Each workspace SHALL keep its own linked issues, issue state, and connection state. A workspace MUST NOT see another workspace's records or learn that the binding is shared.

#### Scenario: Second workspace binds the same repository
- **WHEN** an owner of a second workspace binds an installation and repository already bound by another workspace
- **THEN** the binding succeeds and settings show only that workspace's connection

#### Scenario: Issue event for a shared repository
- **WHEN** a verified issue event arrives for a repository bound by two workspaces
- **THEN** each workspace updates only the issue it linked, and a workspace that did not link the issue records nothing

#### Scenario: Installation deleted while shared
- **WHEN** a verified installation deletion event arrives for an installation bound by two workspaces
- **THEN** both connections show access lost and both workspaces' linked issues show access lost

#### Scenario: One workspace disconnects
- **WHEN** an owner disconnects GitHub in one of two workspaces that share a binding
- **THEN** the other workspace's connection stays active and its linked issues keep syncing
