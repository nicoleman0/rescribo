# Spec Delta

## MODIFIED Requirements

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

## ADDED Requirements

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
