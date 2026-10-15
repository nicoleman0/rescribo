## MODIFIED Requirements

### Requirement: Access revocation
Logout, password change, and revocation of a user's last active membership SHALL invalidate that user's sessions. Membership SHALL be rechecked on every workspace request. Revoking a membership SHALL also remove its Slack identity in the same transaction. Restoring a membership MUST NOT restore its Slack identity.

#### Scenario: Member removed
- **WHEN** an owner revokes a member's only membership
- **THEN** the member's next request is rejected, their sessions no longer authenticate, and their Slack identity is removed

#### Scenario: Revoked membership restored
- **WHEN** a revoked membership is restored
- **THEN** the member has no Slack identity until they link again
