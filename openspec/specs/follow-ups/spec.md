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
