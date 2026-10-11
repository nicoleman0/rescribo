# Spec Delta

## MODIFIED Requirements

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

## ADDED Requirements

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
