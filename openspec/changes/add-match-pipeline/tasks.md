# Tasks

## 1. Ranker

- [ ] 1.1 Build the deterministic `matcher` crate with abstention and evidence references
- [ ] 1.2 Build the binary into dev and production images at a fixed configured path

## 2. Adapter and persistence

- [ ] 2.1 Add the Python adapter with strict validation, timeout, and typed failures
- [ ] 2.2 Add workspace-scoped run and suggestion models with migrations
- [ ] 2.3 Queue runs on commit after report creation or relevant edits, with stale checks and bounded retry
- [ ] 2.4 Add authenticated retry, accept, and reject endpoints; regenerate contracts

## 3. Checks

- [ ] 3.1 Run `task check test build schema-check`, `task worker-check`, and the Rust CI checks
