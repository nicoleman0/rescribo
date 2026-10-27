## ADDED Requirements

### Requirement: Running version in the user menu
The user menu SHALL show the version of Rescribo the server runs, as "Rescribo" followed by the version, below the member's email. The version SHALL be the release version the server was built from. Only a signed-in member SHALL be able to read it. While the version loads, or when it cannot load, the menu MUST show no version line and keep every other item working.

#### Scenario: Open the menu
- **WHEN** a member opens the user menu on a server built from release 0.1.0
- **THEN** the menu shows "Rescribo 0.1.0" below their email

#### Scenario: Signed out
- **WHEN** a request without a session asks the API for the running version
- **THEN** the API refuses it as unauthenticated and returns no version

#### Scenario: Version unavailable
- **WHEN** a member opens the user menu and the version request fails
- **THEN** the menu shows their name, email, theme choice, and Sign out, and no version line
