# Tasks

## 1. Evaluation

- [ ] 1.1 Tune weights and thresholds on development data, then freeze the configuration
- [ ] 1.2 Run the held-out evaluation and publish the report with sample sizes and limitations
- [ ] 1.3 Check deterministic replay and zero invalid or cross-workspace references
- [ ] 1.4 Record whether the gates pass and set the suggestions flag accordingly

## 2. Review and rotation

- [ ] 2.1 Classify each failed exam case automatically by failure kind
- [ ] 2.2 Add `task eval:review` to step through failures and a sample of passes

## 3. Checks

- [ ] 3.1 Run `task check test build schema-check` and the Rust CI checks
