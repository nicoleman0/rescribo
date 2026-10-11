# Spec Delta

## ADDED Requirements

### Requirement: Form errors for fields not shown
When a validation reply names a field that the form does not show, the form's error summary SHALL show that field's name and its message. An error shown under its field MUST NOT be repeated in the summary. An error that belongs to no field SHALL show in the summary without a field name. The summary MUST NOT show a bare reason code, and MUST NOT show the reply's own message twice.

#### Scenario: Field the form does not show
- **WHEN** an owner submits the Slack connect form and the reply rejects `repository` with "This field may not be blank."
- **THEN** the card's error reads "Repository: This field may not be blank." below the reply's message

#### Scenario: Field the form shows
- **WHEN** an owner submits the GitHub connect form and the reply rejects `repository`
- **THEN** the message shows under the repository field and the card's error does not repeat it

#### Scenario: Error that belongs to no field
- **WHEN** a reply carries a validation message that belongs to no field
- **THEN** the form's error shows that message with no field name

#### Scenario: Reply that already explains the field
- **WHEN** a reply's field error only repeats the reply's reason code or its message
- **THEN** the form's error shows the reply's message once and no extra line
