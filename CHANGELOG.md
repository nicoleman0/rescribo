# Changelog

Notable changes to this project. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [0.1.0] - YYYY-MM-DD

First release of Rescribo. Customer feedback captured from Slack or manual entry is triaged into problems, grouped reports are linked to GitHub issues, fixes are confirmed against releases, and employees receive approved follow-up messages.

### Added

- Reports: manual capture with draft preservation, an inbox with text and customer search, status, assignee, and source filters, per-report assignment and editing, conflicting-edit detection, and an activity history.
- Problems: one problem per recurring feedback, grouping of reports, an editable title and summary, an owner, a lifecycle from report to fix confirmation, linked reports naming where each report came from, directed state changes from problem detail, and a timeline of what was linked, moved, ungrouped, and reassigned, so removal history stays on the problem.
- GitHub integration: connect a GitHub App with minimal permissions and one selected repository, open or link one GitHub issue per problem with a Markdown create preview, recover when issue creation fails, receive verified webhooks, keep the current issue state accurate with reconciliation, and be prompted to review when a linked issue is closed.
- Fix releases: choose a release from the connected repository, link it to a confirmed fix, keep a snapshot of the linked release, and replace or remove the link.
- Slack integration: owner-initiated OAuth installation with minimal bot scopes, verified shortcut requests linked to active members, capture from approved channels with server-side capture context and editable fields, fast acknowledgement, idempotent capture, asynchronous permalinks, account linking, and removal plus revocation.
- Follow-ups: one deterministic draft per report revision reviewed by a member before sending, delivery to eligible employees with no guessed recipients, uncertain sends held back, recorded customer contact outcomes, and controlled recipient changes that refuse with a named cause.
- Match suggestions: deterministic ranking of existing problems against a report in the same workspace, with explicit abstention, distinct failure categories, stale results discarded, and a human decision on every suggestion. Suggestions stay off until the evaluation gates pass.
- Accounts: the first owner bootstrapped with `task bootstrap-owner`, one-use invitations, owner and member roles with the last owner protected, sign-in sessions, access revocation, issue and redeem limits on owner-issued password resets, and owner recovery links.
- Workspaces: every record belongs to a verified workspace, foreign records are not found, and search, aggregation, references, and credentials are scoped.
- Demo workspace: seeded demo data, a visible demo label, no real integrations, isolation from private workspaces, and a shared demo sign-in.
- Web interface: app shell with breadcrumbs, collapsible sidebar, navigation counts, user menu with running version, theme choice with system theme support, readable status in every theme, reduced motion honoured, accessible forms, and a responsive layout for phones.
- Self-hosting: a Compose production deployment, encrypted GitHub and Slack credentials at rest, no secrets or customer content in logs, short-lived capture contexts, inbound payload retention limits, and documented backup retention with a verified restore.

### Security

- Owner-issued password resets are limited at issue and redeem time, and a new reset invalidates earlier ones.
- GitHub and Slack credentials are encrypted and are never logged or exposed, and disconnecting keeps business records.
- Product access requires an active workspace membership.

[Unreleased]: https://github.com/nicoleman0/rescribo/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/nicoleman0/rescribo/releases/tag/v0.1.0
