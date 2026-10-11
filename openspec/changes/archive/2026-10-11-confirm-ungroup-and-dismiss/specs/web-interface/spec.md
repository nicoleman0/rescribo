# Spec Delta

## ADDED Requirements

### Requirement: Ungroup and Dismiss ask first
In the report triage actions, Ungroup and Dismiss SHALL each open a confirmation step before the report changes. The step MUST name the action, say what happens to the report, and offer a confirm action and a cancel action. No request to change the report is made until the member confirms. The Ungroup step MUST say that any unsent employee notification for the report is cancelled and that sent history is kept.

#### Scenario: Ungroup asks first
- **WHEN** a member chooses Ungroup on a linked report
- **THEN** the report stays linked, and a step asks them to confirm and says that any unsent employee notification for the report is cancelled and sent history is kept

#### Scenario: Confirm ungroup
- **WHEN** the member confirms the Ungroup step
- **THEN** the report returns to New and the step is gone

#### Scenario: Dismiss asks first
- **WHEN** a member chooses Dismiss on a new report
- **THEN** the report stays New, and a step asks them to confirm and says the report is kept and can be restored

#### Scenario: Confirm dismiss
- **WHEN** the member confirms the Dismiss step
- **THEN** the report shows as Dismissed with the Restore report action

#### Scenario: Cancel
- **WHEN** the member cancels the step
- **THEN** no change is requested, the report is unchanged, and the triage actions show again

#### Scenario: Double click
- **WHEN** a member double-clicks Ungroup or Dismiss
- **THEN** the step is open and the report is unchanged

#### Scenario: Restore does not ask
- **WHEN** a member chooses Restore report on a dismissed report
- **THEN** the report returns to New without a confirmation step

### Requirement: Confirmation step keyboard and touch use
The Ungroup and Dismiss confirmation step SHALL be fully operable by keyboard. When it opens, focus MUST move to the step's title, so repeating the key that opened it does not confirm. Cancel MUST return focus to the action that opened the step. After a confirmed change, focus MUST move to the Triage heading. At phone width the confirm and cancel actions MUST keep a 44px touch target and the page MUST NOT scroll horizontally.

#### Scenario: Keyboard only
- **WHEN** a member presses Enter on Ungroup, then Tab, then Enter
- **THEN** focus moved to the step's title, then to the confirm action, and the report returns to New with focus on the Triage heading

#### Scenario: Repeated Enter
- **WHEN** a member presses Enter twice on Dismiss
- **THEN** the step is open and the report is not dismissed

#### Scenario: Cancel returns focus
- **WHEN** a member opens the Ungroup step and cancels it
- **THEN** focus is on the Ungroup action

#### Scenario: Phone width
- **WHEN** a member opens the step at phone width
- **THEN** the confirm and cancel actions are at least 44px tall and the page does not scroll horizontally

### Requirement: Confirmation step failures
A confirmed Ungroup or Dismiss that fails SHALL keep the step open with the reason, and the member MUST be able to retry or cancel. If the report's state changes so that the action no longer applies, the step MUST close, the current triage actions MUST show, and no other action may be applied in its place.

#### Scenario: Network failure
- **WHEN** the member confirms Ungroup and the request cannot reach the server
- **THEN** the step stays open with an error, and confirming again retries the ungroup

#### Scenario: Report edited meanwhile
- **WHEN** the member confirms Dismiss after another member reassigned the report
- **THEN** the step stays open, an error says the report changed, and confirming again dismisses the current version

#### Scenario: Action no longer applies
- **WHEN** the member confirms Ungroup after another member already ungrouped the report
- **THEN** an error says the report changed, the step closes, the actions for a new report show, and the report is not dismissed
