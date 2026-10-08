# Spec Delta

## ADDED Requirements

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
