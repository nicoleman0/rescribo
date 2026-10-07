# Spec Delta

## ADDED Requirements

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
