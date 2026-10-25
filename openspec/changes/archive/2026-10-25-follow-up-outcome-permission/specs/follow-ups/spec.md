# Spec Delta

## ADDED Requirements

### Requirement: Contact form follows recording permission
The follow-up detail SHALL say whether the viewing member may record a customer contact outcome in the web app, using the same rule the outcome endpoint enforces. When the viewer may not record and an outcome can still be recorded, the web app SHALL hide the record form and show "Only an owner, the report's assignee, or its submitter can record customer contact." in its place. The outcome endpoint MUST still refuse a member who may not record.

#### Scenario: Owner reads a follow-up
- **WHEN** an owner who is neither the assignee nor the submitter reads a follow-up
- **THEN** the detail says the owner may record an outcome

#### Scenario: Assignee reads a follow-up
- **WHEN** a member who is the report's assignee, and not an owner, reads its follow-up
- **THEN** the detail says the member may record an outcome

#### Scenario: Submitter reads a follow-up
- **WHEN** a member who submitted the report, and is not an owner, reads its follow-up
- **THEN** the detail says the member may record an outcome

#### Scenario: Other member reads a follow-up
- **WHEN** a member who is not an owner, the assignee, or the submitter reads a follow-up
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
