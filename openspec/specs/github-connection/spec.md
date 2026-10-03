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
