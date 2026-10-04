# Tasks

## 1. Ranker

- [x] 1.1 Build the deterministic `matcher` crate with abstention and evidence references
- [x] 1.2 Build the binary into the dev image at a fixed configured path (no production image exists yet; it follows the deployment work)

## 2. Adapter and persistence

- [x] 2.1 Add the Python adapter with strict validation, timeout, and typed failures
- [x] 2.2 Add workspace-scoped run and suggestion models with migrations
- [x] 2.3 Queue runs on commit after report creation or relevant edits, with stale checks and bounded retry
- [x] 2.4 Add authenticated retry, accept, and reject endpoints; regenerate contracts

## 3. Checks

- [x] 3.1 Run `task check test build schema-check`, `task worker-check`, and the Rust CI checks
