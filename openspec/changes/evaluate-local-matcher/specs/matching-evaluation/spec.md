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
