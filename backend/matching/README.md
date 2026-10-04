# Matcher contract

Django sends one request to the Rust matcher and reads one response. Design: [ADR 0003](../../docs/adr/0003-local-rust-matcher.md).

| File | Authority for |
| --- | --- |
| `schemas/v1/request.schema.json`, `response.schema.json` | Document shape |
| `schemas/v1/examples.json` | Accepted and rejected documents, with the expected error category |
| `contract.py` | Rules a schema cannot state, listed below |
| `normalization.json` | Tokenizer output |
| `configs/<config_version>.json` | Weights, thresholds, and the linked-report cap. The Rust build embeds them; Python reads them for supported versions |

Rules outside the schemas:

- The request is compact UTF-8 JSON of at most 65,536 bytes. Over-limit input is rejected, never truncated.
- Algorithm and config versions must be supported by the caller's registry. Unknown versions fail closed.
- Candidate and linked report IDs are unique.
- A response repeats the request's versions. Suggestions are candidates, unique, ordered by score descending then problem ID ascending, and use known feature names. Evidence points to the suggested problem or its own linked reports.
- `no_candidates` is the abstain reason exactly when the pool is empty.
- The matcher exits nonzero with a `status: error` document when it rejects input.

## Runtime

- `retrieval.py`: up to ten open or in-progress problems from the report's workspace, by the baseline's PostgreSQL method. Each candidate carries its most recently created linked reports, up to the config's `max_linked_reports`. More is rejected by the matcher, never trimmed.
- `adapter.py`: runs `RESCRIBO_MATCHER_PATH` with an empty environment, `RESCRIBO_MATCHER_TIMEOUT_SECONDS`, and stdout capped at `RESCRIBO_MATCHER_MAX_RESPONSE_BYTES`. Stderr is discarded. Records the binary's SHA-256 with each run.
- `runs.py`: report creation and title or description edits queue a run in the same transaction. Retrieval, process, and timeout failures retry up to three attempts against the same snapshot. Contract and version failures do not retry. A changed report or candidate marks the run stale and queues a replacement.
- `decisions.py`: members accept or reject suggestions from the latest ranked run. Acceptance calls `link_report`.

`task matcher-build` builds the local binary; `task check-matcher test-matcher` runs the Rust checks.

## Tokenization

Applied to every title, description, and summary. The rules are written for Rust's standard library.

1. Lowercase with the Unicode default mapping (`str::to_lowercase`). No case folding: `ß` stays `ß`.
2. A token is a maximal run of characters where `char::is_alphanumeric` is true.
3. An apostrophe (U+0027 or U+2019) between two such characters is dropped and the run continues: `doesn't` gives `doesnt`.
4. A full stop between two ASCII digits is kept inside the token: `v2.4.1`, `3.5`.
5. Every other character separates tokens. No stemming, no stopwords, no length filter. Duplicates and order are kept.

No Unicode normalization form is applied, so a decomposed accent splits the word. Scripts written without spaces produce one token per run.

## Algorithms

- `lexical-1`: IDF-weighted overlap between the report's tokens and each candidate's title, summary, and linked reports.
- `lexical-2`: the same, but report clauses that say something works are left out. Clauses split at `.` before whitespace, `;`, `!`, `?`, line breaks, and the words `but` and `however`. A clause with `fine`, `fixed`, `resolved`, `works`, `worked`, `working`, `anymore`, or `no longer` is left out. Plain negation (`not`, `doesn't`) is kept, because reports use it to describe symptoms.

## Limits

Measured on `practice-20261004-c80b` (generated, 0 to 3 linked reports per problem):

- The largest report with the ten largest candidates serializes to 14,452 bytes, 22% of 64 KiB. The median request is about 10 KB. A candidate is at most 1.9 KB.
- 64 KiB therefore allows about 6 KB per candidate. #23 must cap linked reports per candidate, because real problems collect more than three.
- PostgreSQL recall@10 is 93.5%; every miss is a paraphrase. Batches hold 20 problems, so this overstates recall in larger workspaces. Recheck ten candidates with larger batches before enabling suggestions.
