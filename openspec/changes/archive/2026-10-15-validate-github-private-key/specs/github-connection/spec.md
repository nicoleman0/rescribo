# Spec Delta

## ADDED Requirements

### Requirement: GitHub App private key setting
The operator SHALL be able to set the GitHub App private key as PEM text with real newlines, or as one line with a literal `\n` between PEM lines. An empty or whitespace-only value SHALL mean the GitHub App is not configured. A set value that is not an unencrypted RSA private key in PEM format MUST stop every application process at startup with a message that names the setting and the accepted forms. The message MUST NOT contain the key.

#### Scenario: Multi-line key
- **WHEN** the process environment holds the key as PEM text with real newlines
- **THEN** the application starts and signs GitHub App requests with that key

#### Scenario: One-line key in an env file
- **WHEN** the env file sets the key on one line with `\n` between the PEM lines, unquoted, single-quoted, or double-quoted
- **THEN** the application starts and signs GitHub App requests with that key

#### Scenario: Key not set
- **WHEN** the key is empty
- **THEN** the application starts and GitHub setup asks the operator to configure the GitHub App

#### Scenario: Key that cannot be parsed
- **WHEN** the key is set but is truncated, encrypted, not RSA, or not PEM
- **THEN** the API, worker, and scheduler fail at startup with a message that names `RESCRIBO_GITHUB_PRIVATE_KEY` and the accepted forms, and the message does not contain the key
