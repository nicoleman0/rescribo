# web-interface Specification

## Purpose

Defines the product screens and the shared behaviour every screen must have: states, accessibility, and draft safety.

## Requirements

### Requirement: Product screens
The web app SHALL provide sign-in and invite acceptance, inbox, problems list, problem detail, follow-ups, and settings screens.

#### Scenario: Problem detail
- **WHEN** a member opens a problem
- **THEN** it shows the editable summary, linked reports with provenance, the GitHub link or create flow, fix review, activity, and report reassignment

#### Scenario: Follow-ups queue
- **WHEN** a member opens follow-ups
- **THEN** they are grouped as needs approval, delivery failed or uncertain, awaiting contact, awaiting confirmation, and completed

### Requirement: Asynchronous states
Every asynchronous screen and section SHALL have loading, empty, error, and retry states.

#### Scenario: Load failure
- **WHEN** a list request fails
- **THEN** the section shows an error with a retry action

### Requirement: Read retries never write
A retry on a failed read SHALL refetch only that query. It MUST NOT publish an issue, confirm a fix, delete data, or send a message. Writes are retried only by an explicit user action.

#### Scenario: Retry after error
- **WHEN** a member presses retry on a failed problem detail load
- **THEN** only the read requests repeat

### Requirement: Accessible forms
Forms SHALL have labels, full keyboard operation, visible focus, and inline errors.

#### Scenario: Keyboard only
- **WHEN** a member completes manual capture using only the keyboard
- **THEN** every field and action is reachable and focus is always visible

### Requirement: Draft preservation
Unsaved input SHALL survive recoverable failures, including conflicts and network errors.

#### Scenario: Conflict on save
- **WHEN** a save returns a conflict
- **THEN** the member's edits remain on screen alongside the current data

### Requirement: Responsive layout
The layout SHALL be desktop-first and remain usable at narrow mobile widths without horizontal page scrolling.

#### Scenario: Phone width
- **WHEN** the inbox is opened at phone width
- **THEN** navigation and report actions are usable without horizontal scrolling

### Requirement: Bounded polling
Background state SHALL refresh with bounded polling. Websockets are not required.

#### Scenario: Delivery in progress
- **WHEN** a follow-up is queued
- **THEN** the screen polls until the delivery reaches a final state or the polling limit

### Requirement: Consistent status presentation
Every status shown on a product screen SHALL use one of six tones: neutral, info, progress, success, warning, or danger. A given state MUST use the same tone on every screen, and its text label MUST always be visible so colour is never the only signal.

#### Scenario: Same state on two screens
- **WHEN** a member sees a linked report in the inbox and in a problem's linked-report list
- **THEN** both badges use the success tone and read "Linked"

#### Scenario: Failed delivery
- **WHEN** a follow-up's notification failed to send
- **THEN** its delivery badge uses the danger tone and reads "Failed"

### Requirement: Wordmark returns to the inbox
The wordmark in the desktop sidebar SHALL be a link to the inbox.

#### Scenario: Wordmark click
- **WHEN** a signed-in member on any screen activates the sidebar wordmark
- **THEN** the inbox opens

### Requirement: Theme choice
A member SHALL be able to choose a light, dark, or system theme in Settings. The choice MUST persist in that browser across reloads and sign-out, and MUST apply before the first paint of any screen, including sign-in. With no saved choice the theme is system.

#### Scenario: Choose dark
- **WHEN** a member picks dark in Settings and reloads the page
- **THEN** every screen renders with the dark palette from the first paint

#### Scenario: Choice survives sign-out
- **WHEN** a member who picked dark signs out
- **THEN** the sign-in screen renders dark

### Requirement: System theme follows the operating system
When the theme is system, the app SHALL use dark when the operating system prefers a dark scheme and light otherwise, and MUST switch without a reload when that preference changes.

#### Scenario: Operating system switches to dark
- **WHEN** the theme is system and the operating system changes to a dark scheme
- **THEN** the open screen switches to the dark palette without a reload

### Requirement: Readable status in every theme
Status badges, text, and focus indicators SHALL meet WCAG 2.1 AA contrast in every theme.

#### Scenario: Dark inbox
- **WHEN** the inbox is checked for colour contrast in the dark theme
- **THEN** no contrast violations are reported
