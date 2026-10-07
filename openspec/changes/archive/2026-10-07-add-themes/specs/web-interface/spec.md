# Spec Delta

## ADDED Requirements

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
