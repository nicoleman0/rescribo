# Proposal

## Why

Match suggestions need a fixed contract and labelled data before any ranker is built, so quality can be judged against gates set in advance. Delivers #22, the first of four matching issues (#22, #23, #24, #21).

## What Changes

- Version the JSON request/response contract between Django and the Rust ranker. Design: [ADR 0003](../../../docs/adr/0003-local-rust-matcher.md), slice 1.
- Specify normalization and tokenization with fixtures, and confirm the ten-candidate and 64 KiB limits.
- Create labelled development and held-out cases and record the PostgreSQL baselines.
- Record precision, coverage, and sample-size gates before any held-out run. The product owner sets them in this issue.

## Capabilities

### New Capabilities
- `matching-evaluation`: the labelled dataset and the release gates that decide whether suggestions are shown

### Modified Capabilities

## Impact

New contract schema and fixtures under `rust/` or `backend/` test data; no runtime behaviour yet. No real customer data or provider credentials.
