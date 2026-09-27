<p align="center">
  <img src="docs/assets/rescribo.png" alt="Rescribo wordmark banner" width="100%">
</p>

# Customer feedback, carried through to a fix

[![Checks](https://github.com/nicoleman0/rescribo/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/nicoleman0/rescribo/actions/workflows/ci.yml)
[![Python 3.14](https://img.shields.io/badge/Python-3.14-3776AB?logo=python&logoColor=white)](docs/LOCAL_DEVELOPMENT.md#requirements)
[![Node.js 24](https://img.shields.io/badge/Node.js-24-339933?logo=nodedotjs&logoColor=white)](docs/LOCAL_DEVELOPMENT.md#requirements)

Rescribo is being built to help teams turn customer reports into engineering work and keep track of the follow-up that comes after a fix.

## The workflow

- **Capture:** Record a customer report. Manual entry is available; Slack capture is planned.
- **Connect:** Group related reports and link them to GitHub issues. This workflow is in development.
- **Follow up:** Review fixes and track customer outcomes. This workflow is planned.

## Project status

Rescribo is an early development scaffold. Workspace accounts, invitations, the report inbox, and manual report entry are implemented. Slack and GitHub integrations, problem grouping, and follow-up tracking are not yet available.

## Links

- [MVP specification](docs/MVP_SPEC.md)
- [Local development guide](docs/LOCAL_DEVELOPMENT.md)
- [Architecture and development conventions](docs/DEVELOPMENT.md)
- [Implementation milestone](https://github.com/nicoleman0/rescribo/milestone/1)

## License

Copyright (C) 2026 Nicholas Coleman.

Rescribo is licensed under the [GNU Affero General Public License v3.0](LICENSE). A commercial license is available for organizations that want to embed or host Rescribo without the AGPL's source-sharing obligations — see [LICENSING.md](LICENSING.md).
