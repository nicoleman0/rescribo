# Spec Delta

## ADDED Requirements

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
