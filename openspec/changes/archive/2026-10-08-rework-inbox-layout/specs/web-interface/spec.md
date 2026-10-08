# Spec Delta

## ADDED Requirements

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
