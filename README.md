<p align="center">
  <img src="docs/assets/rescribo.png" alt="Rescribo wordmark banner" width="100%">
</p>

# Customer feedback, carried through to a fix

[![Checks](https://github.com/nicoleman0/rescribo/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/nicoleman0/rescribo/actions/workflows/ci.yml)
[![Python 3.14](https://img.shields.io/badge/Python-3.14-3776AB?logo=python&logoColor=white)](docs/LOCAL_DEVELOPMENT.md#requirements)
[![Node.js 24](https://img.shields.io/badge/Node.js-24-339933?logo=nodedotjs&logoColor=white)](docs/LOCAL_DEVELOPMENT.md#requirements)

Rescribo is being built to help teams turn customer reports into engineering work and keep track of the follow-up that comes after a fix.

## The workflow

- **Capture:** Record a customer report. Capture a Slack message with a shortcut, or enter a report by hand.
- **Connect:** Group related reports, link a GitHub issue, or review and approve a new issue before publication.
- **Follow up:** Confirm the fix, send an approved Slack DM to the employee, and track the customer outcome.

## Project status

Rescribo is in development. The Slack-to-GitHub-to-follow-up workflow is implemented; the manual end-to-end check (#57) has not run yet. Failure and isolation coverage, retention, and the seeded demo (`task demo-seed`) are done. Local match suggestions stay off until the matcher passes its evaluation gates. Open work is in [`openspec/changes/`](openspec/changes/) and the [milestones](https://github.com/nicoleman0/rescribo/milestones).

## Links

- [Product specs](openspec/specs/)
- [Local development guide](docs/LOCAL_DEVELOPMENT.md)
- [Deployment](docs/DEPLOYMENT.md)
- [Workspace settings and provider setup](docs/SETTINGS.md)
- [Architecture and development conventions](docs/DEVELOPMENT.md)

## License

Copyright (C) 2026 Nicholas Coleman.

Rescribo is licensed under the [GNU Affero General Public License v3.0](LICENSE). A commercial license is available for organizations that want to embed or host Rescribo without the AGPL's source-sharing obligations — see [LICENSING.md](LICENSING.md).
