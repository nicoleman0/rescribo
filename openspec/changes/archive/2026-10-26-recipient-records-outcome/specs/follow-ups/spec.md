## MODIFIED Requirements

### Requirement: Who records outcomes
In Slack, only the intended linked member SHALL record outcomes, with membership rechecked on every action. In the web app, the assigned member, submitting member, the follow-up's current recipient, or an owner SHALL record outcomes. The system records who and when; owners may correct an outcome with a reason.

#### Scenario: Another member clicks the Slack action
- **WHEN** a Slack user other than the intended member presses "Customer contacted"
- **THEN** the action is refused and nothing changes

#### Scenario: Reassigned recipient records in the web app
- **WHEN** an owner changes the recipient to a member who is not an owner, the assignee, or the submitter, and that member records an outcome in the web app
- **THEN** the outcome is recorded with that member as who recorded it

#### Scenario: Former recipient records in the web app
- **WHEN** the recipient is changed away from a member who is not an owner, the assignee, or the submitter, and that member then records an outcome in the web app
- **THEN** the outcome endpoint refuses it as a conflict and nothing changes

#### Scenario: Member of another workspace
- **WHEN** a member of another workspace records an outcome on the follow-up
- **THEN** the follow-up is not found and nothing changes

### Requirement: Contact form follows recording permission
The follow-up detail SHALL say whether the viewing member may record a customer contact outcome in the web app, using the same rule the outcome endpoint enforces. When the viewer may not record and an outcome can still be recorded, the web app SHALL hide the record form and show "Only an owner, the report's assignee or submitter, or the follow-up's recipient can record customer contact." in its place. The outcome endpoint MUST still refuse a member who may not record.

#### Scenario: Owner reads a follow-up
- **WHEN** an owner who is neither the assignee nor the submitter reads a follow-up
- **THEN** the detail says the owner may record an outcome

#### Scenario: Assignee reads a follow-up
- **WHEN** a member who is the report's assignee, and not an owner, reads its follow-up
- **THEN** the detail says the member may record an outcome

#### Scenario: Submitter reads a follow-up
- **WHEN** a member who submitted the report, and is not an owner, reads its follow-up
- **THEN** the detail says the member may record an outcome

#### Scenario: Recipient reads a follow-up
- **WHEN** a member who is the follow-up's recipient, and not an owner, the assignee, or the submitter, reads the follow-up
- **THEN** the detail says the member may record an outcome

#### Scenario: Former recipient reads a follow-up
- **WHEN** the recipient is changed away from a member who is not an owner, the assignee, or the submitter, and that member reads the follow-up
- **THEN** the detail says the member may not record an outcome

#### Scenario: Other member reads a follow-up
- **WHEN** a member who is not an owner, the assignee, the submitter, or the recipient reads a follow-up
- **THEN** the detail says the member may not record an outcome

#### Scenario: Other member opens a pending follow-up
- **WHEN** a member who may not record opens a follow-up whose outcome is `pending` or `contacted`
- **THEN** the Customer contact section shows the current outcome and the line naming who can record contact, and no record form

#### Scenario: Other member opens a completed follow-up
- **WHEN** a member who may not record opens a follow-up whose outcome is already final
- **THEN** the Customer contact section shows the current outcome and no form or line

#### Scenario: Stale page submits
- **WHEN** a member loses the right to record while their page still shows the form, and they submit an outcome
- **THEN** the outcome endpoint refuses it as a conflict, nothing changes, and the page replaces the form with the line naming who can record contact
