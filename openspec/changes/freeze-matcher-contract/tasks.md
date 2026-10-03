# Tasks

## 1. Contract and fixtures

- [ ] 1.1 Define the versioned JSON request/response schema with typed evidence references and errors; validation rejects malformed input and unknown contract, algorithm, or config versions
- [ ] 1.2 Specify normalization and tokenization rules with fixtures
- [ ] 1.3 Confirm the ten-candidate and 64 KiB limits against realistic fixtures
- [ ] 1.4 Record the PostgreSQL retrieval and text-search ordering baselines

## 2. Generated cases

- [ ] 2.1 Define the case format: expected answer, batch, generator model, practice or exam
- [ ] 2.2 Write the generator prompts for matches, no-match, paraphrase, negation, confusable causes, missing context, and misleading versions
- [ ] 2.3 Generate the first practice and exam batches with a model other than the tuning agent's

## 3. Labelling tool

- [ ] 3.1 Add `task eval:label`: shows a random sample of a batch; `y`/`n` per case, `u` undo, `q` quit, resumable
- [ ] 3.2 Mark a batch usable only when its sample has no wrong answers
- [ ] 3.3 Maintainer spot-checks the first batches

## 4. Gates

- [ ] 4.1 Maintainer records precision, coverage, minimum sample size, and spot-check sample size before any exam run

## 5. Checks

- [ ] 5.1 Run `task check test build schema-check`
