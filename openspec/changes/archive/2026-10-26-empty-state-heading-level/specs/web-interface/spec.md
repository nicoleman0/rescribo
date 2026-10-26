## ADDED Requirements

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
