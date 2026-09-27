# Changelog

Notable changes to this project. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- Report triage: link to an existing problem, create a problem and link in one step, move, ungroup, dismiss, restore, and assign or clear the assignee from the Inbox (#9).
- Problems list with search, owner, status, report count, and review flag. Problem detail with editable title and summary, owner, linked reports with provenance, per-report assignment, and activity (#9).
- `ReportNotificationOperation` records prepared employee notifications. Reassignment, moves, and ungrouping cancel unsent ones and keep sent history. No production path creates them yet ([ADR 0004](docs/adr/0004-report-notification-cancellation.md), #9).
- Problem timelines record reports linked, moved, ungrouped, and reassigned, so removal history stays on the problem (#9).
- Inbox with paginated reports, text and customer search, status/assignee/source filters, and a report detail panel showing provenance, assignee, triage state, and related problem (#6).
- Manual report capture through the shared report workflow. Unsaved drafts survive failed requests and reloads in the same tab (#6).
- Workspace report list, detail, and create endpoints, plus a member directory readable by all members (#6).
- Workspace-scoped report and problem domain with provenance, transitions, row versions, and content-free activity (#38).
- Workspace accounts and sessions: sign-in, sign-out, invitations, memberships, owner and member roles, and one-use password resets (#37).
- `task bootstrap-owner` creates the first workspace owner. `task issue-owner-recovery` issues an owner recovery link or sets a password (#37).
- Sign-in, invitation acceptance, and password reset pages in the frontend (#37).
- `RESCRIBO_PUBLIC_BASE_URL` and `RESCRIBO_NUM_PROXIES` settings (#37).
- UI foundation: app shell, design tokens, and shared components (#36).
- Slack identity verification and follow-up boundary checks (#33).
- Slack shortcut capture feasibility check and operator scripts (#29, #31).
- GitHub installation and issue lifecycle feasibility checks (#27, #28).
- Local development environment with PostgreSQL, Redis, and Celery.

### Changed

- UI foundation shell screenshots now capture the Follow-ups placeholder, because the Inbox and Problems show live data (#6, #9).
- CI uploads Playwright screenshot differences when the browser checks fail (#6).
- The custom user model replaces Django's `auth_user`. Existing local databases must be recreated before `task migrate`. See the README (#37).
- Product access now requires an active workspace membership. `is_superuser` alone grants none (#37).

### Security

- Owner-issued password resets are limited at issue and redeem time, and a new reset invalidates earlier ones (#37).
