## MODIFIED Requirements

### Requirement: Linked active member
The Slack actor SHALL be linked to an active membership in the workspace that owns the Slack connection. Membership MUST be rechecked on submission. Until the actor is linked, the system MUST NOT reveal whether the message is already captured or show any report link or ID.

#### Scenario: Unlinked user
- **WHEN** an unlinked Slack user runs the shortcut
- **THEN** the modal explains how to link an account and no report is created

#### Scenario: Unlinked user on a captured message
- **WHEN** an unlinked Slack user runs the shortcut on a message that already has a report
- **THEN** they see the same linking modal as for an uncaptured message, with no report link

#### Scenario: User links on a captured message
- **WHEN** that user submits a valid linking code
- **THEN** the existing report link is returned and no second report is created
