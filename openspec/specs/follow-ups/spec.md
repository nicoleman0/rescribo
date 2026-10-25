# follow-ups Specification

## Purpose

Tells the employee who submitted a report that a fix is available, and records whether the customer was contacted and confirmed.

## Requirements

### Requirement: One follow-up per report and revision
Fix confirmation SHALL create one follow-up per active linked report for that resolution revision. A report, problem, and revision combination MUST be unique.

#### Scenario: Two linked reports
- **WHEN** a fix is confirmed for a problem with two active linked reports
- **THEN** two follow-ups exist for that revision

### Requirement: Deterministic draft
The draft message SHALL come from a deterministic template using only the report and the human-approved resolution. It identifies the report, fix note, and source link, and MUST NOT include other customers' reports, internal issue content, or invented dates, versions, causes, or promises.

#### Scenario: Draft content
- **WHEN** a follow-up draft is generated
- **THEN** it contains the report reference, approved fix note, and source link only

### Requirement: Exact-message approval
A member SHALL review and may edit the exact message and destination before sending. Approval SHALL be tied to the draft version and resolution revision; editing or reopening invalidates an unsent approval.

#### Scenario: Edit after approval
- **WHEN** a member edits an approved but unsent message
- **THEN** the approval is cleared and must be given again

### Requirement: Employee delivery
The default destination SHALL be the submitting employee's bot DM. Manual reports use the assigned member. Delivery SHALL be `draft`, `queued`, `sent`, `failed`, `uncertain`, or `cancelled`, and the system SHALL store the returned Slack conversation and message IDs.

#### Scenario: Sent
- **WHEN** Slack accepts the DM
- **THEN** delivery is `sent` with its Slack IDs and customer contact stays `pending`

### Requirement: No guessed recipients
If no verified Slack recipient exists, the system SHALL offer copy-to-clipboard and manual recording. It MUST NOT guess a Slack identity. If the recipient has left, an owner reassigns the report before sending.

#### Scenario: Recipient not linked to Slack
- **WHEN** the recipient has no verified Slack identity
- **THEN** the follow-up offers copy and manual recording and no Slack call is made

### Requirement: Uncertain sends
A send without a conclusive response SHALL be `uncertain`. The system MUST NOT resend it automatically. A member checks the target and message, and a confirmed resend warns about duplication and records the decision.

#### Scenario: Worker crash during send
- **WHEN** a worker stops after calling Slack but before recording the result
- **THEN** the delivery is `uncertain` and waits for a member decision

### Requirement: Customer contact outcomes
Customer contact SHALL be `pending`, `contacted`, `confirmed`, `still_affected`, or `no_response`, independent of delivery. `no_response` requires a dated note and does not count as resolved. A DM MUST NOT count as proof of contact.

#### Scenario: Failed delivery
- **WHEN** delivery fails
- **THEN** customer contact remains unchanged

### Requirement: Who records outcomes
In Slack, only the intended linked member SHALL record outcomes, with membership rechecked on every action. In the web app, the assigned member, submitting member, or an owner SHALL record outcomes. The system records who and when; owners may correct an outcome with a reason.

#### Scenario: Another member clicks the Slack action
- **WHEN** a Slack user other than the intended member presses "Customer contacted"
- **THEN** the action is refused and nothing changes

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

### Requirement: Contact without a message
A member SHALL be able to record a customer contact outcome on a follow-up that has no message draft. The follow-up detail MUST show the customer contact section for every delivery state, including when no message was prepared. Recording an outcome MUST NOT create, send, or cancel a message.

#### Scenario: Contact recorded before any message
- **WHEN** a member records "Customer contacted" on a follow-up with no prepared message
- **THEN** customer contact is `contacted`, delivery still shows "Not prepared", and the follow-up is listed under awaiting confirmation

#### Scenario: Completed without a message
- **WHEN** a member records `confirmed` on a contacted follow-up with no prepared message
- **THEN** the follow-up is listed under completed and no message exists

#### Scenario: Unsent draft is kept
- **WHEN** a member records an outcome on a follow-up whose message is still a draft
- **THEN** the draft is unchanged and can still be edited and sent

#### Scenario: Message prepared after contact
- **WHEN** a member opens a follow-up whose outcome is recorded and whose message was never prepared
- **THEN** the message section says customer contact is already recorded and still offers to prepare a message

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
