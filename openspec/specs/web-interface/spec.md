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

### Requirement: Follow-up full page
The web app SHALL show one follow-up on its own page, reachable by URL and from the follow-up side panel. The page MUST offer the same details and actions as the panel, and MUST provide a way back to the follow-ups list. Opening a follow-up from the list MUST still open the side panel.

#### Scenario: Open from the panel
- **WHEN** a member has a follow-up open in the side panel and chooses "Open full page"
- **THEN** the follow-up opens on its own page with its statuses, details, message, customer contact, and history

#### Scenario: Open by URL
- **WHEN** a member opens the full page link of a follow-up in their workspace
- **THEN** the page shows that follow-up without the list

#### Scenario: List click keeps the panel
- **WHEN** a member opens a follow-up from the list
- **THEN** it opens in the side panel beside the list, not on the full page

#### Scenario: Back to the list
- **WHEN** a member opened the full page from the "Needs approval" bucket on page 2 and chooses "Back to follow-ups"
- **THEN** the list shows the "Needs approval" bucket on page 2

#### Scenario: Act on the full page
- **WHEN** a member records a customer outcome on the full page
- **THEN** the outcome is saved and the page shows the new outcome and history entry

#### Scenario: Follow-up from another workspace
- **WHEN** a member opens the full page of a follow-up outside their workspace
- **THEN** the page says the follow-up was not found and offers the way back to the list

#### Scenario: Phone width
- **WHEN** a member opens the full page at phone width
- **THEN** the content is one column with no horizontal scrolling and every action keeps a 44px touch target

### Requirement: Mark reviewed from the next step
The next-step banner of a problem that needs review, including a "Not planned" banner, SHALL offer a Mark reviewed action. After it succeeds, the banner MUST show the next step for the problem's state without a page reload, and a failed attempt MUST explain what went wrong and keep the banner. Problem activity SHALL read "marked the problem reviewed" for this action, and entries that set the flag MUST still read "flagged the problem for review".

#### Scenario: Mark reviewed
- **WHEN** a member chooses Mark reviewed on the banner of a fixed problem that needs review
- **THEN** the banner changes to the success tone for the available fix, the Needs review badge is gone, and activity shows the member marked the problem reviewed

#### Scenario: Flagged problem that is not planned
- **WHEN** a problem in `not_planned` is flagged for review
- **THEN** the "Not planned" banner keeps its heading and offers Mark reviewed, and after it succeeds the Needs review badge is gone

#### Scenario: Someone else already reviewed it
- **WHEN** a member chooses Mark reviewed after another member already marked the problem reviewed
- **THEN** an error explains the problem changed, and the page shows the current problem without the review flag

#### Scenario: Older flag entries
- **WHEN** a problem's activity holds an entry from before this change that set the review flag
- **THEN** that entry still reads "flagged the problem for review"

### Requirement: Connection check result
When an owner checks the status of a Slack or GitHub connection in Settings, the card SHALL show the result of that check beside the check action: that the connection is working, and the time of the check to the second. The result MUST be announced to assistive technology without moving focus. A failed check MUST show its reason and time in the same place. The card MUST NOT show a passed result and a failed result together, and MUST NOT show a passed result for a connection that is not active.

#### Scenario: Check passes
- **WHEN** an owner chooses "Check GitHub status" on an active GitHub connection and the check passes
- **THEN** the place beside the button reads that the GitHub connection is working with the time of the check to the second, and a screen reader announces it

#### Scenario: Repeated check in the same minute
- **WHEN** an owner runs a second passing check less than a minute after the first
- **THEN** the result shows the time of the second check, which differs from the first

#### Scenario: Check fails
- **WHEN** an owner chooses "Check Slack status" and the check fails
- **THEN** the place beside the button shows the reason and the time, and no passed result is shown

#### Scenario: Check passes after a failure
- **WHEN** an owner runs a check that passes after one that failed
- **THEN** the passed result replaces the failure
