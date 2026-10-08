# Spec Delta

## ADDED Requirements

### Requirement: Labelled follow-up statuses
Wherever a follow-up shows its employee delivery and customer outcome together, each status SHALL carry a visible label naming which one it is: "Delivery" or "Outcome". A follow-up without a prepared message MUST show its delivery as "Not prepared".

#### Scenario: Follow-up row
- **WHEN** a member views a follow-up whose message was sent and whose customer is not yet contacted
- **THEN** its row reads "Delivery" with a "Sent" badge and "Outcome" with a "Pending" badge

#### Scenario: Message not prepared
- **WHEN** a member views a follow-up that has no prepared message
- **THEN** its row and its detail show "Delivery" with a neutral "Not prepared" badge

### Requirement: Integration status cards
Settings SHALL show Slack and GitHub each as a separate card with a status badge, the connected identity, and the counts of queued, running, failed, and uncertain jobs as labelled numbers. The GitHub card MUST also show the repository. A provider with no connection MUST read "Not connected".

#### Scenario: Connected GitHub
- **WHEN** a member opens settings for a workspace with an active GitHub connection
- **THEN** the GitHub card shows a success "Connected" badge, the repository, and each job count with its label

#### Scenario: Connection needs attention
- **WHEN** a connection is in the error state
- **THEN** its card shows a danger "Needs attention" badge and the error detail

#### Scenario: No connection
- **WHEN** a workspace has never connected Slack
- **THEN** the Slack card shows a neutral "Not connected" badge
