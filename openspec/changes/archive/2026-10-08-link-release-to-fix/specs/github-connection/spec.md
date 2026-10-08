# Spec Delta

## MODIFIED Requirements

### Requirement: Minimal permissions
The GitHub App SHALL request Issues read/write, Metadata read, and Contents read only. It MUST NOT request Contents write, Pull requests, or Administration permissions. Each installation token SHALL carry only the permissions its operation needs: Contents read only for release reads. An installation that has not granted Contents read SHALL stay usable for issues.

#### Scenario: Permission review
- **WHEN** an owner inspects the app's requested permissions during installation
- **THEN** only Issues, Metadata, and Contents read are listed

#### Scenario: Issue token
- **WHEN** the system creates an installation token to read or write an issue
- **THEN** the token does not carry Contents permission

#### Scenario: Installation without Contents read
- **WHEN** an installation grants Issues write and Metadata read but not Contents read
- **THEN** setup and health checks pass and only release reads are refused
