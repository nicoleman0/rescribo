# Spec Delta

## ADDED Requirements

### Requirement: Markdown create preview
The create preview SHALL render the saved issue body as GitHub-flavoured Markdown, with a single newline shown as a line break. It SHALL keep the label "Exact preview" and show the operation marker as a separate line of literal text. The title SHALL stay plain text.

#### Scenario: Formatted body
- **WHEN** a member previews a body with a heading, a numbered list, a task list, a table, and a fenced code block
- **THEN** the preview shows each as formatted content and none of the Markdown syntax characters

#### Scenario: Single newline
- **WHEN** a member previews a body with two lines separated by one newline
- **THEN** the preview shows them on two lines

#### Scenario: Marker line
- **WHEN** a member previews any body
- **THEN** the operation marker shows below the body as literal text

#### Scenario: Phone width
- **WHEN** a member previews a body with a table and a long code line at phone width
- **THEN** the page does not scroll horizontally

#### Scenario: Accessibility check
- **WHEN** the preview of a formatted body is checked with axe in the light and dark themes
- **THEN** no violations are reported

#### Scenario: Renderer load failure
- **WHEN** the Markdown renderer chunk fails to load
- **THEN** the body remains visible as plain text and the preview says formatted preview could not load

### Requirement: Preview never renders raw HTML
The create preview MUST NOT render raw HTML from the issue body. HTML in the body SHALL show as literal text, so the member reads everything that will be sent.

#### Scenario: HTML element in the body
- **WHEN** a member previews a body containing `<details><summary>More</summary>Hidden</details>`
- **THEN** the preview shows that text literally and creates no `details` element

#### Scenario: Script in the body
- **WHEN** a member previews a body containing a `script` element or an `onerror` attribute
- **THEN** nothing runs and the text shows literally

### Requirement: Preview links and images are safe
Links in the create preview SHALL open in a new tab without access to the opener. Only `http`, `https`, and `mailto` links SHALL be active; any other link shows as text. The preview MUST NOT load images; an image SHALL show as a link with its alt text.

#### Scenario: Web link
- **WHEN** a member previews a body containing `[docs](https://example.com/docs)`
- **THEN** the preview shows a link named "docs" that opens in a new tab with `rel="noopener noreferrer"`

#### Scenario: Unsafe link
- **WHEN** a member previews a body containing `[x](javascript:alert(1))`
- **THEN** the preview shows "x" as text that is not a link

#### Scenario: Relative link
- **WHEN** a member previews a body containing `[x](/settings)`
- **THEN** the preview shows "x" as text that is not a link

#### Scenario: Image
- **WHEN** a member previews a body containing `![chart](https://example.com/chart.png)`
- **THEN** the browser requests no image, and the preview shows a link named "chart"

### Requirement: Preview names what only GitHub adds
The create preview SHALL say that GitHub also links @mentions and #references and notifies each mentioned user. The preview SHALL show such text unchanged.

#### Scenario: Mention in the body
- **WHEN** a member previews a body containing `cc @octocat, see #12`
- **THEN** the preview shows that text unchanged, and the note about mentions and references is visible
