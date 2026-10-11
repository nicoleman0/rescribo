# Spec Delta

## ADDED Requirements

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

## MODIFIED Requirements

### Requirement: Wordmark returns to the inbox
The wordmark in the expanded desktop sidebar SHALL be a link to the inbox. While the sidebar is collapsed to the rail, the wordmark MUST NOT show, and the Inbox destination MUST stay reachable in the rail.

#### Scenario: Wordmark click
- **WHEN** a signed-in member on any screen with the sidebar expanded activates the sidebar wordmark
- **THEN** the inbox opens

#### Scenario: Collapsed sidebar
- **WHEN** a member collapses the sidebar
- **THEN** the wordmark is not shown and the Inbox icon opens the inbox
