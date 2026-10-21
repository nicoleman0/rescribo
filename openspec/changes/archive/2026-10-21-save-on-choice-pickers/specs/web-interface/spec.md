# Spec Delta

## ADDED Requirements

### Requirement: Member pickers save on choice
The report assignee, problem owner, and follow-up recipient SHALL each be set with a picker that opens from a trigger showing the current member, filters members by name as the member types, and saves when a member is chosen. There MUST be no separate save button. The assignee and owner pickers SHALL offer "Unassigned" and "No owner". A current member missing from the members list SHALL still be listed.

#### Scenario: Assign by choosing
- **WHEN** a member opens the assignee picker on a report, types part of a name, and chooses that member
- **THEN** the assignee is saved with no further step

#### Scenario: Clear the owner
- **WHEN** a member opens the owner picker on a problem and chooses "No owner"
- **THEN** the problem is saved with no owner

#### Scenario: Current member no longer listed
- **WHEN** a report's assignee has left the workspace and a member opens its assignee picker
- **THEN** the picker lists that assignee as the current choice

#### Scenario: Recipient without a Slack link
- **WHEN** an owner opens the recipient picker
- **THEN** members without a Slack link are shown as unavailable and cannot be chosen

### Requirement: A choice shows before the save returns
After a member chooses in a member picker, the page SHALL show the new value at once, before the save returns. If the save fails, the page MUST return to the value it showed before the choice. While a save is in progress the picker MUST NOT accept another choice.

#### Scenario: Optimistic assignee
- **WHEN** a member chooses a new assignee on a linked report row and the save is still in progress
- **THEN** the row already shows the new assignee

#### Scenario: Save fails
- **WHEN** a member chooses a new owner and the save fails with a network error
- **THEN** the owner card shows the previous owner again

### Requirement: Failed picker saves stay open
A member picker whose save fails SHALL stay open and show the error inside it, worded as other failed saves are. A version conflict SHALL show the latest version of the record and explain that it changed. Closing the picker SHALL clear the error.

#### Scenario: Version conflict
- **WHEN** another member changed a report and a member then chooses a new assignee for it
- **THEN** the picker stays open, says the report changed while they were working, and the page shows the latest report

#### Scenario: Retry after a failure
- **WHEN** a recipient save fails and the owner chooses another member in the same open picker
- **THEN** that choice is saved

### Requirement: Saves confirmed by toast
A successful member picker save SHALL show a toast that names the result, such as the new assignee. The toast MUST be announced politely to screen readers, MUST close by itself, and MUST NOT take focus. Failures MUST NOT show a toast; they stay inline where the member acted. The toast MUST NOT cover the phone navigation bar.

#### Scenario: Assignee saved
- **WHEN** a member chooses Ana as the assignee and the save succeeds
- **THEN** a toast reads that the report is assigned to Ana, and focus stays where it was

#### Scenario: Save fails without a toast
- **WHEN** a picker save fails
- **THEN** no toast appears and the error shows in the picker

### Requirement: Assignee warning before the choice
The report assignee picker SHALL show, before the member chooses, that a new assignee cancels any unsent employee notification for the report and does not notify anyone or record customer contact.

#### Scenario: Warning in the open picker
- **WHEN** a member opens the assignee picker from a linked report row on problem detail
- **THEN** the warning about cancelled notifications is visible before any member is chosen

### Requirement: Member picker keyboard and touch use
A member picker SHALL open with focus in its search field and be usable with the keyboard alone. Escape SHALL close it and return focus to its trigger. On phones the trigger and each option MUST meet the 44px touch target, and the open picker MUST NOT cause horizontal scrolling.

#### Scenario: Keyboard choice
- **WHEN** a member focuses the owner trigger, presses Enter, types a name, and presses Enter
- **THEN** that member is saved as owner

#### Scenario: Escape
- **WHEN** a member opens a picker and presses Escape
- **THEN** the picker closes, nothing is saved, and focus is on the trigger

#### Scenario: Phone picker
- **WHEN** a member opens the assignee picker on a 390px wide screen
- **THEN** the trigger and options are at least 44px tall and the page does not scroll sideways

## MODIFIED Requirements

### Requirement: Compact linked reports
Problem detail SHALL list each linked report on a compact row with its title, status, customer, a one-line source, and assignee as text. The assignee picker MUST open only when the member asks to change it. The full captured source MUST stay on the report page, and the page MUST NOT repeat a landmark name.

#### Scenario: Reassign from a row
- **WHEN** a member opens the assignee picker on a linked report row and chooses another member
- **THEN** the row shows the new assignee as text and the picker closes after the save

#### Scenario: Many linked reports
- **WHEN** a problem with six linked reports is checked with axe
- **THEN** no violations are reported, including duplicate landmarks
