# Tasks

## 1. Evaluation

- [x] 1.1 Tune weights and thresholds on development data, then freeze the configuration
- [x] 1.2 Run the held-out evaluation and publish the report with sample sizes and limitations
- [x] 1.3 Check deterministic replay and zero invalid or cross-workspace references
- [x] 1.4 Record whether the gates pass and set the suggestions flag accordingly

## 2. Hosted baseline

- [x] 2.1 Confirm the current Jev version and Decisions API request format before building
- [x] 2.2 Add an evaluation-only adapter that asks Jev one Choice question per exam case over its candidates plus "none"
- [x] 2.3 Run the baseline twice and record agreement between runs, model version, and cost
- [x] 2.4 Add Jev's metrics beside Rust and PostgreSQL in the report

## 3. Review and rotation

- [x] 3.1 Classify each failed exam case automatically by failure kind
- [x] 3.2 Add `task eval:review` to step through failures and a sample of passes

## 4. Checks

- [x] 4.1 Run `task check test build schema-check` and the Rust CI checks
