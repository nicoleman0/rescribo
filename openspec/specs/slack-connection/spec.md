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
An owner SHALL approve a channel by choosing it from the list of channels the bot is in. The system SHALL check the chosen channel with Slack when it is submitted and MUST NOT rely on the list the browser holds. The system SHALL accept a channel only if it is an internal public or private channel, active, and includes the bot. It MUST reject DMs, group DMs, externally shared, archived, and unknown channels.

#### Scenario: Externally shared channel
- **WHEN** an owner tries to approve a Slack Connect channel
- **THEN** the channel is rejected with the reason shown

#### Scenario: Channel changed after the list loaded
- **WHEN** an owner submits a channel from the list after the bot was removed from it or it was archived
- **THEN** the channel is rejected with the reason shown and the allowed channels do not change

#### Scenario: Channel ID not from the list
- **WHEN** a request submits the ID of a channel that the bot is not in
- **THEN** the channel is rejected and the allowed channels do not change

### Requirement: Channel choice list
Settings SHALL offer an owner the public and private channels the bot is in, by name and kind, when the Slack connection is active. Only an owner SHALL read the list. A Slack Connect channel SHALL appear as unavailable with the reason. Archived channels, DMs, group DMs, and channels already allowed MUST NOT be offered. The list MUST use only the granted bot scopes and MUST NOT call Slack in the demo workspace.

#### Scenario: Owner picks a channel by name
- **WHEN** an owner opens settings and the bot is in `#support` and `#key-accounts`
- **THEN** both channels are offered by name with their kind, and no channel ID has to be typed

#### Scenario: Slack Connect channel in the list
- **WHEN** the bot is in a Slack Connect channel
- **THEN** the list shows it as unavailable with the reason and it cannot be chosen

#### Scenario: Member asks for the list
- **WHEN** a member who is not an owner, or a user of another workspace, requests the list
- **THEN** the request is refused and no Slack call is made

#### Scenario: Demo workspace
- **WHEN** the list is requested for the demo workspace
- **THEN** it is refused and no Slack request is made

### Requirement: Channel choice list states
While the channel list loads, settings SHALL show a loading state. When the bot is in no channel that can be offered, settings SHALL say to invite the app to a channel. When Slack fails or limits the request, settings SHALL show the reason with a retry and MUST keep the allowed channels unchanged. The system SHALL read at most 1,000 channels and MUST say when the list is cut short.

#### Scenario: List is loading
- **WHEN** an owner opens settings before Slack has answered
- **THEN** the channel choice shows a loading state and the allow action is not available

#### Scenario: Bot is in no channel
- **WHEN** the list loads and the bot is in no channel
- **THEN** settings say to invite the app to a channel in Slack and offer to load the list again

#### Scenario: Slack limits the request
- **WHEN** Slack answers the list request with a rate limit
- **THEN** settings say to try again shortly, offer a retry, and the allowed channels stay as they were

#### Scenario: Bot is in more than 1,000 channels
- **WHEN** the bot is in more channels than the system reads
- **THEN** settings show the first 1,000 and say the list is cut short

### Requirement: Channel approval placement and notice
Settings SHALL show the allowed channels and the channel choice before the reconnect, status check, and disconnect actions on the Slack card. The publication notice and its confirmation SHALL sit with the channel choice, and the action that allows a channel MUST stay disabled until the owner confirms. The confirmation for a channel SHALL be separate from the confirmation for connecting Slack.

#### Scenario: Confirm beside the channel choice
- **WHEN** an owner has chosen a channel but has not ticked the confirmation next to it
- **THEN** the allow action is disabled and the notice that reports will be visible to all workspace members is shown beside it

#### Scenario: Return from the Slack redirect
- **WHEN** an owner returns from connecting Slack and opens the channel choice
- **THEN** the confirmation for a channel is on screen with the channel choice and can be ticked there

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
A member SHALL link their Slack user with a short-lived, single-use code generated in their logged-in web session and entered in a Slack modal. The "Link Rescribo account" global shortcut SHALL open that modal without a selected message or channel. Redemption MUST be bound to the signed Slack actor and installed team, never to display name or email.

#### Scenario: Code redeemed from another team
- **WHEN** a code is entered by a Slack user from a different team
- **THEN** redemption fails and no identity is linked

#### Scenario: Linked through the shortcut
- **WHEN** an unlinked Slack user runs "Link Rescribo account" and submits a valid code they generated in Settings
- **THEN** their Slack user is linked to the member who generated the code, the modal confirms it, and Settings shows the link

#### Scenario: Linking needs no message
- **WHEN** a Slack user runs "Link Rescribo account"
- **THEN** no message text, channel, or capture context is stored

### Requirement: Link shortcut outcomes
The "Link Rescribo account" modal SHALL tell the Slack user what happened. A rejected code SHALL keep the modal open with the reason under the code field. A Slack user who is already linked to an active member SHALL see a notice in place of the code field. The request MUST pass the same signature and timestamp check as every Slack request.

#### Scenario: Invalid, expired, or used code
- **WHEN** a Slack user submits a code that is unknown, expired, already used, or issued in another workspace
- **THEN** the modal stays open with an error under the code field and no identity is linked

#### Scenario: Empty code
- **WHEN** a Slack user submits the modal with no code
- **THEN** the modal stays open with an error under the code field

#### Scenario: Already linked
- **WHEN** a Slack user who is linked to an active member runs "Link Rescribo account"
- **THEN** a notice says the account is already linked and that Settings can unlink it, and no code field is shown

#### Scenario: Team without an active connection
- **WHEN** the shortcut is run in a Slack team with no active connection
- **THEN** no modal opens and nothing is stored

#### Scenario: Slack user already linked to another member
- **WHEN** a code is submitted by a Slack user whose identity belongs to a different member
- **THEN** redemption fails with that reason and both members' links are unchanged

### Requirement: Slack link ends with the membership
Revoking a membership SHALL remove that member's Slack link in the same transaction. A Slack user MUST NOT stay linked to a revoked member. Restoring the membership MUST NOT restore the link. A revocation MUST NOT change Slack links in another workspace. A Slack user linked to an active member SHALL still be refused when redeeming another member's code.

#### Scenario: Slack user of a revoked member links to another member
- **WHEN** an owner revokes a member whose Slack user is linked, and that Slack user then submits a valid code generated by another active member
- **THEN** the Slack user is linked to the member who generated the code

#### Scenario: Revoked member is restored
- **WHEN** a revoked member who had a Slack link is restored to the workspace
- **THEN** the member has no Slack link until they redeem a new code

#### Scenario: Revocation in another workspace
- **WHEN** an owner revokes a membership in one workspace and the same person has a linked membership in another workspace
- **THEN** the link in the other workspace is unchanged

#### Scenario: Revocation fails
- **WHEN** a revocation is refused or fails, such as revoking the last active owner
- **THEN** the member stays active and keeps their Slack link

#### Scenario: Slack user linked to an active member
- **WHEN** a Slack user linked to an active member submits a code generated by a different member
- **THEN** redemption fails with the reason that the Slack account is linked to another member, and both members' links are unchanged

#### Scenario: Links left on members revoked earlier
- **WHEN** the system is upgraded and Slack links point at members revoked before this change
- **THEN** those links are removed and their Slack users can link to another member
