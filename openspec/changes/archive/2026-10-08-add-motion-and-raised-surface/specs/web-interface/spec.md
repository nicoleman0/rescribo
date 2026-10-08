# Spec Delta

## ADDED Requirements

### Requirement: Motion confirms changes
The web app SHALL animate a page change, content replacing a loading state, a new row in the inbox, problems, or follow-ups list, a detail panel opening, and a status badge changing state. Every animation MUST finish within 220ms, not counting the row stagger delay, and MUST NOT hold back input or focus.

#### Scenario: Page change
- **WHEN** a member moves from the inbox to problems
- **THEN** the problems page fades in with a short rise

#### Scenario: Content replaces the loading state
- **WHEN** a list finishes loading
- **THEN** its content fades in where the loading skeleton was

#### Scenario: New row on refresh
- **WHEN** a background refresh of the inbox adds one report
- **THEN** only that report's row animates in, and rows already shown stay still

#### Scenario: Status change
- **WHEN** a report in the inbox list changes from New to Linked
- **THEN** its badge colours change with a transition, not a jump

### Requirement: Detail panel motion keeps the place
A detail panel beside a list SHALL slide in only when it opens from no selection. Moving to another item while a panel is open MUST only fade the panel content, and MUST NOT replay the page animation or reset the list, its filters, or its scroll position.

#### Scenario: Open a report
- **WHEN** no report is selected and a member opens one from the inbox
- **THEN** the report panel slides in from the side with a fade

#### Scenario: Next report
- **WHEN** a report is open and the member opens another report
- **THEN** only the panel content fades, the panel stays in place, and the list keeps its filters and scroll position

### Requirement: Reduced motion
When the operating system asks for reduced motion, the web app SHALL show every change without movement, scaling, or animated transitions. State, colour, and shadow changes MUST still appear.

#### Scenario: Reduced motion
- **WHEN** reduced motion is on and a member opens a report and presses a button
- **THEN** the panel appears without a slide or fade and the button does not scale

### Requirement: Raised panels stand apart
Level-2 panels (the report detail, the follow-up detail, and the sign-in card) SHALL use a raised surface colour that is distinct from resting cards in the dark theme. Text on the raised surface MUST meet WCAG 2.1 AA contrast in every theme.

#### Scenario: Dark report panel
- **WHEN** a member in the dark theme opens a report beside the inbox list
- **THEN** the report panel's surface is lighter than the list's card surface

#### Scenario: Raised surface contrast
- **WHEN** an open report panel is checked for colour contrast in the dark theme
- **THEN** no contrast violations are reported
