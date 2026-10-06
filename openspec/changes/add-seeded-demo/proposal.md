# Proposal

## Why

Reviewers need to see the full workflow without connecting Slack or GitHub. Delivers #25 in milestone D. Deployment notes, walkthrough, timings, and live evidence are documentation, not product behaviour, and are tracked in #89.

## What Changes

- Seed a separate demo workspace with fictitious companies, reports, problems, issues, mistakes, and failures.
- Label it as a demo and block integration setup and outbound calls by default.
- Publish only a member-role demo login, so visitors cannot reach owner actions, and reset the demo to its seeded state every night.

## Capabilities

### New Capabilities
- `demo-workspace`: a seeded, clearly labelled workspace that never touches real integrations

### Modified Capabilities

## Impact

A seed management command, a demo flag on the workspace, guards in Slack and GitHub operation paths, a nightly reset job, and a UI label.
