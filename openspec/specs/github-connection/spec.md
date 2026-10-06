# github-connection Specification

## Purpose

Connects one GitHub repository to a product workspace through a GitHub App installation with the least access needed for issues.

## Requirements

### Requirement: Minimal permissions
The GitHub App SHALL request Issues read/write and Metadata read only. It MUST NOT request Contents, Pull requests, or Administration permissions.

#### Scenario: Permission review
- **WHEN** an owner inspects the app's requested permissions during installation
- **THEN** only Issues and Metadata are listed

### Requirement: Verified installation binding
Installation SHALL be bound to a single-use state and the product workspace. Before binding, the system SHALL verify through GitHub user authorisation that the connecting user can access the installation. An `installation_id` from a callback alone MUST NOT be trusted.

#### Scenario: Forged installation ID
- **WHEN** a callback names an installation the connecting user cannot access
- **THEN** the binding is rejected

### Requirement: Short-lived repository tokens
The system SHALL discard user credentials after verification and use short-lived installation tokens restricted to the selected repository for all later requests.

#### Scenario: Ongoing request
- **WHEN** the system reads an issue
- **THEN** it uses an installation token scoped to the selected repository

### Requirement: One selected repository with consent
Each workspace SHALL select one repository. Settings SHALL show the repository and its visibility, and the owner SHALL explicitly permit members to see issue metadata and create issues through the app.

#### Scenario: Private repository selected
- **WHEN** an owner selects a private repository
- **THEN** settings show it as private and ask for the member-access permission before enabling issue actions

### Requirement: Access loss
Repository removal and installation deletion SHALL be treated as the same access-lost signal. Suspension SHALL pause issue operations. An inaccessible issue MUST be shown as unknown, not closed.

#### Scenario: Installation deleted
- **WHEN** a verified installation deletion event arrives
- **THEN** linked issues show access lost and no issue write is attempted

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
