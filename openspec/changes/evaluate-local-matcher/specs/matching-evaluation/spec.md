# Spec Delta

## ADDED Requirements

### Requirement: Retrieval and ranking reported separately
The evaluation SHALL report candidate recall@10 and gold matches omitted by retrieval separately from ranking. Ranking is compared with PostgreSQL text-search order on the same candidate pool, reporting top-1 precision, top-3 recall, coverage, abstention, false suggestions on no-match cases, and evidence validity.

#### Scenario: Retrieval miss
- **WHEN** a gold match was not retrieved
- **THEN** it counts as a retrieval miss, not a ranking failure

### Requirement: No unsupported quality claims
Results SHALL state sample sizes, test conditions, and limitations. The project MUST NOT claim matching quality if the gates are not met.

#### Scenario: Gates missed
- **WHEN** the held-out result misses a gate
- **THEN** the report says so and suggestions stay disabled

### Requirement: Automatic failure triage
Each failed exam case SHALL be classified automatically as a retrieval miss, ranking miss, false suggestion, or wrong abstention. A suggested pattern tag, such as paraphrase or negation, SHALL be proposed by a model and confirmed or corrected by a person.

#### Scenario: Right problem never retrieved
- **WHEN** the expected problem is absent from the candidate pool
- **THEN** the case is tagged as a retrieval miss before any human review

### Requirement: Spent exams rotate
Once exam results are used to decide what to fix, those cases SHALL move to the practice set. A fresh exam batch MUST be generated and spot-checked before the next exam result counts.

#### Scenario: Retest after a fix
- **WHEN** the matcher is changed after reviewing exam failures
- **THEN** the next score comes from a new exam batch, not the reviewed one
