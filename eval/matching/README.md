# Matching evaluation data

Synthetic cases that decide whether match suggestions are shown. Requirements: `openspec/specs/matching-evaluation/`. Code: `scripts/eval_cases.py`.

## Rules

- Agents tune the matcher on `practice` batches only. Do not open, score, or summarize `exam` batches while choosing features, weights, or thresholds.
- A batch is used only once its spot-check sample is complete with no wrong answers. A person reviews with `task eval:label`; a reviewer model with `task eval:review-model -- <batch_id> --model <id>`.
- The maintainer fills in `gates.json` before any exam run, and `spot_check_sample_size` before the first review.
- Generators and reviewer models must not be the tuning agent's model (Claude) or the evaluation baseline (Jev), and a reviewer must not be the batch's generator. The tools refuse them.

## Scoring

- `task eval:matcher -- <batch_id>... --config <version>`: the release binary against PostgreSQL order on the same pools, with gates. An exam scores once per config. `--sweep` tunes on practice batches.
- `task eval:jev -- <batch_id>... --run 1|2 --yes`: the Jev baseline. Paid; without `--yes` it prints the estimate.
- `task eval:review -- <result file>`: triaged failures, then a sample of passes.
- Latest report: `docs/MATCHING_EVALUATION.md`.

## Layout

```text
gates.json                    Gates and spot-check sample size, set by the maintainer
prompts/                      Generator prompts; their hash is the batch's prompt_version
reviewer/prompt.md            Reviewer model prompt
batches/<batch_id>/batch.json One synthetic workspace: problems and cases
batches/<batch_id>/review.json Spot-check seed, batch hash, and verdicts
results/                      Recorded metrics (`task eval:baseline`, `eval:matcher`, `eval:jev`)
```

## Batch format

```json
{
  "batch_id": "practice-20261003-a1b2",
  "split": "practice",
  "data_source": "synthetic",
  "generator": {"provider": "openrouter", "model": "...", "prompt_version": "...", "created_at": "..."},
  "problems": [
    {"id": "<uuid>", "title": "...", "summary": "...", "confusable_with": "<uuid or null>",
     "linked_reports": [{"id": "<uuid>", "title": "...", "description": "..."}]}
  ],
  "cases": [
    {"id": "<uuid>", "kind": "paraphrase", "report": {"title": "...", "description": "..."},
     "source_problem_id": "<uuid>", "expected_problem_id": "<uuid>"}
  ]
}
```

The expected answer follows from how a case was generated:

| Kind | Written about | Expected |
| --- | --- | --- |
| `match` | A listed problem, plainly | That problem |
| `paraphrase` | A listed problem, avoiding its wording | That problem |
| `confusable` | A listed problem, worded like its confusable sibling | That problem |
| `missing_context` | A listed problem, short and vague | That problem |
| `misleading_version` | A listed problem, citing an unrelated version | That problem |
| `negation` | A listed problem's symptom, said not to occur | No match |
| `no_match` | A problem left out of the list (`unlisted_problem`: title, summary) | No match |

Editing a reviewed `batch.json` makes its review stale, and the batch needs a new sample.
