# Tasks

## 1. Contract and fixtures (#22, ADR 0003 slice 1)

- [ ] 1.1 Define the versioned JSON request/response schema with typed evidence references and errors
- [ ] 1.2 Specify normalization and tokenization rules with fixtures
- [ ] 1.3 Confirm the ten-candidate and 64 KiB limits against realistic fixtures
- [ ] 1.4 Create labelled development and held-out cases with reviewable provenance
- [ ] 1.5 Record the PostgreSQL retrieval and text-search ordering baselines
- [ ] 1.6 Record product gates and minimum sample size before any held-out run

## 2. Ranker, adapter, and persistence (#23, slices 2 to 4)

- [ ] 2.1 Build the deterministic `matcher` crate with abstention and evidence references
- [ ] 2.2 Build the binary into dev and production images at a fixed configured path
- [ ] 2.3 Add the Python adapter with strict validation, timeout, and typed failures
- [ ] 2.4 Add workspace-scoped run and suggestion models with migrations
- [ ] 2.5 Queue runs on commit after report creation or relevant edits, with stale checks and bounded retry
- [ ] 2.6 Add authenticated retry, accept, and reject endpoints; regenerate contracts

## 3. Held-out evaluation (#24)

- [ ] 3.1 Tune weights and thresholds on development data, then freeze the configuration
- [ ] 3.2 Run the held-out evaluation and publish the report with limitations
- [ ] 3.3 Record whether the gates pass and set the suggestions flag accordingly

## 4. Review interface (#21, slice 5)

- [ ] 4.1 Show matching states, up to three suggestions, and source evidence in the inbox
- [ ] 4.2 Wire accept, reject, and retry actions; keep manual search available in every state
- [ ] 4.3 Hide suggestions while the evaluation gate is unmet

## 5. Checks

- [ ] 5.1 Run `task check test build schema-check`, `task e2e`, `task worker-check`, and the Rust CI checks
