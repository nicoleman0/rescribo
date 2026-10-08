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

### Requirement: Labelled follow-up statuses
Wherever a follow-up shows its employee delivery and customer outcome together, each status SHALL carry a visible label naming which one it is: "Delivery" or "Outcome". A follow-up without a prepared message MUST show its delivery as "Not prepared".

#### Scenario: Follow-up row
- **WHEN** a member views a follow-up whose message was sent and whose customer is not yet contacted
- **THEN** its row reads "Delivery" with a "Sent" badge and "Outcome" with a "Pending" badge

#### Scenario: Message not prepared
- **WHEN** a member views a follow-up that has no prepared message
- **THEN** its row and its detail show "Delivery" with a neutral "Not prepared" badge

### Requirement: Integration status cards
Settings SHALL show Slack and GitHub each as a separate card with a status badge, the connected identity, and the counts of queued, running, failed, and uncertain jobs as labelled numbers. The GitHub card MUST also show the repository. A provider with no connection MUST read "Not connected".

#### Scenario: Connected GitHub
- **WHEN** a member opens settings for a workspace with an active GitHub connection
- **THEN** the GitHub card shows a success "Connected" badge, the repository, and each job count with its label

#### Scenario: Connection needs attention
- **WHEN** a connection is in the error state
- **THEN** its card shows a danger "Needs attention" badge and the error detail

#### Scenario: No connection
- **WHEN** a workspace has never connected Slack
- **THEN** the Slack card shows a neutral "Not connected" badge

### Requirement: Scannable inbox rows
At desktop width each inbox row SHALL fit on one line and start with the report's status badge, followed by the title, customer, assignee, and creation date. An open report SHALL show in a raised panel beside the list on desktop.

#### Scenario: Scan the list
- **WHEN** a member opens the inbox at desktop width
- **THEN** every report row is a single line with its status badge at the left

#### Scenario: Open a report on desktop
- **WHEN** a member opens a report from the list at desktop width
- **THEN** the report shows in a raised panel beside the list and the list stays visible

### Requirement: Inbox status chips
The inbox SHALL offer status filter chips for all reports and for each triage state. Each chip MUST show how many reports match the other active filters.

#### Scenario: Filter by status
- **WHEN** a member searches for a customer and then picks the New chip
- **THEN** only new reports for that customer are listed, and each chip's count covers that customer search

### Requirement: Inbox filters on phones
At phone width the report search and a single Filters button SHALL stay visible. The remaining filters MUST open from that button, and the button MUST show how many filters are active.

#### Scenario: Phone width
- **WHEN** a member opens the inbox at phone width
- **THEN** the search, the Filters button, and the first reports are visible without scrolling, and the other filters stay hidden until the member opens them

### Requirement: Problem next step
Problem detail SHALL show one next-step banner below the header. Its tone and text MUST follow the problem state and the needs-review flag, and it MUST say what a member does next. A problem that needs review MUST show the warning tone and point to the follow-ups and, when one is linked, the GitHub issue.

#### Scenario: Open problem
- **WHEN** a member opens an open problem that does not need review
- **THEN** the banner tells them to confirm the fix once it ships

#### Scenario: Fix available and needs review
- **WHEN** a member opens a problem with a fix available that needs review
- **THEN** the banner uses the warning tone, explains that the GitHub issue or a customer outcome changed after the fix was confirmed, and links to the follow-ups and the GitHub issue

#### Scenario: Fix available
- **WHEN** a member opens a problem with a fix available that does not need review
- **THEN** the banner uses the success tone and links to the follow-ups

### Requirement: Compact linked reports
Problem detail SHALL list each linked report on a compact row with its title, status, customer, a one-line source, and assignee as text. The assignee form MUST open only when the member asks to change it. The full captured source MUST stay on the report page, and the page MUST NOT repeat a landmark name.

#### Scenario: Reassign from a row
- **WHEN** a member chooses Change on a linked report row, picks another member, and saves
- **THEN** the row shows the new assignee as text after the save

#### Scenario: Many linked reports
- **WHEN** a problem with six linked reports is checked with axe
- **THEN** no violations are reported, including duplicate landmarks

### Requirement: Readable problem activity
Problem activity SHALL describe each change in words, never as a raw field or state value. Consecutive links of reports by the same member SHALL show as one entry with the report count, which expands to list each linked report.

#### Scenario: Flagged for review
- **WHEN** the needs-review flag is set on a problem
- **THEN** activity reads that the problem was flagged for review

#### Scenario: Batch of links
- **WHEN** a member links six reports to a problem in a row
- **THEN** activity shows one entry reading "linked 6 reports" that expands to the six report titles
