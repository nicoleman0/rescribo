# Spec Delta

## ADDED Requirements

### Requirement: Recipient change
An owner SHALL be able to change a follow-up's recipient to another active member of the workspace who has a Slack link. The change SHALL be allowed in every delivery and contact state. It SHALL cancel an unsent notification and record who made the change.

#### Scenario: Linked member chosen
- **WHEN** an owner changes the recipient to an active member with a Slack link
- **THEN** that member is the recipient, an unsent notification is cancelled, and the follow-up history shows the change

#### Scenario: Completed follow-up
- **WHEN** an owner changes the recipient of a follow-up whose customer outcome is already recorded
- **THEN** the change is accepted

#### Scenario: Member tries to change the recipient
- **WHEN** a member who is not an owner sends a recipient change
- **THEN** it is refused as forbidden and the follow-up is unchanged

### Requirement: Recipient change refusals name their cause
A refused recipient change SHALL leave the follow-up, its notification, and its history unchanged. Each cause SHALL have its own reason in the response, and the web app SHALL show a message that names the cause.

#### Scenario: New recipient has no Slack link
- **WHEN** an owner changes the recipient to an active member with no Slack link
- **THEN** the change is refused with reason `recipient_not_linked` and the owner is told the member has not linked a Slack account

#### Scenario: New recipient is already the recipient
- **WHEN** an owner sends a recipient change that names the current recipient
- **THEN** the change is refused with reason `no_changes`

#### Scenario: New recipient is not an active member
- **WHEN** an owner sends a recipient change that names a revoked member, an unknown member, or a member of another workspace
- **THEN** the change is refused with reason `invalid_reference` on the recipient field, with the same response in all three cases

### Requirement: Recipient picker shows eligibility
The recipient picker SHALL list every active member of the workspace. A member with no Slack link SHALL be shown as unavailable, with the reason in the option text, and SHALL NOT be selectable as a new recipient. The member directory SHALL say whether each member has a Slack link in that workspace.

#### Scenario: Member with no Slack link
- **WHEN** an owner opens the recipient picker and an active member has no Slack link
- **THEN** that member's option is disabled and reads "<name> (no Slack link)"

#### Scenario: Current recipient has no Slack link
- **WHEN** the follow-up's current recipient has no Slack link
- **THEN** the picker shows that member as the selected option, labelled "(no Slack link)"

#### Scenario: Directory entry
- **WHEN** a member reads the member directory
- **THEN** each active member's entry says whether that member has a Slack link
