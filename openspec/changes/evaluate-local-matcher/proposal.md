# Proposal

## Why

The ranker from #23 must be measured on held-out data against the gates from #22 before suggestions are shown. Delivers #24. Requires `freeze-matcher-contract` and `add-match-pipeline` to be archived first.

## What Changes

- Tune weights and thresholds on development data only, then freeze the configuration.
- Run the held-out evaluation and publish retrieval and ranking results separately, with limitations.
- Record whether the gates pass. Lexical ranking can miss paraphrases and negation; if gates fail, suggestions stay disabled.

## Capabilities

### New Capabilities

### Modified Capabilities
- `matching-evaluation`: adds separate retrieval/ranking reporting and the rule against unsupported quality claims

## Impact

Evaluation script and report under `docs/`; the suggestions feature flag.
