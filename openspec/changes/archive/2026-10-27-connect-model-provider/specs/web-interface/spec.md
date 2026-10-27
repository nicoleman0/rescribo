# Spec Delta

## ADDED Requirements

### Requirement: Model provider card
Settings Connections SHALL show a model provider card after the Slack and GitHub cards. It SHALL show a status badge, the API style, base URL, model, and when the provider was last reached. With no connection it MUST read "Not connected". The card MUST NOT show job counts.

#### Scenario: Active model connection
- **WHEN** a member opens Connections for a workspace with an active model connection
- **THEN** the model card shows a success "Connected" badge, the API style, base URL, model, and last reached time, and no job counts

#### Scenario: Never connected
- **WHEN** a member opens Connections for a workspace with no model connection
- **THEN** the model card shows a neutral "Not connected" badge

### Requirement: Model provider form
An owner SHALL see a form with a provider choice (OpenAI, Anthropic, Google, OpenRouter, Other OpenAI-compatible), base URL, model, API key, and a consent checkbox. Choosing a named provider SHALL fill its base URL. The connect button MUST stay disabled until consent is checked. The key field MUST NOT show a stored key.

#### Scenario: Pick a named provider
- **WHEN** an owner picks Anthropic
- **THEN** the base URL fills with Anthropic's API URL and the API style is Anthropic

#### Scenario: Test fails
- **WHEN** an owner submits the form and the connection test fails
- **THEN** the form stays filled except for the key and an error names the reason

#### Scenario: Member view
- **WHEN** a member who is not an owner opens Connections
- **THEN** the model card shows status only and asks them to contact an owner

### Requirement: Locked deployment provider
When the deployment config file sets the provider, the model card SHALL show its values read-only with a note that the deployment manages them. An owner SHALL see only the consent checkbox and an enable button.

#### Scenario: Deployment default
- **WHEN** an owner opens Connections on a deployment whose config file sets the provider
- **THEN** the card shows the configured values as text, no provider, URL, model, or key fields, and an enable button behind the consent checkbox
