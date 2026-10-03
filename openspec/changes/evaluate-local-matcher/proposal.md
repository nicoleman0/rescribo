# Proposal

## Why

The ranker from #23 must be measured on held-out data against the gates from #22 before suggestions are shown. Delivers #24. Requires `freeze-matcher-contract` and `add-match-pipeline` to be archived first.

## What Changes

- Tune weights and thresholds on development data only, then freeze the configuration.
- Run the held-out evaluation and publish retrieval and ranking results separately, with limitations.
- Record whether the gates pass. Lexical ranking can miss paraphrases and negation; if gates fail, suggestions stay disabled.
- Add `task eval:review`: shows exam failures already sorted into retrieval miss, ranking miss, false suggestion, or wrong abstention, with a model-suggested pattern tag for the maintainer to confirm.
- Rotate spent exams: reviewed exam cases move to practice, and a fresh exam batch is generated and spot-checked before the next result counts.

Not in scope: using real link decisions from the app as labels. That needs the redacted-data decision left open in ADR 0003.

## Capabilities

### New Capabilities

### Modified Capabilities
- `matching-evaluation`: adds separate retrieval/ranking reporting, failure triage, exam rotation, and the rule against unsupported quality claims

## Impact

Evaluation script, review tool, and report under `docs/`; the suggestions feature flag.
