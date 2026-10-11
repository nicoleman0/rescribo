# Spec Delta

## ADDED Requirements

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
