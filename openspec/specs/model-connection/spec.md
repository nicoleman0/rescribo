# model-connection Specification

## Purpose

Connects a product workspace to one language model provider, so later features can send it workspace content after the owner has agreed to that.

## Requirements

### Requirement: One model provider per workspace
Each workspace SHALL have at most one model provider connection. A connection names an API style (OpenAI-compatible or Anthropic), a base URL, a model name, and an API key. Only an active owner MAY connect, change, check, or disconnect it. Every member SHALL be able to read its status, API style, base URL, and model name.

#### Scenario: Owner connects a provider
- **WHEN** an owner submits the OpenAI-compatible style, a public HTTPS base URL, a model name, an API key, and consent, and the connection test passes
- **THEN** the workspace has an active model connection showing that style, base URL, and model

#### Scenario: Member tries to connect
- **WHEN** a member who is not an owner submits a model connection
- **THEN** the request is refused and nothing changes

#### Scenario: Member reads status
- **WHEN** a member lists the workspace connections
- **THEN** the model connection shows its status, API style, base URL, and model name

### Requirement: Consent before content leaves
Connecting or enabling a model provider SHALL require the owner to accept that conversation and report content from this workspace will be sent to that provider. Without accepted consent the connection MUST NOT be saved and no model call MUST be made.

#### Scenario: Consent not given
- **WHEN** an owner submits a model connection without consent
- **THEN** the request is refused with the consent reason and no request reaches the provider

### Requirement: Structured-output connection test
Connecting and checking status SHALL send a fixed synthetic prompt that contains no workspace content. The test SHALL pass only when the model returns JSON that validates against the test schema. A failed test MUST leave a new connection unsaved and MUST put an existing connection in the error state with a safe error code.

#### Scenario: Key works but output is not valid JSON
- **WHEN** the provider accepts the key and returns text that is not JSON matching the test schema
- **THEN** the connection is not saved and the owner sees that the model did not return structured output

#### Scenario: Rejected key
- **WHEN** the provider answers the test with an authentication error
- **THEN** the connection is not saved and the owner sees that the key was rejected

#### Scenario: Status check fails later
- **WHEN** an owner checks an active model connection and the provider rejects the key
- **THEN** the connection is in the error state with an error detail that names the next step

### Requirement: Public endpoints from Settings
A base URL entered in Settings SHALL use HTTPS and MUST NOT carry credentials, a query, or a fragment. Every request to it SHALL resolve the host, refuse when any resolved address is not publicly routable, and connect to an address it checked. Redirects and proxy settings from the environment MUST NOT be followed.

#### Scenario: Private address entered
- **WHEN** an owner enters a base URL whose host resolves to a loopback, private, link-local, or other non-public address
- **THEN** the connection is refused with a safe reason that does not reveal the resolved address

#### Scenario: Host changes address after saving
- **WHEN** a saved base URL's host later resolves to a private address
- **THEN** the next model request is refused before any connection is opened to that address

#### Scenario: Plain HTTP entered
- **WHEN** an owner enters a base URL that starts with `http://`
- **THEN** the field is rejected

### Requirement: Deployment default from a config file
An operator SHALL be able to set one model provider for every workspace in a deployment config file. The file names the API style, base URL, model, and the environment variable that holds the key, and MUST NOT hold the key. When the file sets a provider, Settings SHALL show it as locked, and owners MUST NOT change its style, base URL, model, or key.

#### Scenario: Deployment default set
- **WHEN** the config file sets a provider and an owner opens Settings
- **THEN** the model card shows the configured values as managed by the deployment, with no fields to edit them

#### Scenario: Owner tries to override
- **WHEN** the config file sets a provider and an owner submits their own base URL and key
- **THEN** the request is refused and the deployment values remain in use

### Requirement: Each workspace opts in to the deployment default
A deployment default SHALL NOT send content for a workspace until an owner of that workspace enables it with consent and the connection test passes. Disconnecting SHALL stop model use for that workspace only.

#### Scenario: New workspace on a configured deployment
- **WHEN** the config file sets a provider and a workspace owner has not enabled it
- **THEN** the workspace's model connection reads "Not connected" and no model call is made for it

#### Scenario: Owner enables the default
- **WHEN** an owner enables the deployment default with consent and the test passes
- **THEN** the workspace's model connection is active

### Requirement: Private endpoints only from the config file
Only the deployment config file MAY name an HTTP base URL or a host with a private or local address. Requests to that base URL SHALL skip the public-address check.

#### Scenario: Local server in the config file
- **WHEN** the config file names `http://ollama:11434/v1` and an owner enables it
- **THEN** the connection test runs against that server

### Requirement: Invalid deployment config stops startup
When the config file exists and has an unknown API style, a missing field, an invalid base URL, or names a key variable that is unset or empty, every process SHALL fail at startup with a message that names the file and the problem. The message MUST NOT contain a key.

#### Scenario: Key variable unset
- **WHEN** the config file sets `api_key_env = "OPENAI_API_KEY"` and that variable is not set
- **THEN** startup fails with a message naming the file and `OPENAI_API_KEY`

#### Scenario: No config file
- **WHEN** no config file exists
- **THEN** startup succeeds and owners configure the provider in Settings

### Requirement: Key bound to its endpoint
API responses MUST NOT contain the key. An owner who changes the API style or base URL SHALL enter a new key. An owner who changes only the model MAY keep the stored key.

#### Scenario: Base URL changed without a key
- **WHEN** an owner changes the base URL of an active connection and leaves the key empty
- **THEN** the request is refused and the stored key is not sent anywhere

#### Scenario: Model changed without a key
- **WHEN** an owner changes only the model name and leaves the key empty
- **THEN** the connection test runs with the stored key and the new model

### Requirement: Model disconnect
Disconnecting the model provider SHALL delete the stored key and the workspace's consent, and set the connection to disconnected. Reports and other records MUST remain. Reconnecting SHALL require consent again.

#### Scenario: Owner disconnects
- **WHEN** an owner disconnects the model provider
- **THEN** no usable key remains for that workspace and the next model call is refused

### Requirement: Guarded model calls
Every model call SHALL first check that the workspace is not the demo workspace and has an active, consented model connection. A call that fails the check MUST NOT reach a provider.

#### Scenario: Demo workspace
- **WHEN** any feature asks for a model call in the demo workspace
- **THEN** the call is refused and no provider request is made

#### Scenario: Demo settings
- **WHEN** an owner of the demo workspace tries to connect a model provider
- **THEN** the request is refused with the demo reason

#### Scenario: No connection
- **WHEN** a feature asks for a model call in a workspace without an active model connection
- **THEN** the call is refused and no provider request is made

### Requirement: No model content or keys in logs
Logs and stored error records for model calls MUST NOT contain the key, the prompt, the response body, or report content. They SHALL record only a safe error category.

#### Scenario: Provider returns an error
- **WHEN** a model request fails with a provider error whose body echoes the prompt
- **THEN** the log and stored error code contain only the error category
