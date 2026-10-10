# Spec Delta

## ADDED Requirements

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
