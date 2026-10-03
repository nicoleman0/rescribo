# Spec Delta

## ADDED Requirements

### Requirement: Suggestion review interface
The inbox SHALL show pending, unavailable, stale, abstained, and completed states, up to three suggestions with source evidence, and separate accept, reject, and retry actions. Only the latest completed non-stale result is shown.

#### Scenario: Retry after failure
- **WHEN** a member presses retry on a failed run
- **THEN** a new run is queued and the report stays usable

### Requirement: Suggestions gated by evaluation
Suggestions SHALL stay hidden until the matching evaluation passes its predeclared gates.

#### Scenario: Gates not met
- **WHEN** the held-out evaluation misses a gate
- **THEN** no suggestions are shown and manual search remains available
