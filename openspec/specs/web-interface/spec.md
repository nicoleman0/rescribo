# web-interface Specification

## Purpose

Defines the product screens and the shared behaviour every screen must have: states, accessibility, and draft safety.

## Requirements

### Requirement: Form errors for fields not shown
When a validation reply names a field that the form does not show, the form's error summary SHALL show that field's name and its message. An error shown under its field MUST NOT be repeated in the summary. An error that belongs to no field SHALL show in the summary without a field name. The summary MUST NOT show a bare reason code, and MUST NOT show the reply's own message twice.

#### Scenario: Field the form does not show
- **WHEN** an owner submits the Slack connect form and the reply rejects `repository` with "This field may not be blank."
- **THEN** the card's error reads "Repository: This field may not be blank." below the reply's message

#### Scenario: Field the form shows
- **WHEN** an owner submits the GitHub connect form and the reply rejects `repository`
- **THEN** the message shows under the repository field and the card's error does not repeat it

#### Scenario: Error that belongs to no field
- **WHEN** a reply carries a validation message that belongs to no field
- **THEN** the form's error shows that message with no field name

#### Scenario: Reply that already explains the field
- **WHEN** a reply's field error only repeats the reply's reason code or its message
- **THEN** the form's error shows the reply's message once and no extra line

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
The wordmark in the expanded desktop sidebar SHALL be a link to the inbox. While the sidebar is collapsed to the rail, the wordmark MUST NOT show, and the Inbox destination MUST stay reachable in the rail.

#### Scenario: Wordmark click
- **WHEN** a signed-in member on any screen with the sidebar expanded activates the sidebar wordmark
- **THEN** the inbox opens

#### Scenario: Collapsed sidebar
- **WHEN** a member collapses the sidebar
- **THEN** the wordmark is not shown and the Inbox icon opens the inbox

### Requirement: Collapsible sidebar
At desktop width a member SHALL be able to collapse the sidebar to a rail of icons and expand it again, by pointer and by keyboard. The choice MUST persist in that browser across reloads. In the rail every destination MUST keep its accessible name and show its name on hover or focus. At phone width the app MUST keep the bottom tab bar and MUST NOT show the sidebar or the rail.

#### Scenario: Collapse and reload
- **WHEN** a member collapses the sidebar at desktop width and reloads the page
- **THEN** the sidebar is still a rail of icons and the content area is wider

#### Scenario: Navigate from the rail
- **WHEN** a member with the sidebar collapsed activates the Problems icon
- **THEN** the problems list opens and the sidebar stays collapsed

#### Scenario: Keyboard only
- **WHEN** a member tabs from the top of the page with the sidebar collapsed
- **THEN** "Skip to main content" is the first stop, every destination is reachable with a visible focus, and each announces its name

#### Scenario: Phone width
- **WHEN** a member opens the inbox at phone width
- **THEN** the bottom tab bar shows the four destinations with 44px touch targets and no sidebar or rail is shown

### Requirement: User menu
The shell SHALL offer a user menu that shows the signed-in member's name and email and holds the theme choice and Sign out. The menu MUST be reachable at desktop and phone width, with the sidebar expanded or collapsed, and MUST be fully operable by keyboard. Sign out MUST NOT appear outside the menu on a product screen. A sign-out that fails MUST leave the member signed in and show the reason.

#### Scenario: Open the menu
- **WHEN** a member opens the user menu
- **THEN** it shows their name and email, the theme choice with the current theme marked, and Sign out

#### Scenario: Sign out
- **WHEN** a member chooses Sign out in the user menu
- **THEN** the sign-in screen opens and the inbox is no longer reachable without signing in

#### Scenario: Sign out fails
- **WHEN** a member chooses Sign out and the request fails
- **THEN** the member stays on the same screen and a message explains that sign-out failed

#### Scenario: Keyboard only
- **WHEN** a member focuses the user menu, presses Enter, and presses Escape
- **THEN** the menu opens with focus inside it, then closes with focus back on its trigger

#### Scenario: Phone width
- **WHEN** a member opens the user menu at phone width
- **THEN** the menu shows the same items, its trigger is at least 44px, and the page does not scroll horizontally

### Requirement: Running version in the user menu
The user menu SHALL show the version of Rescribo the server runs, as "Rescribo" followed by the version, below the member's email. The version SHALL be the release version the server was built from. Only a signed-in member SHALL be able to read it. While the version loads, or when it cannot load, the menu MUST show no version line and keep every other item working.

#### Scenario: Open the menu
- **WHEN** a member opens the user menu on a server built from release 0.1.0
- **THEN** the menu shows "Rescribo 0.1.0" below their email

#### Scenario: Signed out
- **WHEN** a request without a session asks the API for the running version
- **THEN** the API refuses it as unauthenticated and returns no version

#### Scenario: Version unavailable
- **WHEN** a member opens the user menu and the version request fails
- **THEN** the menu shows their name, email, theme choice, and Sign out, and no version line

### Requirement: Theme choice in the user menu
The user menu SHALL offer the same theme choices as Settings: light, dark, and system. A choice made in either place MUST apply at once, persist the same way, and show as the current choice in the other.

#### Scenario: Choose dark from the menu
- **WHEN** a member picks dark in the user menu and then opens Settings
- **THEN** the screen is dark and the Settings theme choice shows dark

### Requirement: Navigation counts
The Inbox destination SHALL show the number of new reports in the workspace, and the Follow-ups destination SHALL show the number of follow-ups that need approval. A count of zero MUST show no number. The counts MUST update after a member's own triage or approval without a reload, and MUST refresh with bounded polling. Each count MUST be announced with what it counts, and MUST NOT change the destination's accessible name. The counts MUST cover only the member's workspace.

#### Scenario: New reports
- **WHEN** a member opens any screen of a workspace with three new reports
- **THEN** the Inbox destination shows 3, announced as three new reports

#### Scenario: Nothing waiting
- **WHEN** no follow-up in the workspace needs approval
- **THEN** the Follow-ups destination shows no number

#### Scenario: Count follows triage
- **WHEN** a member dismisses one of three new reports
- **THEN** the Inbox destination shows 2 without a reload

#### Scenario: Collapsed sidebar
- **WHEN** the sidebar is collapsed and two follow-ups need approval
- **THEN** the Follow-ups icon still shows 2

#### Scenario: Count cannot load
- **WHEN** the request for a count fails
- **THEN** the destination shows no number and still opens its screen

### Requirement: Breadcrumbs
The header SHALL show a breadcrumb trail for the current screen in place of the tagline. A list screen MUST show its section. A full detail page MUST show its section as a link to the list, followed by the record's title as the current page. The trail MUST fit at phone width without horizontal scrolling.

#### Scenario: List screen
- **WHEN** a member opens the problems list
- **THEN** the header shows "Problems" as the current page

#### Scenario: Problem detail
- **WHEN** a member opens a problem
- **THEN** the header shows "Problems" as a link followed by the problem's title, and the link opens the problems list

#### Scenario: Follow-up full page
- **WHEN** a member opens the full page of a follow-up
- **THEN** the header shows "Follow-ups" as a link followed by the report's title

#### Scenario: Title still loading
- **WHEN** a problem page is open and its title has not loaded
- **THEN** the trail shows "Problems" followed by "Problem"

#### Scenario: Long title on a phone
- **WHEN** a member opens a problem with a long title at phone width
- **THEN** the title is cut short with an ellipsis and the page does not scroll horizontally

### Requirement: Demo label survives the shell layout
In a demo workspace the shell SHALL show the demo label at desktop width with the sidebar expanded or collapsed, and at phone width.

#### Scenario: Collapsed sidebar in the demo
- **WHEN** a demo visitor collapses the sidebar
- **THEN** the Demo label is still shown on the screen

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
Problem detail SHALL list each linked report on a compact row with its title, status, customer, a one-line source, and assignee as text. The assignee picker MUST open only when the member asks to change it. The full captured source MUST stay on the report page, and the page MUST NOT repeat a landmark name.

#### Scenario: Reassign from a row
- **WHEN** a member opens the assignee picker on a linked report row and chooses another member
- **THEN** the row shows the new assignee as text and the picker closes after the save

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

### Requirement: Mark problems with no reports
The problems list and the problem detail header SHALL show a "No reports" status in the warning tone on an `open` or `in_progress` problem that has no linked reports. A problem with a linked report, and a `fix_available` or `not_planned` problem, MUST NOT show it. The problem picker MUST keep a problem with no reports selectable.

#### Scenario: Empty problem in the list
- **WHEN** a member ungroups the only report of an open problem and opens the problems list
- **THEN** that row shows "No reports" beside its Open status

#### Scenario: Empty problem detail
- **WHEN** a member opens an in-progress problem with no linked reports
- **THEN** the header shows "No reports" beside its In progress status, and the linked reports section says no reports are linked and that the problem and its history are kept

#### Scenario: Report linked again
- **WHEN** a member links a report to a problem that shows "No reports"
- **THEN** the problem no longer shows "No reports" in the list or on its detail page

#### Scenario: Settled problem
- **WHEN** a `not_planned` or `fix_available` problem has no linked reports
- **THEN** it does not show "No reports"

#### Scenario: Pick an empty problem
- **WHEN** a member links a report and the picker lists a problem with no reports
- **THEN** the member can choose that problem

### Requirement: Shared signed-out layout
The sign-in, accept-invite, and reset-password pages SHALL share one layout that shows the product name, one line about what the product does, the page heading, and the page's form or message. Each page MUST have exactly one level-1 heading, which names the page.

#### Scenario: Desktop sign-in
- **WHEN** a signed-out person opens sign-in at desktop width
- **THEN** the product name and the line about the product show beside the sign-in form

#### Scenario: Same layout on a token page
- **WHEN** a person opens an expired invitation or reset link
- **THEN** the page shows the same product name and line, with the expiry message where the form would be

#### Scenario: Phone width
- **WHEN** any of the three pages is opened at phone width
- **THEN** the product name and line show above the form, and the page does not scroll horizontally

#### Scenario: Accessibility check
- **WHEN** sign-in is checked with axe in the light and dark themes
- **THEN** no violations are reported

### Requirement: Full-size signed-out controls
On the sign-in, accept-invite, and reset-password pages, the submit action SHALL be as tall as the text inputs of its form and span the form's width. At phone width every input and action MUST keep a 44px touch target.

#### Scenario: Desktop sign-in
- **WHEN** a person opens sign-in at desktop width
- **THEN** the Sign in button is as tall and as wide as the Email input

#### Scenario: Phone width
- **WHEN** a person opens sign-in at phone width
- **THEN** the inputs and the Sign in button are at least 44px tall

### Requirement: Demo sign-in hint
When the instance offers a demo, the sign-in page SHALL show a hint with the demo visitor email and password and an action that fills the sign-in form with them. The hint MUST say the demo data is fictitious. When no demo is offered, or the offer cannot be read, the page MUST show no hint and sign-in MUST still work. The accept-invite and reset-password pages MUST NOT show the hint.

#### Scenario: Use the demo login
- **WHEN** a demo is offered and a visitor chooses the hint's action, then Sign in
- **THEN** the form holds the demo email and password, and the demo inbox opens

#### Scenario: No demo
- **WHEN** the instance offers no demo and a person opens sign-in
- **THEN** the page shows no demo hint

#### Scenario: Offer cannot be read
- **WHEN** the demo offer request fails
- **THEN** the page shows no hint and no error, and a member can still sign in

#### Scenario: Keyboard only
- **WHEN** a visitor reaches the hint's action with the keyboard and activates it
- **THEN** the form is filled and focus is on the Sign in button

#### Scenario: Auth pages have no demo hint
- **WHEN** a person opens accept-invite or reset-password
- **THEN** the demo hint does not appear

### Requirement: Command palette
Every signed-in product screen SHALL offer a command palette. It MUST open from a trigger in the header at desktop and phone width, and from Cmd+K or Ctrl+K, including while focus is in a text field. The same key MUST close it, and so MUST Escape. Closing without choosing a command MUST return focus to where it was. The signed-out pages MUST NOT offer the palette.

#### Scenario: Open with the keyboard
- **WHEN** a member on the inbox presses Ctrl+K
- **THEN** the palette opens with focus in its search field

#### Scenario: Open while typing
- **WHEN** a member with focus in the inbox search field presses Cmd+K
- **THEN** the palette opens and the inbox search text is unchanged

#### Scenario: Open from the trigger
- **WHEN** a member activates the palette trigger in the header
- **THEN** the palette opens

#### Scenario: Close
- **WHEN** a member opens the palette from the trigger and presses Escape
- **THEN** the palette closes, focus is on the trigger, and the screen is unchanged

#### Scenario: Signed out
- **WHEN** a signed-out person on sign-in presses Ctrl+K
- **THEN** no palette opens

### Requirement: Go to a screen from the palette
The palette SHALL list the product screens: Inbox, Problems, Follow-ups, Settings, and New report. Typed text MUST narrow the list. Choosing a screen MUST open it and close the palette.

#### Scenario: Go to problems
- **WHEN** a member on the inbox opens the palette, types "prob", and presses Enter
- **THEN** the problems list opens and the palette is closed

#### Scenario: Nothing typed
- **WHEN** a member opens the palette
- **THEN** all five screens are listed before anything is typed

### Requirement: Find reports and problems from the palette
When a member has typed at least two characters, the palette SHALL list reports and problems that match the text, each kind under its own heading, with at most five of each. The matches MUST be the ones the inbox search and the problems list search return for that text, and MUST come only from the member's workspace. Choosing a report MUST open it in the inbox. Choosing a problem MUST open its page.

#### Scenario: Find a problem by title
- **WHEN** a member types part of a problem's title and chooses that problem
- **THEN** the problem's page opens and the palette is closed

#### Scenario: Find a report by title
- **WHEN** a member types part of a report's title and chooses that report
- **THEN** the inbox opens with that report shown

#### Scenario: One character
- **WHEN** a member has typed one character
- **THEN** no report or problem search is made

#### Scenario: Another workspace
- **WHEN** a member types the title of a report that belongs to another workspace
- **THEN** that report is not listed

### Requirement: Palette search states
While a palette search is running the palette SHALL say so. When nothing matches the typed text, it MUST say that nothing was found. When a search fails, it MUST say which search failed and offer a retry, and the screen and theme commands MUST stay usable.

#### Scenario: Nothing found
- **WHEN** a member types text that matches no screen, command, report, or problem
- **THEN** the palette says nothing was found

#### Scenario: Search fails
- **WHEN** the report search request fails
- **THEN** the palette says reports could not be searched and offers a retry, and matching problems and screens are still listed

#### Scenario: Retry
- **WHEN** a member chooses the retry after a failed report search
- **THEN** only the report search repeats

### Requirement: Change the theme from the palette
The palette SHALL offer the same theme choices as Settings and the user menu, with the current choice marked. Choosing one MUST apply at once and persist the same way as a choice made in Settings.

#### Scenario: Choose dark
- **WHEN** a member opens the palette, chooses the dark theme, and then opens Settings
- **THEN** the screen is dark and the Settings theme choice shows dark

### Requirement: Keyboard shortcuts listed in the palette
At desktop width the palette SHALL list every keyboard shortcut of the app with its keys, including the palette's own and the sidebar toggle. The keys MUST be shown as Cmd on Apple devices and Ctrl elsewhere. Choosing a listed shortcut MUST do what its keys do. The palette trigger MUST show the palette's keys at desktop width.

#### Scenario: Shortcut list
- **WHEN** a member on Windows opens the palette at desktop width
- **THEN** it lists "Toggle sidebar" with Ctrl B and "Open command palette" with Ctrl K

#### Scenario: Run a listed shortcut
- **WHEN** a member with the sidebar expanded chooses "Toggle sidebar" in the palette
- **THEN** the sidebar collapses to the rail and the palette is closed

#### Scenario: Sidebar keys still work
- **WHEN** a member presses Ctrl+B with the palette closed
- **THEN** the sidebar collapses, as it did before the palette existed

#### Scenario: Phone width
- **WHEN** a member opens the palette at phone width
- **THEN** no keyboard shortcuts are listed

### Requirement: Palette keyboard and phone use
The palette SHALL be fully operable by keyboard: arrow keys move through the items, Enter chooses the highlighted one, and focus stays inside the palette while it is open. At phone width the trigger and every item MUST keep a 44px touch target and the page MUST NOT scroll horizontally. The open palette MUST pass the accessibility checks in every theme, and MUST open without movement or fading under reduced motion.

#### Scenario: Keyboard only
- **WHEN** a member opens the palette, presses the down arrow twice, and presses Enter
- **THEN** the third item's command runs

#### Scenario: Phone width
- **WHEN** a member opens the palette at phone width
- **THEN** the trigger and each item are at least 44px tall and the page does not scroll horizontally

#### Scenario: Accessibility check
- **WHEN** the open palette with search results is checked with axe in the light and dark themes
- **THEN** no violations are reported

#### Scenario: Reduced motion
- **WHEN** reduced motion is on and a member opens the palette
- **THEN** the palette appears without a fade or movement

### Requirement: Palette choice
A member SHALL be able to choose a palette in Settings, Appearance: indigo, forest, autumn, or sky. The palette MUST be independent of the theme and work in light and dark. The choice MUST persist in that browser across reloads and sign-out, and MUST apply before the first paint of any screen, including sign-in. With no saved choice, or an unknown saved value, the palette is indigo.

#### Scenario: Choose forest
- **WHEN** a member picks forest in Settings and reloads the page
- **THEN** every screen renders with the forest palette from the first paint

#### Scenario: Palette survives sign-out
- **WHEN** a member who picked sky signs out
- **THEN** the sign-in screen renders with the sky palette

#### Scenario: Palette and theme combine
- **WHEN** a member who picked autumn switches the theme from light to dark
- **THEN** the screen shows the dark autumn palette and the palette choice still shows autumn

#### Scenario: Default palette
- **WHEN** a member with no saved palette opens any screen
- **THEN** it renders with the indigo palette, unchanged from before palettes existed

### Requirement: Palette swatch picker
The palette choice SHALL be a group named "Palette" with one option per palette. Each option MUST show its palette's brand colour in the current theme and its name as visible text, MUST mark the current palette, and MUST be operable by keyboard. At phone width each option MUST keep a 44px touch target.

#### Scenario: Keyboard choice
- **WHEN** a member tabs to the Palette group and presses the arrow keys
- **THEN** the next palette is selected and applied at once

#### Scenario: Swatches follow the theme
- **WHEN** a member in the dark theme opens Settings, Appearance
- **THEN** each swatch shows that palette's dark brand colour

### Requirement: Palettes leave status colours fixed
A palette SHALL change only the brand colour, the focus ring, the selection highlight, and the tint of neutral surfaces, borders, and text. Status badge colours and destructive actions MUST be identical in every palette.

#### Scenario: Status badge in another palette
- **WHEN** a member views the same status badge in indigo and then in forest
- **THEN** the badge background, text, and dot colours are the same in both

### Requirement: Readable text in every palette
Text, links, and buttons SHALL meet WCAG 2.1 AA contrast in every palette and theme: 4.5:1 for text against every surface it sits on, and 3:1 for the focus ring against the surfaces it outlines.

#### Scenario: Every palette in both themes
- **WHEN** the colour tokens of each palette are checked in light and dark
- **THEN** every checked pair meets its contrast threshold

#### Scenario: Settings in a non-default palette
- **WHEN** Settings is checked with axe in the forest palette in light and in dark
- **THEN** no violations are reported

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

### Requirement: Settings sections
Settings SHALL be split into sections, each at its own URL: Appearance at `/settings/appearance`, Members at `/settings/members`, Connections at `/settings/connections`, Slack account at `/settings/slack-account`, and Workspace at `/settings/workspace`. Settings MUST show one section at a time. `/settings` MUST redirect to Appearance. Opening a section URL directly MUST show that section.

#### Scenario: Settings opens on Appearance
- **WHEN** a member opens `/settings`
- **THEN** the address becomes `/settings/appearance` and the theme choice is shown

#### Scenario: A link opens one section
- **WHEN** an owner opens `/settings/connections`
- **THEN** the Slack and GitHub cards are shown, and the theme choice, members list, and workspace deletion are not

#### Scenario: Demo alert sits with the connections
- **WHEN** a visitor opens the demo workspace's Connections section
- **THEN** the alert that integrations are disabled in the demo is shown there and in no other section

### Requirement: Settings section navigation
Settings SHALL show a navigation that lists the sections the member can use, in the order Appearance, Members, Connections, Slack account, Workspace, and marks the current one as the current page. At desktop width the navigation MUST sit beside the section. At phone width it MUST sit above the section in a compact row that keeps 44px touch targets and does not make the page scroll horizontally.

#### Scenario: Move between sections
- **WHEN** an owner on Appearance chooses Connections in the settings navigation
- **THEN** the address becomes `/settings/connections`, the Connections section is shown, and Connections is marked as the current page

#### Scenario: Phone width
- **WHEN** an owner opens settings at 320px wide
- **THEN** the section navigation is above the section, every section can be reached from it, and the page does not scroll horizontally

### Requirement: Owner-only settings sections
Members and Workspace SHALL be owner-only sections. They MUST NOT appear in a non-owner's settings navigation. When a non-owner opens one by URL, the section MUST say that workspace owners manage invitations, members, connections and deletion, and MUST NOT show any member, invitation, or deletion control.

#### Scenario: Member navigation
- **WHEN** a member who is not an owner opens settings
- **THEN** the navigation lists Appearance, Connections, and Slack account only

#### Scenario: Member follows a link to an owner section
- **WHEN** a member who is not an owner opens `/settings/workspace`
- **THEN** the section says that workspace owners manage invitations, members, connections and deletion, and no "Delete workspace" control is shown

### Requirement: Readable connection facts
Each connection card SHALL identify the connected Slack workspace or GitHub account in plain words. GitHub cards MUST name the repository and its visibility. Cards MUST show when Rescribo last reached the provider; GitHub cards MUST also show when issues last synced. Missing times MUST read "Not yet".

#### Scenario: Connected Slack
- **WHEN** a member opens Connections for a workspace whose Slack connection last succeeded at a known time
- **THEN** the Slack card names the Slack workspace and shows that time beside "Last reached Slack", and shows no scopes or team ID

#### Scenario: Never reached
- **WHEN** a member opens Connections for a GitHub connection with no successful API call and no issue sync
- **THEN** the GitHub card reads "Not yet" beside "Last reached GitHub" and beside "Issues last synced"

#### Scenario: Repository in plain words
- **WHEN** a member opens Connections for a GitHub connection to a private repository
- **THEN** the GitHub card shows the repository name and says it is private

#### Scenario: Missing scopes remain a setup problem
- **WHEN** Slack is connected but lacks required scopes
- **THEN** the card explains that required scopes are missing and how to fix the setup, without showing the raw granted-scope list

### Requirement: Raw connection values
Raw granted-scope lists, provider IDs, and error codes SHALL appear only in the owner-only "Technical details" disclosure. A card MAY show a plain-language setup problem that names missing required Slack scopes.

#### Scenario: A member sees plain connection facts
- **WHEN** a non-owner opens a connection card with scopes, a provider ID, and an error code
- **THEN** none of those raw values are shown

### Requirement: Connection technical details for owners
Each connection card SHALL give an owner a "Technical details" disclosure, collapsed by default, with the raw values: the provider ID, the granted scopes, the last API success time, for GitHub the last issue sync time, and the error code when there is one. An empty value MUST read "None". A non-owner MUST NOT see the disclosure.

#### Scenario: Owner opens technical details
- **WHEN** an owner expands "Technical details" on the Slack card
- **THEN** the Slack team ID and the granted scopes are shown

#### Scenario: Collapsed by default
- **WHEN** an owner opens Connections
- **THEN** each card's technical details are collapsed

#### Scenario: Member sees no technical details
- **WHEN** a member who is not an owner opens Connections
- **THEN** no card has a "Technical details" disclosure

### Requirement: Readable Slack account link
The Slack account section SHALL say in plain words whether the member's Slack account is linked and, when it is, the date it was linked. The Slack user and team IDs MUST appear only in a collapsed "Technical details" disclosure, shown to owners only.

#### Scenario: Member with a linked account
- **WHEN** a member who is not an owner with a linked Slack account opens the Slack account section
- **THEN** the section says the account is linked and when, and shows no Slack user or team ID

#### Scenario: Owner with a linked account
- **WHEN** an owner with a linked Slack account expands "Technical details" in the Slack account section
- **THEN** the Slack user ID and team ID are shown

### Requirement: Links to fix a connection open Connections
A link or redirect that sends a member to settings to connect or fix Slack or GitHub SHALL open the Connections section.

#### Scenario: Release picker without GitHub
- **WHEN** a member follows "Open settings" from the release picker in a workspace without GitHub
- **THEN** the Connections section opens

#### Scenario: Back from provider setup
- **WHEN** an owner completes Slack or GitHub setup and the provider returns to Rescribo
- **THEN** the Connections section opens

### Requirement: Settings section breadcrumbs
On a settings section the header SHALL show "Settings" as a link followed by the section name as the current page. The "Settings" link MUST open `/settings`.

#### Scenario: Connections breadcrumb
- **WHEN** an owner opens `/settings/connections`
- **THEN** the header shows "Settings" as a link followed by "Connections"

### Requirement: Problem detail touch targets on phones
At phone width, every standalone link on problem detail SHALL keep a 44px touch target. A standalone link is one that is not part of a sentence: a linked report title, the activity entry that folds several report links and the report links it reveals, the GitHub issue link, the release and fix evidence links, and the links offered after creating an issue or when GitHub is not connected. A link inside running text MAY stay at text height. Desktop width MUST keep its compact layout.

#### Scenario: Standalone links at phone width
- **WHEN** a member opens a problem with a confirmed fix, a linked release, a linked GitHub issue, and several reports linked together, at phone width
- **THEN** each linked report title, the folded activity entry, the release link, and the GitHub issue link are at least 44px tall and the page does not scroll horizontally

#### Scenario: Folded report links
- **WHEN** a member opens the folded "linked N reports" activity entry at phone width
- **THEN** each report link it reveals is at least 44px tall

#### Scenario: Links inside a sentence
- **WHEN** an activity entry reads "moved" a report "here from" another problem at phone width
- **THEN** the report and problem links stay at text height inside the sentence

#### Scenario: Desktop width
- **WHEN** a member opens the same problem at desktop width
- **THEN** the links keep their text height

### Requirement: Empty states keep one page heading
An empty, not-found, or access-removed state SHALL NOT add a second level-1 heading to a signed-in page. Inside a page or panel whose page already has a level-1 heading, the state's title MUST be a level-2 heading. Where the state is the only content of the page, its title MUST be the page's one level-1 heading.

#### Scenario: Empty list page
- **WHEN** a member opens Inbox, Problems, or Follow-ups and the list has no rows, including when filters or a search match nothing
- **THEN** the page has exactly one level-1 heading, the page name, and the empty state's title is a level-2 heading

#### Scenario: Missing record in a panel
- **WHEN** a member opens a report or follow-up in the panel beside its list and the record is not found or access was removed
- **THEN** the page has exactly one level-1 heading, the list page name, and the panel's state title is a level-2 heading

#### Scenario: Missing record on a full page
- **WHEN** a member opens a problem page or a follow-up full page and the record is not found or access was removed
- **THEN** the state's title is the page's only level-1 heading

#### Scenario: Unknown route
- **WHEN** a person opens a path the app does not know
- **THEN** "Page not found" is the page's only level-1 heading

#### Scenario: No workspace left
- **WHEN** a signed-in person has no workspace membership
- **THEN** "Workspace access removed" is the page's only level-1 heading

### Requirement: Model provider card
Settings Connections SHALL show a model provider card after the Slack and GitHub cards. It SHALL show a status badge, the API style, base URL, model, and when the provider was last reached. With no connection it MUST read "Not connected". The card MUST NOT show job counts.

#### Scenario: Active model connection
- **WHEN** a member opens Connections for a workspace with an active model connection
- **THEN** the model card shows a success "Connected" badge, the API style, base URL, model, and last reached time, and no job counts

#### Scenario: Never connected
- **WHEN** a member opens Connections for a workspace with no model connection
- **THEN** the model card shows a neutral "Not connected" badge

### Requirement: Model provider form
An owner SHALL see a form with a provider choice (OpenAI, Anthropic, Google, OpenRouter, Other OpenAI-compatible), base URL, model, API key, and a consent checkbox. Choosing a named provider SHALL fill its base URL. The connect button MUST stay disabled until consent is checked. The key field MUST NOT show a stored key.

#### Scenario: Pick a named provider
- **WHEN** an owner picks Anthropic
- **THEN** the base URL fills with Anthropic's API URL and the API style is Anthropic

#### Scenario: Test fails
- **WHEN** an owner submits the form and the connection test fails
- **THEN** the form stays filled except for the key and an error names the reason

#### Scenario: Member view
- **WHEN** a member who is not an owner opens Connections
- **THEN** the model card shows status only and asks them to contact an owner

### Requirement: Locked deployment provider
When the deployment config file sets the provider, the model card SHALL show its values read-only with a note that the deployment manages them. An owner SHALL see only the consent checkbox and an enable button.

#### Scenario: Deployment default
- **WHEN** an owner opens Connections on a deployment whose config file sets the provider
- **THEN** the card shows the configured values as text, no provider, URL, model, or key fields, and an enable button behind the consent checkbox
