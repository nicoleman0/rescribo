# Proposal

## Why

The ranker from #23 must be measured on held-out data against the gates from #22 before suggestions are shown. Delivers #24. Requires `freeze-matcher-contract` and `add-match-pipeline` to be archived first.

## What Changes

- Tune weights and thresholds on development data only, then freeze the configuration.
- Run the held-out evaluation and publish retrieval and ranking results separately, with limitations.
- Record whether the gates pass. Lexical ranking can miss paraphrases and negation; if gates fail, suggestions stay disabled.
- Compare against a hosted baseline: TypeSafe's Jev (`typesafe/jev-1.13`, pinned; not `~typesafe/jev-latest`) through OpenRouter. Jev answers typed Choice questions with a probability per option, so each exam case becomes one Choice over its candidates plus "none". This shows how much a model-based matcher would gain over lexical ranking. It runs in evaluation tooling only and is never shipped; ADR 0003's local-only product decision stands.
- Add `task eval:review`: shows exam failures already sorted into retrieval miss, ranking miss, false suggestion, or wrong abstention.
- Rotate spent exams by hand: reviewed exam cases move to practice, and a fresh exam batch is generated and spot-checked before the next result counts. Automate rotation only if it repeats.

Not in scope: using real link decisions from the app as labels. That needs the redacted-data decision left open in ADR 0003.

## Capabilities

### New Capabilities

### Modified Capabilities
- `matching-evaluation`: adds separate retrieval/ranking reporting, failure triage, exam rotation, the hosted baseline, and the rule against unsupported quality claims

## Impact

Evaluation script, review tool, and report under `docs/`; the suggestions feature flag. The baseline needs an `OPENROUTER_API_KEY` in `.env` and costs $0.042 per million input tokens (output is free). Jev's Decisions API is marked alpha and documents no seed or temperature control, so the adapter stays in evaluation code and repeat runs are compared.
