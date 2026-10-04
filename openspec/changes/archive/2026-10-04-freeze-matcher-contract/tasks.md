# Tasks

## 1. Contract and fixtures

- [x] 1.1 Define the versioned JSON request/response schema with typed evidence references and errors; validation rejects malformed input and unknown contract, algorithm, or config versions
- [x] 1.2 Specify normalization and tokenization rules with fixtures
- [x] 1.3 Confirm the ten-candidate and 64 KiB limits against realistic fixtures
- [x] 1.4 Record the PostgreSQL retrieval and text-search ordering baselines

## 2. Generated cases

- [x] 2.1 Define the case format: expected answer, batch, generator model, practice or exam
- [x] 2.2 Write the generator prompts for matches, no-match, paraphrase, negation, confusable causes, missing context, and misleading versions
- [x] 2.3 Generate the first practice and exam batches with a model other than the tuning agent's

## 3. Labelling tool

- [x] 3.1 Add `task eval:label`: shows a random sample of a batch; `y`/`n` per case, `u` undo, `q` quit, resumable
- [x] 3.2 Mark a batch usable only when its sample has no wrong answers
- [x] 3.3 Add `task eval:review-model`: a reviewer model checks a batch's sample and records its verdicts and reasons
- [x] 3.4 Spot-check the first batches, by the maintainer or a reviewer model

## 4. Gates

- [x] 4.1 Maintainer records precision, coverage, minimum sample size, and spot-check sample size before any exam run

## 5. Checks

- [x] 5.1 Run `task check test build schema-check`
