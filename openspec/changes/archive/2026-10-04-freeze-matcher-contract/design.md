# Design

## Context

ADR 0003 fixes the subprocess boundary, the request/response fields, the error categories, and the ten-candidate and 64 KiB limits. The Rust crate and the Django adapter come in #23. This change freezes what both sides build against, and the data that judges the result.

## Goals / Non-Goals

**Goals:**
- One authoritative description of contract v1 that Rust and Python both read.
- Normalization and tokenization rules both sides can implement with their standard libraries.
- A case and review format that later evaluation scripts read without guessing.

**Non-Goals:**
- Any ranking, retrieval code in the product, persistence, or Celery wiring (#23).
- Choosing feature names, weights, or thresholds (#23 and #24).

## Decisions

### Contract lives in JSON Schema under `backend/matching/schemas/v1/`
`request.schema.json` and `response.schema.json` (draft 2020-12) are the authority. Python validates them with `jsonschema`. The Rust crate tests against the same files and fixtures. Rules JSON Schema cannot state go in `backend/matching/contract.py`: the 64 KiB byte limit, version support, unique IDs, and a response checked against its exact request (membership, rank order, evidence references).

Alternative: typed Python dataclasses with a Markdown description for Rust. Rejected because the shape would live in two places.

### Supported versions are passed in, not hard-coded
The schema fixes `contract_version` to `"1"`. Algorithm and config versions, and their feature names, are a `SupportedAlgorithms` value the caller passes to validation. #23 decides where that comes from, such as the versioned config files. Hard-coding algorithm names now would commit #23 to them, and tuning adds config versions often.

### Tokenization uses standard-library character classes only
Text is lowercased, then split into runs of `char::is_alphanumeric` characters, the Unicode Alphabetic or Numeric property. Two joins keep meaning lexical features need: apostrophes inside a word (`doesn't` → `doesnt`, keeping negation visible) and a dot between digits (`2.4.1`). There is no Unicode normalization form, because Rust's standard library has none and the ADR prefers no dependency. The rules are written in `backend/matching/README.md`; the fixtures in `backend/matching/normalization.json` are the authority. A test oracle in Python checks that the fixtures agree with the written rules.

### Each batch is one synthetic workspace
`eval/matching/batches/<batch_id>/batch.json` holds the batch's problems (with linked reports) and its cases. Labels come from how a case was generated:
- Cases about a listed problem expect that problem.
- `no_match` and `negation` cases expect none.
- A no-match case is written about a problem the generator made and then dropped from the list.

Keeping each batch self-contained means retrieval runs over a realistic problem list with confusable neighbours.

### Review state is a separate file
`review.json` beside the batch records the seed, the sampled case IDs, the sample size, and the verdicts. Usability is derived: the sample is complete, its size meets the gate, and nothing is marked wrong. Regenerating a batch creates a new batch ID, so a stale review can never apply to new data.

### A reviewer model can stand in for the person
`task eval:review-model` sends each sampled case, rendered as the person sees it plus every problem summary, to an OpenRouter model. The model returns right or wrong with a reason. Verdicts share `review.json` with human verdicts and record their reviewer, so a person can finish or overrule a model review. The script prints case IDs and counts only, so an agent can run it on an exam batch without reading exam text. The tool refuses Claude, Jev, and the batch's generator.

Alternative: a separate review file per reviewer. Rejected because usability would then depend on combining files.

### Gates and spot-check size live in `eval/matching/gates.json`
The labelling tool reads the spot-check sample size from this file and refuses to run while it is unset. This keeps one value in one place and makes the maintainer set it first.

### Generation runs through OpenRouter with a stdlib script
`scripts/eval_generate.py` calls the OpenRouter chat API with `urllib`. The model is a required argument, recorded per batch. It must not be a Claude model, which is the tuning agent, or Jev, the baseline. The script refuses either.

## Risks / Trade-offs

- [No Unicode normalization: decomposed accents tokenize differently from composed ones] → Slack sends NFC text. A fixture records the behaviour so it is not a surprise.
- [Synthetic language from one model is narrower than real reports] → Batches record the model. Later exam batches can use a different generator. The ADR's open redacted-data decision is unchanged.
- [A reviewer model from the generator's vendor may share its blind spots] → Prefer a reviewer from another vendor. The reviewer is recorded per verdict.
- [Agents can read exam files in the repository] → The rule is in AGENTS.md and the evaluation README. Exam batches are named by split so tuning scripts can refuse them.
