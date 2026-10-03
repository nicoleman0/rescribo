# Proposal

## Why

Reviewers need to see the full workflow without connecting Slack or GitHub. Delivers the demo part of #25 in milestone D. The deployment notes, walkthrough, and live evidence in #25 are documentation, not product behaviour, and are tracked in its tasks.

## What Changes

- Seed a separate demo workspace with fictitious companies, reports, problems, issues, mistakes, and failures.
- Label it as a demo and block integration setup and outbound calls by default.

## Capabilities

### New Capabilities
- `demo-workspace`: a seeded, clearly labelled workspace that never touches real integrations

### Modified Capabilities

## Impact

A seed management command, a demo flag on the workspace, guards in Slack and GitHub operation paths, a UI label, and deployment and walkthrough docs.
