# Spec Delta

## Purpose

Suggests existing problems that a new or edited report may belong to, with evidence, and leaves the decision to a member.

## ADDED Requirements

### Requirement: Same-workspace retrieval
The system SHALL retrieve at most ten open problems from the report's workspace using PostgreSQL text search over problem titles, summaries, and linked report descriptions.

#### Scenario: Similar problem in another workspace
- **WHEN** only another workspace has a problem matching the report
- **THEN** that problem is never retrieved, ranked, or counted

### Requirement: Isolated deterministic ranking
Ranking SHALL run in a local executable with no database, network, or credential access. The same input, algorithm, configuration, and build MUST produce identical ordered output.

#### Scenario: Replay
- **WHEN** a stored run's input is ranked again with the same versions
- **THEN** the ordered suggestions and scores are identical

### Requirement: Validated response
The system SHALL accept a ranking response only if every problem and evidence reference belongs to the exact candidate set supplied, versions match, and scores are finite and non-negative. At most three suggestions are kept.

#### Scenario: Unknown problem ID in response
- **WHEN** the executable returns a problem ID that was not supplied
- **THEN** the run fails as invalid output and no suggestion is saved

### Requirement: Explicit abstention
The ranker SHALL abstain when no candidate clears the evaluated threshold, the top candidates are too close, or there are no candidates. Scores MUST NOT be shown as probabilities or confidence.

#### Scenario: Empty candidate set
- **WHEN** retrieval finds no candidates
- **THEN** the run completes as abstained with no suggestions

### Requirement: Capture independent of matching
Matching SHALL run asynchronously after report creation or a matching-relevant edit. Queue, retrieval, executable, timeout, or contract failure MUST leave the report committed and manual search and grouping available.

#### Scenario: Executable missing
- **WHEN** the matcher binary cannot be started
- **THEN** the report exists, the run records an executable failure, and the inbox shows suggestions as unavailable

### Requirement: Distinct failure categories
Runs SHALL record retrieval failure, executable failure, invalid contract output, timeout, and stale input as separate categories. Transient failures retry with a bound; validation failures do not retry.

#### Scenario: Malformed output
- **WHEN** the executable returns invalid JSON
- **THEN** the run fails as invalid output and is not retried automatically

### Requirement: Stale results discarded
The system SHALL snapshot report and candidate versions at retrieval and recheck them, with workspace ownership, before ranking and before saving. Changed inputs mark the run stale and enqueue a fresh run if the report is still eligible.

#### Scenario: Report edited during ranking
- **WHEN** the report changes between retrieval and save
- **THEN** the result is marked stale, not shown, and a new run is queued

### Requirement: Human decision
A member SHALL accept or reject each suggestion. Acceptance MUST call the normal version-checked report-linking use case. Matching MUST NOT link, dismiss, or change a problem.

#### Scenario: Accept suggestion
- **WHEN** a member accepts a suggestion
- **THEN** the report is linked through the normal linking rules and the suggestion records the decision

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
