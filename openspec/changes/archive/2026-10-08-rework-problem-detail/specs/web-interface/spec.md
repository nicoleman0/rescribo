# Spec Delta

## ADDED Requirements

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
