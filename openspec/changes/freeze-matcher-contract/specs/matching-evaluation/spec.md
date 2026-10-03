# Spec Delta

## Purpose

Decides with labelled data whether match suggestions are good enough to show, and reports retrieval and ranking quality separately.

## ADDED Requirements

### Requirement: Versioned labelled dataset
The repository SHALL hold a versioned labelled dataset split into development and held-out cases. It covers genuine matches, no-match reports, paraphrases, negation, similar wording with different causes, missing context, misleading version details, and realistic lengths. Synthetic and redacted real data stay distinct.

#### Scenario: Case counts
- **WHEN** the evaluation report is generated
- **THEN** case counts and class balance are derived from the fixtures, not hard-coded

### Requirement: Gates declared before held-out results
Precision, coverage, and minimum sample size gates SHALL be recorded before held-out results are inspected. Zero invalid references, zero cross-workspace references, and deterministic replay are always required.

#### Scenario: Tuning
- **WHEN** weights or thresholds are tuned
- **THEN** only development cases are used, and the configuration is frozen before held-out evaluation
