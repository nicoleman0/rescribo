# Spec Delta

## ADDED Requirements

### Requirement: Settings sections
Settings SHALL be split into sections, each at its own URL: Appearance at `/settings/appearance`, Members at `/settings/members`, Connections at `/settings/connections`, Slack account at `/settings/slack-account`, and Workspace at `/settings/workspace`. Settings MUST show one section at a time. `/settings` MUST redirect to Appearance. Opening a section URL directly MUST show that section.

#### Scenario: Settings opens on Appearance
- **WHEN** a member opens `/settings`
- **THEN** the address becomes `/settings/appearance` and the theme choice is shown

#### Scenario: A link opens one section
- **WHEN** an owner opens `/settings/connections`
- **THEN** the Slack and GitHub cards are shown, and the theme choice, members list, and workspace deletion are not

#### Scenario: Demo alert sits with the connections
- **WHEN** a visitor opens the demo workspace's Connections section
- **THEN** the alert that integrations are disabled in the demo is shown there and in no other section

### Requirement: Settings section navigation
Settings SHALL show a navigation that lists the sections the member can use, in the order Appearance, Members, Connections, Slack account, Workspace, and marks the current one as the current page. At desktop width the navigation MUST sit beside the section. At phone width it MUST sit above the section in a compact row that keeps 44px touch targets and does not make the page scroll horizontally.

#### Scenario: Move between sections
- **WHEN** an owner on Appearance chooses Connections in the settings navigation
- **THEN** the address becomes `/settings/connections`, the Connections section is shown, and Connections is marked as the current page

#### Scenario: Phone width
- **WHEN** an owner opens settings at 320px wide
- **THEN** the section navigation is above the section, every section can be reached from it, and the page does not scroll horizontally

### Requirement: Owner-only settings sections
Members and Workspace SHALL be owner-only sections. They MUST NOT appear in a non-owner's settings navigation. When a non-owner opens one by URL, the section MUST say that workspace owners manage invitations, members, connections and deletion, and MUST NOT show any member, invitation, or deletion control.

#### Scenario: Member navigation
- **WHEN** a member who is not an owner opens settings
- **THEN** the navigation lists Appearance, Connections, and Slack account only

#### Scenario: Member follows a link to an owner section
- **WHEN** a member who is not an owner opens `/settings/workspace`
- **THEN** the section says that workspace owners manage invitations, members, connections and deletion, and no "Delete workspace" control is shown

### Requirement: Readable connection facts
Each connection card SHALL identify the connected Slack workspace or GitHub account in plain words. GitHub cards MUST name the repository and its visibility. Cards MUST show when Rescribo last reached the provider; GitHub cards MUST also show when issues last synced. Missing times MUST read "Not yet".

#### Scenario: Connected Slack
- **WHEN** a member opens Connections for a workspace whose Slack connection last succeeded at a known time
- **THEN** the Slack card names the Slack workspace and shows that time beside "Last reached Slack", and shows no scopes or team ID

#### Scenario: Never reached
- **WHEN** a member opens Connections for a GitHub connection with no successful API call and no issue sync
- **THEN** the GitHub card reads "Not yet" beside "Last reached GitHub" and beside "Issues last synced"

#### Scenario: Repository in plain words
- **WHEN** a member opens Connections for a GitHub connection to a private repository
- **THEN** the GitHub card shows the repository name and says it is private

#### Scenario: Missing scopes remain a setup problem
- **WHEN** Slack is connected but lacks required scopes
- **THEN** the card explains that required scopes are missing and how to fix the setup, without showing the raw granted-scope list

### Requirement: Raw connection values
Raw granted-scope lists, provider IDs, and error codes SHALL appear only in the owner-only "Technical details" disclosure. A card MAY show a plain-language setup problem that names missing required Slack scopes.

#### Scenario: A member sees plain connection facts
- **WHEN** a non-owner opens a connection card with scopes, a provider ID, and an error code
- **THEN** none of those raw values are shown

### Requirement: Connection technical details for owners
Each connection card SHALL give an owner a "Technical details" disclosure, collapsed by default, with the raw values: the provider ID, the granted scopes, the last API success time, for GitHub the last issue sync time, and the error code when there is one. An empty value MUST read "None". A non-owner MUST NOT see the disclosure.

#### Scenario: Owner opens technical details
- **WHEN** an owner expands "Technical details" on the Slack card
- **THEN** the Slack team ID and the granted scopes are shown

#### Scenario: Collapsed by default
- **WHEN** an owner opens Connections
- **THEN** each card's technical details are collapsed

#### Scenario: Member sees no technical details
- **WHEN** a member who is not an owner opens Connections
- **THEN** no card has a "Technical details" disclosure

### Requirement: Readable Slack account link
The Slack account section SHALL say in plain words whether the member's Slack account is linked and, when it is, the date it was linked. The Slack user and team IDs MUST appear only in a collapsed "Technical details" disclosure, shown to owners only.

#### Scenario: Member with a linked account
- **WHEN** a member who is not an owner with a linked Slack account opens the Slack account section
- **THEN** the section says the account is linked and when, and shows no Slack user or team ID

#### Scenario: Owner with a linked account
- **WHEN** an owner with a linked Slack account expands "Technical details" in the Slack account section
- **THEN** the Slack user ID and team ID are shown

### Requirement: Links to fix a connection open Connections
A link or redirect that sends a member to settings to connect or fix Slack or GitHub SHALL open the Connections section.

#### Scenario: Release picker without GitHub
- **WHEN** a member follows "Open settings" from the release picker in a workspace without GitHub
- **THEN** the Connections section opens

#### Scenario: Back from provider setup
- **WHEN** an owner completes Slack or GitHub setup and the provider returns to Rescribo
- **THEN** the Connections section opens

### Requirement: Settings section breadcrumbs
On a settings section the header SHALL show "Settings" as a link followed by the section name as the current page. The "Settings" link MUST open `/settings`.

#### Scenario: Connections breadcrumb
- **WHEN** an owner opens `/settings/connections`
- **THEN** the header shows "Settings" as a link followed by "Connections"
