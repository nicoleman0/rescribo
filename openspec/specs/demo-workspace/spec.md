# demo-workspace Specification

## Purpose
Lets anyone review the product end to end with fictitious data and no access to real Slack or GitHub accounts.

## Requirements

### Requirement: Seeded demo data
An operator command SHALL create a separate demo workspace with fictitious companies, reports, problems, linked issues, follow-ups, mistakes, and failure states. It MUST NOT include real customer data.

#### Scenario: Seed run
- **WHEN** an operator runs the demo seed command
- **THEN** a demo workspace exists with records in every main workflow state

### Requirement: Visible demo label
Every screen in the demo workspace SHALL show a demo label.

#### Scenario: Demo inbox
- **WHEN** a member opens the demo inbox
- **THEN** the page shows that it is a demo

### Requirement: No real integrations
In the demo workspace, integration setup and outbound Slack and GitHub calls SHALL be disabled by default. Demo mutations MUST NOT call a real provider.

#### Scenario: Send a follow-up in the demo
- **WHEN** a member approves a follow-up in the demo workspace
- **THEN** no Slack request is made and the result is simulated and labelled

### Requirement: Demo isolated from private workspaces
A public demonstration SHALL expose only the demo workspace. It MUST NOT expose a private test workspace or its credentials.

#### Scenario: Demo visitor
- **WHEN** a demo visitor signs in
- **THEN** they can reach only the demo workspace

### Requirement: Shared demo login
A public demonstration SHALL publish only a member-role login for the demo workspace and MUST NOT publish owner credentials. The demo workspace SHALL reset to its seeded state on a nightly schedule.

#### Scenario: Visitor tries an owner action
- **WHEN** a visitor signed in with the published demo login tries to invite someone, change members, issue a password reset, or delete the workspace
- **THEN** the request is refused and nothing changes

#### Scenario: Nightly reset
- **WHEN** visitors have edited demo reports and problems and the nightly reset runs
- **THEN** the demo workspace matches its seeded state and other workspaces are unchanged
