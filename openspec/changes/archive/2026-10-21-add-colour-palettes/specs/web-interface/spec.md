# Spec Delta

## ADDED Requirements

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
