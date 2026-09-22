# Changelog

Notable changes to this project. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

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

- The custom user model replaces Django's `auth_user`. Existing local databases must be recreated before `task migrate`. See the README (#37).
- Product access now requires an active workspace membership. `is_superuser` alone grants none (#37).

### Security

- Owner-issued password resets are limited at issue and redeem time, and a new reset invalidates earlier ones (#37).
