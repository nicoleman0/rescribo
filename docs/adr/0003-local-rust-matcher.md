# ADR 0003: Local Rust report matcher

Status: accepted design; implementation not started.

## Decision

Django owns authentication, workspace isolation, PostgreSQL retrieval, persistence, task lifecycle, and the human approval workflow. A Rust executable scores only the candidate set Django supplies. It has no database access, network access, credentials, or authority to link records. PostgreSQL text search remains the initial retrieval method. No hosted AI provider or embedding model is an initial dependency.

Use a subprocess with a versioned JSON request/response contract, invoked by a thin Python adapter from the existing Celery worker. A Python extension could avoid process startup and provide in-process calls, but adds native wheel and Python ABI packaging to every supported deployment environment. The subprocess keeps a language-neutral contract and independent crash/timeout boundary; one short-lived process per job is the simplest production-suitable initial path. Measure process overhead before considering a persistent worker or extension.

## Contract and validation

- Request fields: `contract_version`, `algorithm_version`, `config_version`, `report` (`id`, `version`, title and description), and ordered `candidates` (problem `id`, `version`, title, summary, and bounded linked-report text with typed source IDs and field names).
- Response fields: matching contract and algorithm versions, `status` (`ranked` or `abstain`), ordered suggestions (problem ID, raw score, feature breakdown, evidence references), and a stable abstention reason when applicable. No free-form generated explanation and no probability field.
- JSON is UTF-8 on stdin/stdout. Stdout contains exactly one JSON document; diagnostics go to stderr. Python launches an absolute configured executable path with an argument array, never a shell command. It captures output and enforces a timeout.
- Initial limit: ten candidates and a 64 KiB serialized request. This is a design limit to be validated against realistic fixtures before implementation. Reject over-limit input; do not silently truncate report text. Bound response bytes as well. The exact response cap and execution timeout are implementation parameters to set from tests and deployment measurements before enabling the feature.
- Python validates schema, contract/algorithm versions, candidate membership, unique IDs, finite non-negative scores, rank order, allowed feature names, and evidence references against the exact request. Rust independently validates required fields, duplicate IDs, text limits, and supported versions. Unknown versions fail closed.
- Stable deterministic order is score descending then problem UUID ascending. The Rust ranker returns at most three suggestions. It abstains on an empty candidate set or when its versioned threshold/margin rule rejects the result.
- Errors are typed: retrieval failure (Python/PostgreSQL), invalid request, unsupported contract/config, executable missing, nonzero exit/crash, timeout, malformed/oversized response, and stale snapshot. Logs contain IDs only where operationally necessary, versions, status, duration, and error category; never text, payloads, customer data, or raw stderr. Limit stderr capture and redact before logging.

The score is a deterministic ranking signal, not a calibrated probability. Initial lexical features may include normalized token overlap by source field, exact phrase overlap, and shared informative terms. Feature weights and abstention thresholds are versioned data, learned/tuned on development cases only, and frozen for held-out evaluation. Normalization and tokenization rules must be specified and covered by fixtures. Evidence references point to a supplied record ID and field; Python validates them and renders the short explanation. Similar vocabulary can hide different causes; paraphrases and negation can defeat lexical features. Human review remains required.

## Execution and state

Create the run/outbox row in the same transaction as eligible report creation or edit, then dispatch through Celery after commit. Capture success is independent of queue and matcher success. A recovery task finds undispatched pending rows; matcher failures leave manual triage available. Retry bounded transient process/worker failures, not malformed contracts or unsupported versions.

The immutable input snapshot records report and candidate versions and the ordered IDs. Check report eligibility and versions before invocation and recheck report/candidate workspace and versions under transaction before saving. Mark stale results without showing suggestions; enqueue a replacement for still-eligible reports. Retry a run only against its unchanged snapshot. On human acceptance, use the normal version-checked report linking use case.

Run and suggestion data are workspace-scoped. Persist algorithm/configuration and contract versions, snapshot versions, outcome/failure class, separate retrieval/ranking duration, retry count, and decision outcome. Reproducibility requires the same validated input, algorithm/configuration versions, and executable build to produce byte-equivalent ordered suggestions. Record the binary build/release identifier with the run. Avoid storing duplicated report text in run records.

## Crate and delivery

Start with one `matcher` binary crate under `rust/`, with pure scoring/normalization modules and a small stdin/stdout adapter. Keep integration-specific orchestration in Python; do not add a Rust service or extra crate until an independent need appears. Prefer the Rust standard library. Add a dependency only for a concrete contract or correctness need, pin it in `Cargo.lock`, review maintenance/security status, and document why it cannot reasonably be handled in the standard library. No network-capable runtime dependencies.

Declare the supported stable toolchain through `rust-toolchain.toml`; set and test the crate `rust-version` (MSRV) explicitly once the selected CI/deployment image is known. Commit `Cargo.lock`. Build a release binary in a multi-stage backend image and copy it into the runtime image at a fixed path configured for the adapter. Local development may build through a Task target; production must run the built artifact and must not compile on task startup. Keep Python's uv lock and frontend npm lock independent. Rust installation, CI action, and container toolchain versions remain to be selected during the first implementation slice; this design does not assert a specific current version.

CI adds formatting, clippy with warnings denied, Rust unit tests, JSON contract tests, deterministic replay tests, and a backend integration check that invokes the built binary. Build the same target architecture used by deployment; if multi-architecture deployment is selected, build/test each target. Pin the Rust toolchain/action and container base versions under the repository's existing update process. Rust version compatibility claims belong to the selected toolchain and `rust-version`, not a vague "latest stable" promise. Cargo's manifest documents the `rust-version` field and workspace lock behavior; see [Cargo manifest reference](https://doc.rust-lang.org/cargo/reference/manifest.html) and [Cargo workspaces](https://doc.rust-lang.org/cargo/reference/workspaces.html).

Python's standard `subprocess.run` supports argument arrays, stdin input, captured output, return-code checks, and timeout handling, which covers this boundary without an extra Python package ([Python subprocess documentation](https://docs.python.org/3/library/subprocess.html)). A PyO3 extension is viable if process overhead later proves material, but its own build/distribution path is an added operational cost ([PyO3 build and distribution guide](https://pyo3.rs/latest/building-and-distribution.html)).

## Evaluation and implementation slices

Compare two stages separately:

1. Retrieval: candidate recall@k and fraction of labelled matches omitted by PostgreSQL.
2. Ranking: on the same retrieved candidate pool, top-1 precision, top-3 recall, suggestion coverage, abstention, false suggestion rate on no-match cases, and valid evidence-reference rate. Include PostgreSQL's native order as the baseline.

Use development data for feature/threshold selection and a held-out set for the release decision. Report counts, class balance, confidence intervals, coverage, and failure cases. Define acceptable precision/coverage and minimum sample size with product owners before opening held-out results; do not substitute an arbitrary number. Required gates: no cross-workspace references, no invalid output references, deterministic replay, no report-capture regression on task/executable failure, and measured improvement sufficient for the predeclared product gate. Otherwise keep suggestions disabled and manual search available. Do not claim better quality, speed, or security from Rust alone.

Dependency-ordered slices:

1. Freeze contract and evaluation set: define JSON schema, normalization fixtures, labelled development/held-out split, PostgreSQL baseline, and predeclared decision gates. Acceptance: schema validation rejects malformed/unknown versions; fixture labels and source provenance are reviewable; evaluation can report retrieval separately from ranking.
2. Build standalone deterministic crate: implement normalization, feature extraction, scoring, tie-breaking, abstention, evidence IDs, and versioned config. Acceptance: unit/property-style edge cases cover empty text, Unicode, duplicates, negation wording, versions, similar distinct problems, and repeatable output; no network dependencies.
3. Package and adapter: build binary into local/dev and production images; add strict Python contract validation, bounded subprocess invocation, error mapping, and structured safe metrics. Acceptance: real binary contract check passes; missing/crashing/timed-out binary and invalid output become typed failures; report capture remains committed.
4. Persist and schedule: add workspace-scoped run/suggestion persistence, on-commit queue dispatch, stale checks, bounded retry and recovery. Acceptance: workspace isolation, duplicate dispatch, stale report/candidate changes, worker outage, and retry cases pass against PostgreSQL/Redis.
5. Evaluate and expose advisory workflow: compare held-out results with PostgreSQL ordering, add authenticated retry/accept/reject using normal linking. Acceptance: predeclared gates pass, all references and versions revalidated, human action required, and UI presents scores as relative rank evidence rather than confidence.

## Open decisions

- Product owner must set precision/coverage tradeoff and minimum evaluation sample size before held-out evaluation.
- Select the deployment OS/CPU targets and supported Rust MSRV when the deployment base image is chosen.
- Confirm 64 KiB input and ten-candidate limits against realistic report/candidate data before crate implementation.
- Decide whether evaluation may include redacted production reports, subject to retention and consent policy; synthetic-only evaluation may not represent real language variation.

## GitHub issue alignment

Checked 27 September 2026. The matching/settings issues below are open in Milestone 2 or 4. Their descriptions still specify Jev/OpenRouter or paid AI. This design change does not edit them. Update their titles, scope, acceptance criteria, and dependencies before implementation:

- [#16: settings for members, connections, channels, AI, and deletion](https://github.com/nicoleman0/rescribo/issues/16) should remove AI enablement and provider-disclosure requirements. Keep membership, connection, channel, disconnect, and deletion controls.

- [#22: live Jev/OpenRouter contract check](https://github.com/nicoleman0/rescribo/issues/22) is superseded. Replace it with slice 1, freezing the local JSON contract, fixture set, normalization rules, and evaluation gates. There is no live provider check.
- [#23: PostgreSQL retrieval and Jev pipeline](https://github.com/nicoleman0/rescribo/issues/23) maps to slices 2–4: deterministic Rust crate, subprocess adapter, then workspace-scoped async persistence and stale-run handling. Keep retrieval in PostgreSQL/Django; remove Choice/Noul and provider-failure criteria.
- [#24: Jev evaluation](https://github.com/nicoleman0/rescribo/issues/24) maps to slice 1 and the held-out gate after slice 2. Keep retrieval recall and same-pool ranking metrics, but replace injected-instruction/model/cost metrics and the fixed 90%/30-suggestion bar with predeclared product gates.
- [#21: AI suggestion review interface](https://github.com/nicoleman0/rescribo/issues/21) maps to slice 5 after the contract and persistence work. Keep pending, unavailable, stale, abstained, and completed states; human accept/reject and manual search. Remove Choice/Noul display requirements.
- [#25: seeded demo and portfolio evidence](https://github.com/nicoleman0/rescribo/issues/25) should replace the paid-AI demo restriction with the local matcher behavior selected for demo. Keep real integration setup and outbound actions disabled by default.

The first implementation issue should be slice 1. Preserve the existing domain/workspace foundation prerequisite for #23. Confirm exact issue dependency links and milestone order with maintainers when updating GitHub issues.
