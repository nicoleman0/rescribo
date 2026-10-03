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
