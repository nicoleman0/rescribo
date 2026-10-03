# slack-connection Specification

## Purpose

Connects one Slack workspace to a product workspace, controls which channels may be captured from, and links Slack users to product members.

## Requirements

### Requirement: Owner-initiated OAuth installation
Only an authenticated owner SHALL start Slack installation. The OAuth state MUST be single-use, expire after ten minutes, and be bound to that owner, workspace, and browser session.

#### Scenario: Replayed or expired state
- **WHEN** a callback arrives with a reused, expired, or foreign state
- **THEN** the installation is rejected and no connection is stored

### Requirement: Verified installation identity
On callback the system SHALL verify the returned app, Slack team, and granted scopes. A Slack team MUST NOT be attached to two product workspaces.

#### Scenario: Team already connected elsewhere
- **WHEN** an owner installs into a Slack team already connected to another product workspace
- **THEN** the installation is rejected

### Requirement: Minimal bot scopes
The app SHALL request only `commands`, `channels:read`, `groups:read`, `chat:write`, and `im:write`. It MUST NOT request message history, file, email, or user-token scopes.

#### Scenario: Missing scope
- **WHEN** an installation grants fewer scopes than required
- **THEN** connection settings show the missing scopes as a setup problem

### Requirement: Approved capture channels
An owner SHALL approve channels by ID or link. The system SHALL accept a channel only if it is an internal public or private channel, active, and includes the bot. It MUST reject DMs, group DMs, externally shared, archived, and unknown channels.

#### Scenario: Externally shared channel
- **WHEN** an owner tries to approve a Slack Connect channel
- **THEN** the channel is rejected with the reason shown

### Requirement: Publication notice
Setup and the capture modal SHALL state "This report will be visible to all members of [workspace]." The system MUST NOT claim that Slack channel permissions are preserved.

#### Scenario: Private channel approval
- **WHEN** an owner approves a private channel
- **THEN** setup shows the publication notice before the channel is enabled

### Requirement: Readiness separate from installation
Connection settings SHALL show installation success separately from readiness, listing missing scopes, absent bot membership, and unavailable channels.

#### Scenario: Bot not in channel
- **WHEN** an approved channel no longer includes the bot
- **THEN** settings mark that channel unavailable and capture from it is refused

### Requirement: Removal and revocation
The system SHALL handle Slack URL verification and app-removal events. A verified removal, or a revocation detected through an API error, SHALL disable the connection and cancel pending sends.

#### Scenario: App uninstalled
- **WHEN** a verified app-removal event arrives
- **THEN** the connection is disabled, unsent deliveries are cancelled, and stored reports remain

### Requirement: Slack account linking
A member SHALL link their Slack user with a short-lived, single-use code generated in their logged-in web session and entered in a Slack modal. Redemption MUST be bound to the signed Slack actor and installed team, never to display name or email.

#### Scenario: Code redeemed from another team
- **WHEN** a code is entered by a Slack user from a different team
- **THEN** redemption fails and no identity is linked
