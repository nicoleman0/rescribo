# slack-capture Specification

## Purpose

Turns one selected Slack message into a report through the "Submit customer feedback" message shortcut.

## Requirements

### Requirement: Verified shortcut requests
The system SHALL verify the raw-body signature and timestamp of every Slack request before trusting or storing any of its content.

#### Scenario: Bad signature
- **WHEN** a shortcut request has an invalid signature or a stale timestamp
- **THEN** it is rejected and nothing from it is stored

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

### Requirement: Fast acknowledgement
The shortcut handler SHALL acknowledge within Slack's three-second deadline and open the modal with the trigger. It MUST NOT run matching, fetch history, or call GitHub in that path.

#### Scenario: Shortcut opened
- **WHEN** a linked member runs the shortcut on a message in an approved channel
- **THEN** the modal opens with a preview of the selected message

### Requirement: Source channel eligibility
Capture SHALL be accepted only from approved, currently eligible channels. The initial modal MAY use a short-lived cached validation; submission MUST fail closed unless revalidation has succeeded. Text from rejected sources MUST NOT be retained.

#### Scenario: Channel archived during capture
- **WHEN** the channel becomes ineligible while the modal is open
- **THEN** submission is refused and the message text is discarded

### Requirement: Server-side capture context
The system SHALL store capture context server-side for 15 minutes and put only its opaque ID in modal metadata. Modal metadata MUST NOT select a workspace or source message.

#### Scenario: Expired context
- **WHEN** a member submits a modal more than 15 minutes after opening it
- **THEN** the system asks them to run the shortcut again

### Requirement: Editable report fields
The modal SHALL offer an editable title and optional customer organisation/contact reference, affected version, and context. The message snapshot SHALL stay separate from the edited report text.

#### Scenario: Title edited
- **WHEN** a member changes the title before submitting
- **THEN** the report stores the new title and the original snapshot unchanged

### Requirement: Committed submission
A successful modal submission SHALL mean the report and its activity entry are committed. A database failure MUST return a visible error, not a success acknowledgement.

#### Scenario: Database unavailable
- **WHEN** the commit fails on submission
- **THEN** the modal shows an error and Slack does not report success

### Requirement: Snapshot content limits
The snapshot SHALL contain only the selected message's text and source identifiers, labelled "Captured on [date]". The system MUST NOT fetch attachments, linked pages, or the rest of the thread. A reply's preview SHALL say the parent is not included.

#### Scenario: Thread reply captured
- **WHEN** a member captures a reply in a thread
- **THEN** the report contains only that reply and the preview notes the missing parent

### Requirement: Asynchronous permalink
The system SHALL resolve the message permalink after the report is committed. Permalink failure SHALL leave the report intact with a retryable link error.

#### Scenario: Permalink lookup fails
- **WHEN** the permalink request fails
- **THEN** the report exists and shows a retry action for the link

### Requirement: Idempotent capture
Reports SHALL be unique per workspace, Slack team, channel, and message timestamp. Capturing an already captured message SHALL return the existing report without changing it or resetting follow-up. Different messages in one thread remain separate reports.

#### Scenario: Same message submitted twice
- **WHEN** a member submits a message that already has a report
- **THEN** the existing report link is returned and no second report is created
