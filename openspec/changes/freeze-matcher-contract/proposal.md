# Proposal

## Why

Match suggestions need a fixed contract and labelled data before any ranker is built, so quality can be judged against gates set in advance. Delivers #22, the first of four matching issues (#22, #23, #24, #21).

## What Changes

- Version the JSON request/response contract between Django and the Rust ranker. Design: [ADR 0003](../../../docs/adr/0003-local-rust-matcher.md), slice 1.
- Specify normalization and tokenization with fixtures, and confirm the ten-candidate and 64 KiB limits.
- Generate practice and exam cases from known problems, so each case has its expected answer when written. Use a different model from the one that tunes the matcher.
- Add `task eval:label`: a terminal tool that shows a random sample of each batch for a quick right/wrong check.
- Record the PostgreSQL baselines.
- Record precision, coverage, sample-size, and spot-check sample gates before any exam run.

## Roles

- Agents: generate cases, build the tools, and later build and tune the matcher on practice cases only.
- Maintainer: sets the gates, spot-checks each batch, and signs off results.
- Exam cases stay in the repository. Agents must not tune against them.

## Capabilities

### New Capabilities
- `matching-evaluation`: the labelled dataset, how it is generated and checked, and the release gates that decide whether suggestions are shown

### Modified Capabilities

## Impact

New contract schema and fixtures under `rust/` or `backend/` test data; a stdlib-only Python labelling script and Task target; no runtime behaviour yet. No real customer data or provider credentials.
