# Tasks

## 1. Evaluation

- [ ] 1.1 Tune weights and thresholds on development data, then freeze the configuration
- [ ] 1.2 Run the held-out evaluation and publish the report with sample sizes and limitations
- [ ] 1.3 Check deterministic replay and zero invalid or cross-workspace references
- [ ] 1.4 Record whether the gates pass and set the suggestions flag accordingly

## 2. Hosted baseline

- [ ] 2.1 Confirm the current Jev version and Decisions API request format before building
- [ ] 2.2 Add an evaluation-only adapter that asks Jev one Choice question per exam case over its candidates plus "none"
- [ ] 2.3 Run the baseline twice and record agreement between runs, model version, and cost
- [ ] 2.4 Add Jev's metrics beside Rust and PostgreSQL in the report

## 3. Review and rotation

- [ ] 3.1 Classify each failed exam case automatically by failure kind
- [ ] 3.2 Add `task eval:review` to step through failures and a sample of passes

## 4. Checks

- [ ] 4.1 Run `task check test build schema-check` and the Rust CI checks
