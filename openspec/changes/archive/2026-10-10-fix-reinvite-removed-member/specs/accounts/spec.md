# Spec Delta

## ADDED Requirements

### Requirement: Invitation acceptance by an existing account
When the invited email already has an account, the system SHALL accept the invitation only from a request that proves control of that account: a session signed in as it, or its current password sent with the invitation. Acceptance SHALL NOT change the account's name or password. A wrong password MUST NOT spend the invitation or start a session. Password attempts on an invitation MUST count against that account's login attempt limit.

#### Scenario: Removed member is invited again
- **WHEN** a person whose only membership was revoked opens a new invitation for the same email and enters the account's current password
- **THEN** they are an active member with the invitation's role, they are signed in, and the invitation can no longer be used

#### Scenario: Wrong password
- **WHEN** an invitee enters a wrong password for the existing account
- **THEN** the system refuses, starts no session, and the invitation can still be used

#### Scenario: Signed in as the invited account
- **WHEN** a person signed in as the invited account accepts the invitation
- **THEN** they become an active member without entering a password

#### Scenario: Signed in as a different account
- **WHEN** a person signed in as another account submits the invitation, with or without the invited account's password
- **THEN** the system refuses and the invitation can still be used

#### Scenario: Account active in another workspace
- **WHEN** the invited account is an active member of another workspace and its current password is sent with the invitation
- **THEN** the account is signed in as an active member of both workspaces

#### Scenario: Deactivated account
- **WHEN** the invited account is deactivated and its correct password is sent with the invitation
- **THEN** the system refuses as it does for a wrong password

#### Scenario: Submitted name is ignored
- **WHEN** an existing account accepts an invitation and the request carries a full name
- **THEN** the account keeps its name and its password

#### Scenario: Repeated wrong passwords
- **WHEN** wrong passwords sent with an invitation exceed the invited account's login attempt limit
- **THEN** further password attempts on the invitation and logins for that account are rejected until the limit window passes
