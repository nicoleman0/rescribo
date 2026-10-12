# engineering-issues Specification

## Purpose

Links each problem to one GitHub issue, creates issues on explicit request, and keeps issue state current.

## Requirements

### Requirement: One issue per problem
A problem SHALL have at most one active GitHub issue link, and an issue SHALL map to at most one problem in a workspace. Relinking SHALL record history and invalidate pending approvals based on the old issue.

#### Scenario: Relink
- **WHEN** a member replaces a problem's linked issue
- **THEN** the old link is kept in history and unsent approvals tied to it are invalidated

### Requirement: Link an existing issue
The system SHALL accept an issue URL or number, verify it belongs to the selected repository, fetch it, and reject pull requests.

#### Scenario: Pull request URL
- **WHEN** a member links a URL that resolves to a pull request
- **THEN** the link is rejected

### Requirement: Create with preview
Issue creation SHALL show an editable title, body, and destination before publishing. The default body contains the problem summary and a product link, without customer identities or raw Slack text. Publishing MUST happen only on an explicit member action.

#### Scenario: Preview not published
- **WHEN** a member opens the create preview and leaves
- **THEN** no GitHub issue exists

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

### Requirement: Recoverable issue creation
The approved issue body SHALL include an opaque operation marker. Before retrying an uncertain create, the system SHALL search the repository for that marker. With no conclusive result, it SHALL require manual reconciliation.

#### Scenario: Timeout after create
- **WHEN** the create request times out and a later search finds the marker
- **THEN** the found issue is linked and no second issue is created

### Requirement: Verified webhooks
The system SHALL verify GitHub webhook signatures, persist the accepted delivery by delivery ID before responding, and process it asynchronously. Duplicate deliveries MUST NOT repeat transitions.

#### Scenario: Duplicate delivery
- **WHEN** GitHub redelivers a delivery ID already accepted
- **THEN** the response succeeds and no second transition occurs

### Requirement: Current state wins
Processing an issue change SHALL fetch the current issue, serialise per issue, and keep provider update times. An older event MUST NOT overwrite newer state.

#### Scenario: Close and reopen arrive reversed
- **WHEN** a reopen event is processed before the earlier close event
- **THEN** the stored state is open

### Requirement: Reconciliation
The system SHALL reconcile active linked issues every 15 minutes and offer a Refresh status action. It SHALL show the last successful sync and stale or access-lost status.

#### Scenario: Missed webhook
- **WHEN** an issue closed while webhooks were not delivered
- **THEN** the next reconciliation or refresh records it as closed

### Requirement: Closure prompts review
A verified close SHALL flag the problem with "Review engineering update" and keep `state_reason`. A close as not planned MUST NOT be treated as a fix.

#### Scenario: Closed as not planned
- **WHEN** the issue closes with reason not planned
- **THEN** the problem is flagged for review and no fix follow-up is created

### Requirement: Reopen invalidates unsent work
Reopening a linked issue SHALL return a `fix_available` problem to `in_progress` with a review flag and invalidate unsent fix notifications. Sent notifications and recorded outcomes SHALL remain, and a later confirmation creates a new revision.

#### Scenario: Reopened after fix
- **WHEN** the linked issue reopens after a fix was confirmed
- **THEN** the problem is `in_progress`, unsent approvals are invalidated, and sent history is unchanged
