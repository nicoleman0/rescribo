# accounts Specification

## Purpose

Invite-only owner and member accounts for a product workspace, with browser sessions that end when access is revoked.

## Requirements

### Requirement: First owner bootstrap
The system SHALL create the first owner only through an interactive operator command. It MUST NOT ship default credentials or offer public signup.

#### Scenario: Fresh installation
- **WHEN** an operator runs the bootstrap command on an empty installation
- **THEN** one workspace and its owner exist, and no other account can sign in

### Requirement: One-use invitations
An owner SHALL create invitations that are stored as hashed tokens, expire after 48 hours, and can be redeemed once. The owner shares the link; the system sends no email.

#### Scenario: Invitation accepted
- **WHEN** an invitee opens a valid link and sets a password that passes Django validation
- **THEN** the invitee becomes an active member and the invitation can no longer be used

#### Scenario: Expired or reused invitation
- **WHEN** an invitee opens an expired or already used link
- **THEN** the system shows that the invitation is no longer valid and creates no account

### Requirement: Roles and the last owner
Each membership SHALL have the role owner or member. The system MUST keep at least one active owner per workspace.

#### Scenario: Last owner demotion
- **WHEN** the only active owner tries to demote or remove themselves
- **THEN** the system rejects the change

### Requirement: Sign-in and sessions
The system SHALL use secure HttpOnly session cookies and require a CSRF token on every browser write, including login. Login and token redemption MUST be rate-limited.

#### Scenario: Repeated failed logins
- **WHEN** a client exceeds the login attempt limit
- **THEN** further attempts are rejected until the limit window passes

### Requirement: Access revocation
Logout, password change, and revocation of a user's last active membership SHALL invalidate that user's sessions. Membership SHALL be rechecked on every workspace request.

#### Scenario: Member removed
- **WHEN** an owner revokes a member's only membership
- **THEN** the member's next request is rejected and their sessions no longer authenticate

### Requirement: Password recovery without email
An owner SHALL be able to issue a one-use reset link for a member. An operator command SHALL issue a reset for an owner. No email provider is required.

#### Scenario: Member reset
- **WHEN** a member redeems an unexpired owner-issued reset link with a valid password
- **THEN** the password changes, the link is spent, and existing sessions are invalidated

### Requirement: Password reset requires a different password
Redeeming a reset link SHALL refuse the password the account already has and ask for a different one. This applies to owner-issued and operator-issued links. A refused password MUST NOT spend the link, change the password, or invalidate sessions. Submissions to a reset link MUST count against that account's login attempt limit.

#### Scenario: Member submits the current password
- **WHEN** a member redeems an unexpired owner-issued reset link with the account's current password
- **THEN** the system refuses and asks for a different password, the link can still be used, and existing sessions stay valid

#### Scenario: Owner submits the current password
- **WHEN** an owner redeems an unexpired operator-issued reset link with the account's current password
- **THEN** the system refuses and the link can still be used

#### Scenario: Different password after a refusal
- **WHEN** a person whose current password was refused submits a different valid password on the same link
- **THEN** the password changes, the link is spent, and existing sessions are invalidated

#### Scenario: Repeated submissions
- **WHEN** submissions to a reset link exceed the account's login attempt limit
- **THEN** further submissions to the link and logins for that account are rejected until the limit window passes

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
