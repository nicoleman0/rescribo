# Spec Delta

## ADDED Requirements

### Requirement: Suggestions off until gates pass
Match suggestions SHALL be shown only when the `RESCRIBO_MATCH_SUGGESTIONS_ENABLED` setting is on, and it MUST stay off until a frozen configuration passes the matching gates on an exam. While off, match runs still execute, the match read returns no run and says suggestions are off, and retry, accept, and reject are refused as not found. Workspace access checks apply either way.

#### Scenario: Suggestions off
- **WHEN** a member reads a report's match while the setting is off
- **THEN** the response says suggestions are off and contains no run or suggestion

#### Scenario: Decision while off
- **WHEN** a member accepts, rejects, or retries while the setting is off
- **THEN** the request is refused as not found and nothing is linked or recorded
