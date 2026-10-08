# fix-releases Specification

## Purpose
Links a confirmed fix to the release that shipped it, so members can point customers at the release without looking it up by hand.

## Requirements

### Requirement: Choose a release from the connected repository
A member SHALL be able to list published releases from the workspace's connected repository, newest first, 20 per page with a way to load the next page. Draft releases MUST NOT be listed. Pre-releases SHALL be listed and marked as pre-releases.

#### Scenario: Releases listed
- **WHEN** a member opens the release picker on a problem with a confirmed fix and the repository has 25 published releases
- **THEN** the 20 newest are shown with tag, name, and published date, and the member can load the remaining 5

#### Scenario: Pre-release marked
- **WHEN** the repository's newest release is a pre-release
- **THEN** it is listed with a pre-release label

#### Scenario: Draft excluded
- **WHEN** the repository has a draft release
- **THEN** the draft does not appear in the list

### Requirement: Link a release to a confirmed fix
A member SHALL be able to link one release to a problem in `fix_available`. The system SHALL verify the release belongs to the connected repository at link time and store its tag, name, URL, published date, and provider ID. Linking MUST NOT change the fix note, fix version, state, or resolution revision.

#### Scenario: Release linked
- **WHEN** a member links release `v4.13` to a problem with a confirmed fix
- **THEN** the confirmed fix card shows a link to the `v4.13` release with its name and published date, and the activity records who linked it

#### Scenario: Problem without a confirmed fix
- **WHEN** a member tries to link a release to an `open` problem
- **THEN** the request is rejected and nothing is stored

#### Scenario: Stale problem version
- **WHEN** a member links a release using an out-of-date problem version
- **THEN** the request is rejected as a conflict and the existing link is unchanged

### Requirement: Replace or remove a linked release
A member SHALL be able to replace the linked release with another one, or remove it. Each change SHALL be recorded in the problem's activity.

#### Scenario: Release replaced
- **WHEN** a member links `v4.14` to a problem already linked to `v4.13`
- **THEN** the card shows `v4.14` and the activity records the change

#### Scenario: Release removed
- **WHEN** a member removes the linked release
- **THEN** the card shows no release and the activity records the removal

### Requirement: Snapshot of the linked release
The system SHALL show the stored release details and MUST NOT read the release from the provider after linking. A release deleted or edited on the provider SHALL keep showing as stored.

#### Scenario: Release deleted on GitHub
- **WHEN** a linked release is deleted on GitHub
- **THEN** the confirmed fix card still shows the stored tag, name, and link

### Requirement: Release access unavailable
When the workspace has no active GitHub connection, or the installation has not granted release access, the release picker SHALL say why and what to do, and linking MUST be refused. In the demo workspace, releases MUST NOT be fetched from GitHub; seeded release links SHALL still be shown.

#### Scenario: No connected repository
- **WHEN** a member opens the release picker in a workspace without an active GitHub connection
- **THEN** the picker says to connect GitHub in workspace settings and lists no releases

#### Scenario: Installation without release access
- **WHEN** the GitHub installation has not accepted the Contents read permission
- **THEN** the picker says the installation owner must grant release access, and issue features keep working

#### Scenario: Demo workspace
- **WHEN** a visitor opens a fixed problem in the demo workspace
- **THEN** the seeded linked release is shown and no GitHub request is made
